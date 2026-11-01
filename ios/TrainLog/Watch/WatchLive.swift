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
    /// A button pressed on the Watch, for the screen showing the same workout here.
    var onCommand: ((WatchWire.Command) -> Void)?
    /// The Watch's strength session after a change there.
    var onStrength: ((WatchWire.Strength) -> Void)?

    private var session: HKWorkoutSession?
    private let store = HKHealthStore()
    private var lastLaunch: HKWorkoutActivityType?
    /// What this phone leads, with everything included: sent again when the Watch attaches late.
    private var leading = WatchWire.Live()

    /// The Watch's workout is mirrored here.
    var linked: Bool { session != nil }

    /// Settings: workouts started here open TrainLog on the Watch. On unless turned off.
    var autoStart: Bool {
        UserDefaults.standard.object(forKey: Self.autoStartKey) as? Bool ?? true
    }

    /// Starting a workout here will open TrainLog on the Watch.
    var canStartOnWatch: Bool {
        let connectivity = WCSession.default
        return autoStart && WCSession.isSupported() && connectivity.activationState == .activated
            && connectivity.isPaired && connectivity.isWatchAppInstalled
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

    /// A workout started on the phone: TrainLog on the Watch starts the Health workout for heart
    /// rate and shows the same session. Skipped when the Watch already runs one, the app isn't on
    /// the Watch, or Settings turned it off.
    func startOnWatch(_ activity: HKWorkoutActivityType) {
        lastLaunch = activity
        guard canStartOnWatch, session == nil else { return }
        launch(activity)
    }

    /// The chip's Retry.
    func retry() {
        guard let lastLaunch, session == nil else { return }
        launch(lastLaunch)
    }

    private func launch(_ activity: HKWorkoutActivityType) {
        join = .joining
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = activity
        configuration.locationType = .indoor
        store.startWatchApp(with: configuration) { @Sendable started, _ in
            Task { @MainActor in WatchLive.shared.launched(started) }
        }
    }

    private func launched(_ started: Bool) {
        guard session == nil else { return }
        guard started else {
            join = .failed
            return
        }
        // Launched, but the workout has to start and mirror back; give it a while.
        Task {
            try? await Task.sleep(for: .seconds(20))
            if session == nil, join == .joining { join = .failed }
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
        send(WatchWire.Live(rehab: state))
    }

    /// The strength session changed here (a set, a jump, the server's progressed copy).
    func share(strength: WatchWire.Strength) {
        leading.strength = strength
        send(WatchWire.Live(strength: strength))
    }

    /// The workout shown here closed: nothing to send a late Watch any more.
    func stopLeading() {
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
        // A routine already under way on the Watch: ask for it from the start, exercises included.
        send(.sync)
        // And whatever this phone was already running, for a Watch that joined late.
        sendLeading()
    }

    private func sendLeading() {
        guard leading.rehab != nil || leading.strength != nil else { return }
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
        switch live.command {
        case nil: break
        // The Watch asking for everything again: what this phone leads.
        case .sync: sendLeading()
        case let command?: onCommand?(command)
        }
    }

    fileprivate func ended() {
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
        Task { @MainActor in WatchLive.shared.ended() }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didDisconnectFromRemoteDeviceWithError error: Error?) {
        Task { @MainActor in WatchLive.shared.ended() }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {}
}
