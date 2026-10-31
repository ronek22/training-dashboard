import Foundation
import HealthKit
import Observation

/// The HealthKit workout behind a session: live heart rate and energy, the app kept frontmost (and
/// Always On) while it runs, mirrored to the iPhone, and saved to Apple Health at the end so Strava
/// imports it like any Apple Workout.
@MainActor
@Observable
final class WorkoutTracker: NSObject {
    static let shared = WorkoutTracker()

    struct Summary: Equatable {
        let duration: TimeInterval
        let averageHeartRate: Double?
        let maxHeartRate: Double?
        let activeKcal: Double?
        /// Saved to Apple Health.
        let saved: Bool
    }

    private(set) var heartRate: Double?
    private(set) var activeKcal: Double?
    private(set) var running = false
    private(set) var paused = false
    private(set) var startDate: Date?
    /// Highest reading this workout; HealthKit's own maximum isn't available until the end.
    private(set) var maxHeartRate: Double?
    /// Heart rate going down (resting) or up since the previous reading.
    private(set) var falling = false

    let store = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    private var lastMirrored = Date.distantPast

    var available: Bool { HKHealthStore.isHealthDataAvailable() }

    func requestAuthorization() async {
        guard available else { return }
        let share: Set<HKSampleType> = [HKQuantityType.workoutType()]
        let read: Set<HKObjectType> = [HKQuantityType(.heartRate), HKQuantityType(.activeEnergyBurned), HKQuantityType.workoutType()]
        try? await store.requestAuthorization(toShare: share, read: read)
    }

    /// Time since the start, paused time left out.
    func elapsed(at date: Date = .now) -> TimeInterval {
        builder?.elapsedTime(at: date) ?? startDate.map { date.timeIntervalSince($0) } ?? 0
    }

    func start(_ activity: HKWorkoutActivityType) async {
        guard available, session == nil else { return }
        await requestAuthorization()
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = activity
        configuration.locationType = .indoor
        do {
            let session = try HKWorkoutSession(healthStore: store, configuration: configuration)
            let builder = session.associatedWorkoutBuilder()
            builder.dataSource = HKLiveWorkoutDataSource(healthStore: store, workoutConfiguration: configuration)
            session.delegate = self
            builder.delegate = self
            self.session = session
            self.builder = builder
            let start = Date.now
            session.startActivity(with: start)
            try await builder.beginCollection(at: start)
            startDate = start
            running = true
            paused = false
            heartRate = nil
            maxHeartRate = nil
            activeKcal = nil
            // The phone's strength screen shows the live heart rate.
            try? await session.startMirroringToCompanionDevice()
        } catch {
            reset()
        }
    }

    /// After a crash or relaunch mid-workout: picks the running session back up. The app delegate
    /// and the root view both ask; they share one attempt, so neither starts a second workout
    /// while the first is still being recovered.
    func recover() async {
        if let recovering { return await recovering.value }
        let attempt = Task { await recoverOnce() }
        recovering = attempt
        await attempt.value
    }

    private var recovering: Task<Void, Never>?

    private func recoverOnce() async {
        guard session == nil, let recovered = try? await store.recoverActiveWorkoutSession() else { return }
        session = recovered
        builder = recovered.associatedWorkoutBuilder()
        recovered.delegate = self
        builder?.delegate = self
        builder?.dataSource = HKLiveWorkoutDataSource(healthStore: store, workoutConfiguration: recovered.workoutConfiguration)
        startDate = recovered.startDate
        running = true
        paused = recovered.state == .paused
    }

    func togglePause() {
        guard let session else { return }
        if paused { session.resume() } else { session.pause() }
    }

    /// Ends the workout and saves it to Apple Health.
    func finish() async -> Summary {
        let end = Date.now
        let duration = elapsed(at: end)
        let fallback = Summary(duration: duration, averageHeartRate: nil, maxHeartRate: maxHeartRate, activeKcal: activeKcal, saved: false)
        guard let session, let builder else { reset(); return fallback }
        session.end()
        do {
            try await builder.endCollection(at: end)
            let workout = try await builder.finishWorkout()
            let bpm = HKUnit.count().unitDivided(by: .minute())
            let heart = builder.statistics(for: HKQuantityType(.heartRate))
            let energy = builder.statistics(for: HKQuantityType(.activeEnergyBurned))?.sumQuantity()
            let summary = Summary(
                duration: workout?.duration ?? duration,
                averageHeartRate: heart?.averageQuantity()?.doubleValue(for: bpm),
                maxHeartRate: heart?.maximumQuantity()?.doubleValue(for: bpm) ?? maxHeartRate,
                activeKcal: energy?.doubleValue(for: .kilocalorie()) ?? activeKcal,
                saved: workout != nil
            )
            reset()
            return summary
        } catch {
            reset()
            return fallback
        }
    }

    /// Ends without saving anything to Apple Health.
    func discard() {
        session?.end()
        builder?.discardWorkout()
        reset()
    }

    private func reset() {
        session = nil
        builder = nil
        running = false
        paused = false
        startDate = nil
    }

    fileprivate func collected(_ types: Set<HKSampleType>) {
        guard let builder else { return }
        if types.contains(HKQuantityType(.heartRate)),
           let value = builder.statistics(for: HKQuantityType(.heartRate))?.mostRecentQuantity()?
               .doubleValue(for: .count().unitDivided(by: .minute())) {
            falling = heartRate.map { value < $0 } ?? false
            heartRate = value
            maxHeartRate = max(maxHeartRate ?? 0, value)
        }
        if types.contains(HKQuantityType(.activeEnergyBurned)) {
            activeKcal = builder.statistics(for: HKQuantityType(.activeEnergyBurned))?.sumQuantity()?.doubleValue(for: .kilocalorie())
        }
        mirror()
    }

    /// At most every 3 s: enough for a live number on the phone.
    private func mirror() {
        guard let session, Date.now.timeIntervalSince(lastMirrored) >= 3,
              let data = try? JSONEncoder().encode(WatchWire.Live(heartRate: heartRate, activeKcal: activeKcal))
        else { return }
        lastMirrored = .now
        session.sendToRemoteWorkoutSession(data: data) { @Sendable _, _ in }
    }

    #if DEBUG
    func demo(heartRate: Double, startedMinutesAgo minutes: Double) {
        self.heartRate = heartRate
        startDate = Date.now.addingTimeInterval(-minutes * 60)
        running = true
    }
    #endif

    fileprivate func stateChanged(_ state: HKWorkoutSessionState) {
        paused = state == .paused
    }
}

extension WorkoutTracker: HKWorkoutSessionDelegate, HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didChangeTo toState: HKWorkoutSessionState, from fromState: HKWorkoutSessionState, date: Date) {
        Task { @MainActor in WorkoutTracker.shared.stateChanged(toState) }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {}

    nonisolated func workoutBuilder(_ workoutBuilder: HKLiveWorkoutBuilder, didCollectDataOf collectedTypes: Set<HKSampleType>) {
        Task { @MainActor in WorkoutTracker.shared.collected(collectedTypes) }
    }

    nonisolated func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}
}
