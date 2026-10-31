import Foundation
import HealthKit
import Observation

/// The workout running on the Watch, mirrored here (iOS 17+ workout mirroring): its live heart
/// rate for the strength screen. HealthKit hands the session over even with the app in the
/// background, so the handler is set at launch.
@MainActor
@Observable
final class WatchLive: NSObject {
    static let shared = WatchLive()

    private(set) var heartRate: Double?
    private(set) var updatedAt: Date?
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

    private func attach(_ session: HKWorkoutSession) {
        self.session = session
        session.delegate = self
    }

    fileprivate func received(_ live: WatchWire.Live) {
        guard let bpm = live.heartRate else { return }
        heartRate = bpm
        updatedAt = .now
    }

    fileprivate func ended() {
        session = nil
        heartRate = nil
        updatedAt = nil
    }
}

extension WatchLive: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didReceiveDataFromRemoteWorkoutSession data: [Data]) {
        let readings = data.compactMap { try? JSONDecoder().decode(WatchWire.Live.self, from: $0) }
        guard let latest = readings.last else { return }
        Task { @MainActor in WatchLive.shared.received(latest) }
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
