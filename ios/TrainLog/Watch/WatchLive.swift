import Foundation
import HealthKit
import Observation
import WatchConnectivity

/// The workout running on the Watch, mirrored here (iOS 17+ workout mirroring), and the phone's
/// side of the two-way channel it opens: live heart rate, a rehab routine run on either device,
/// the strength session after each change, and button presses (`WatchWire.Live`).
///
/// A workout started here opens TrainLog on the Watch (`startOnWatch`), which starts the Health
/// workout and mirrors it back. HealthKit hands the session over even with the app in the
/// background, so the handler is set at launch.
@MainActor
@Observable
final class WatchLive: NSObject {
    static let shared = WatchLive()
    static let autoStartKey = "watchAutoStart"

    enum Join: Equatable {
        case none
        /// The Watch app was asked to start the workout; waiting for it to mirror back.
        case joining
        /// It didn't (off the wrist, out of reach, or turned down).
        case failed
    }

    private(set) var heartRate: Double?
    private(set) var updatedAt: Date?
    /// A rehab routine running on the Watch, for the phone to follow.
    private(set) var rehab: WatchWire.Rehab?
    /// That routine's exercises, as the Watch loaded them.
    private(set) var rehabSession: GuidedSession?
    private(set) var join: Join = .none
    /// When the Watch was asked to wake, for "Still waking…" after a while.
    private(set) var joiningSince: Date?
    /// When the Watch last asked over WatchConnectivity what this phone has open: it's awake and
    /// talking even before the mirrored workout links.
    private(set) var contactedAt: Date?
    /// A button pressed on the Watch, for the screen showing the same workout here.
    var onCommand: ((WatchWire.Command) -> Void)?
    /// The Watch's strength session after a change there.
    var onStrength: ((WatchWire.Strength) -> Void)?

    private var session: HKWorkoutSession?
    private let store = HKHealthStore()
    private var lastLaunch: HKWorkoutActivityType?
    /// What this phone leads, with everything included: sent again when the Watch attaches late,
    /// and the answer when the Watch asks over WatchConnectivity.
    private var leading = WatchWire.Live()
    /// Closed before Start: the Watch, if it asks over WatchConnectivity, is told to drop its ready
    /// screen (the mirrored `discard` may not have reached it).
    private var discardPending = false

    /// The Watch's workout is mirrored here.
    var linked: Bool { session != nil }

    /// Awake and talking: linked, or asked over WatchConnectivity in the last few seconds.
    func ready(at date: Date = .now) -> Bool {
        linked || contactedAt.map { date.timeIntervalSince($0) < 6 } ?? false
    }

    /// Settings: workouts started here open TrainLog on the Watch. On unless turned off.
    var autoStart: Bool {
        UserDefaults.standard.object(forKey: Self.autoStartKey) as? Bool ?? true
    }

    /// Opening a workout here will try to wake TrainLog on the Watch. Only needs a paired Watch:
    /// `isWatchAppInstalled` misses an app installed straight onto the Watch (how development
    /// builds get there), and a launch that fails shows Retry anyway.
    var canStartOnWatch: Bool {
        let connectivity = WCSession.default
        guard autoStart, HKHealthStore.isHealthDataAvailable(), WCSession.isSupported() else { return false }
        // Before WatchConnectivity has activated, `isPaired` isn't known yet: try.
        return connectivity.activationState != .activated || connectivity.isPaired
    }

    /// A reading from the last 20 s; older means the Watch stopped sending.
    func liveHeartRate(at date: Date = .now) -> Double? {
        guard let updatedAt, date.timeIntervalSince(updatedAt) < 20 else { return nil }
        return heartRate
    }

    func start() {
        guard HKHealthStore.isHealthDataAvailable() else { return }
        store.workoutSessionMirroringStartHandler = { @Sendable session in
            Task { @MainActor in WatchLive.shared.attach(session) }
        }
    }

    // MARK: Starting on the Watch

    /// A workout opened on the phone: TrainLog on the Watch wakes, links up and waits on a ready
    /// screen; Start on either device starts both (or, for a session already running, it joins
    /// straight away). Skipped when the Watch already runs one, the app isn't on the Watch, or
    /// Settings turned it off.
    func startOnWatch(_ activity: HKWorkoutActivityType) {
        lastLaunch = activity
        guard canStartOnWatch, session == nil else { return }
        launch(activity)
    }

    /// The chip's Retry.
    func retry() {
        guard let lastLaunch, session == nil else { return }
        WatchLinkLog.shared.add("Retry")
        launch(lastLaunch)
    }

    private func launch(_ activity: HKWorkoutActivityType) {
        join = .joining
        joiningSince = .now
        WatchLinkLog.shared.add("Waking the Watch (\(activity.rawValue))")
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = activity
        configuration.locationType = .indoor
        store.startWatchApp(with: configuration) { @Sendable started, error in
            let reason = error?.localizedDescription
            Task { @MainActor in WatchLive.shared.launched(started, reason: reason) }
        }
        // The workout has to start on the Watch and mirror back, which takes longer with the
        // wrist down; past 45 s without a word from it, say so.
        let since = joiningSince
        Task {
            try? await Task.sleep(for: .seconds(45))
            guard joiningSince == since, join == .joining, !ready() else { return }
            join = .failed
            WatchLinkLog.shared.add("No answer from the Watch after 45 s")
        }
    }

    private func launched(_ started: Bool, reason: String?) {
        guard session == nil else { return }
        if started {
            WatchLinkLog.shared.add("Watch app launched")
        } else {
            join = .failed
            WatchLinkLog.shared.add("Launch failed: \(reason ?? "no reason given")")
        }
    }

    // MARK: Sending

    func send(_ command: WatchWire.Command) {
        send(WatchWire.Live(command: command))
    }

    /// A rehab routine run here moved; `state` carries the routine on the first call.
    func share(rehab state: WatchWire.Rehab) {
        let routine = state.session ?? leading.rehab?.session
        leading.rehab = state
        leading.rehab?.session = routine
        leading.pending = nil
        discardPending = false
        send(WatchWire.Live(rehab: state))
    }

    /// The strength session changed here (a set, a jump, the server's progressed copy).
    func share(strength: WatchWire.Strength) {
        leading.strength = strength
        leading.pending = nil
        discardPending = false
        send(WatchWire.Live(strength: strength))
    }

    /// A workout open here and not started yet, for the Watch's ready screen.
    func share(pending: WatchWire.Pending) {
        discardPending = false
        leading.pending = pending
        send(WatchWire.Live(pending: pending))
    }

    /// The workout shown here closed: nothing to send a late Watch any more. Closed before Start,
    /// the Watch drops its ready screen (nothing was recorded).
    func stopLeading() {
        if leading.pending != nil {
            send(.discard)
            discardPending = true
        }
        leading = WatchWire.Live()
        lastLaunch = nil
        if session == nil { join = .none }
    }

    private func send(_ live: WatchWire.Live) {
        guard let session, let data = try? JSONEncoder().encode(live) else { return }
        session.sendToRemoteWorkoutSession(data: data) { @Sendable _, _ in }
    }

    // MARK: Receiving

    private func attach(_ session: HKWorkoutSession) {
        self.session = session
        session.delegate = self
        join = .none
        WatchLinkLog.shared.add("Linked: the Watch's workout is mirrored here")
        // A routine already under way on the Watch: ask for it from the start, exercises included.
        send(.sync)
        // And whatever this phone was already running, for a Watch that joined late.
        sendLeading()
    }

    /// The Watch asking over WatchConnectivity what this phone has open (its ready screen, before
    /// or without the mirrored link).
    func leadingForWatch() -> WatchWire.Reply {
        if contactedAt == nil || !ready() { WatchLinkLog.shared.add("Watch asked what's open") }
        contactedAt = .now
        if join == .joining || join == .failed { join = .none }
        if discardPending {
            discardPending = false
            return WatchWire.Reply(status: 200, data: try? JSONEncoder().encode(WatchWire.Live(command: .discard)))
        }
        return WatchWire.Reply(status: 200, data: try? JSONEncoder().encode(leading))
    }

    /// A button on the Watch, over either channel.
    func received(_ command: WatchWire.Command) {
        switch command {
        case .sync: sendLeading()
        case .start:
            WatchLinkLog.shared.add("Start pressed on the Watch")
            onCommand?(command)
        default: onCommand?(command)
        }
    }

    private func sendLeading() {
        guard leading.rehab != nil || leading.strength != nil || leading.pending != nil else { return }
        send(leading)
    }

    fileprivate func received(_ live: WatchWire.Live) {
        if let bpm = live.heartRate {
            heartRate = bpm
            updatedAt = .now
        }
        if var state = live.rehab {
            if let data = state.session {
                rehabSession = try? JSONDecoder().decode(GuidedSession.self, from: data)
                state.session = nil
            } else if rehabSession == nil {
                send(.sync)
            }
            rehab = state
        }
        if let strength = live.strength { onStrength?(strength) }
        if let command = live.command { received(command) }
    }

    fileprivate func ended(_ reason: String) {
        if session != nil { WatchLinkLog.shared.add(reason) }
        session = nil
        heartRate = nil
        updatedAt = nil
        rehab = nil
        rehabSession = nil
    }
}

extension WatchLive: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didReceiveDataFromRemoteWorkoutSession data: [Data]) {
        // Every one in order: an earlier one may carry the routine a later one leaves out.
        let readings = data.compactMap { try? JSONDecoder().decode(WatchWire.Live.self, from: $0) }
        Task { @MainActor in readings.forEach(WatchLive.shared.received) }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didChangeTo toState: HKWorkoutSessionState, from fromState: HKWorkoutSessionState, date: Date) {
        guard toState == .ended || toState == .stopped else { return }
        Task { @MainActor in WatchLive.shared.ended("The Watch's workout ended") }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didDisconnectFromRemoteDeviceWithError error: Error?) {
        let reason = error.map { "Link to the Watch dropped: \($0.localizedDescription)" } ?? "Link to the Watch dropped"
        Task { @MainActor in WatchLive.shared.ended(reason) }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {}
}
