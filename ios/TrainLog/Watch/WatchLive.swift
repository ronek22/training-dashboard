import Foundation
import HealthKit
import Observation

/// The workout running on the Watch, mirrored here (iOS 17+ workout mirroring): its live heart
/// rate for the strength screen, and a rehab routine's step for the phone to follow along (with
/// Next, Back and Pause sent back). HealthKit hands the session over even with the app in the
/// background, so the handler is set at launch.
@MainActor
@Observable
final class WatchLive: NSObject {
    static let shared = WatchLive()

    private(set) var heartRate: Double?
    private(set) var updatedAt: Date?
    /// The Watch's rehab routine, while one runs there.
    private(set) var rehab: WatchWire.Rehab?
    /// That routine's exercises, as the Watch loaded them.
    private(set) var rehabSession: GuidedSession?
    private var session: HKWorkoutSession?
    private let store = HKHealthStore()

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

    /// Presses a button on the Watch's rehab routine.
    func send(_ action: WatchWire.Command.Action) {
        guard let session, let data = try? JSONEncoder().encode(WatchWire.Command(action: action)) else { return }
        session.sendToRemoteWorkoutSession(data: data) { @Sendable _, _ in }
    }

    private func attach(_ session: HKWorkoutSession) {
        self.session = session
        session.delegate = self
        // A routine already under way: ask for it from the start, exercises included.
        send(.sync)
    }

    fileprivate func received(_ live: WatchWire.Live) {
        if let bpm = live.heartRate {
            heartRate = bpm
            updatedAt = .now
        }
        guard var state = live.rehab else { return }
        if let data = state.session {
            rehabSession = try? JSONDecoder().decode(GuidedSession.self, from: data)
            state.session = nil
        } else if rehabSession == nil {
            send(.sync)
        }
        rehab = state
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
