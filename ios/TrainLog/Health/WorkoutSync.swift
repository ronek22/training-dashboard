import CoreLocation
import Foundation
import HealthKit
import Observation

/// Sends Apple Watch workouts to the backend as soon as HealthKit saves them, so Today and the
/// training load don't wait for the next Strava import. HealthKit wakes the app in the background
/// for a new workout; the app also checks when it comes to the foreground.
///
/// Each run reads the last week of workouts and skips the ones already sent (the backend ignores
/// a re-push too), so a push missed while the Mac was unreachable goes out with the next one.
@MainActor
@Observable
final class WorkoutSync {
    static let shared = WorkoutSync()

    static let enabledKey = "healthSendWorkouts"
    private static let sentKey = "healthWorkoutsSent"
    private static let lastSuccessKey = "healthWorkoutsLastPush"
    static let pushPath = "/integrations/health-workouts/push"

    private(set) var syncing = false
    private(set) var lastSuccess: Date?
    private(set) var failed = false

    private let store = HKHealthStore()
    private let defaults: UserDefaults
    private var observer: HKObserverQuery?
    private var rerun = false

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        lastSuccess = defaults.object(forKey: Self.lastSuccessKey) as? Date
    }

    var enabled: Bool { defaults.bool(forKey: Self.enabledKey) }

    func requestAccess() async {
        guard HealthSync.isAvailable, enabled else { return }
        try? await store.requestAuthorization(toShare: [], read: Set(WorkoutReader.readTypes))
    }

    /// Call at launch and after the toggle changes, like `HealthSync.startObserving`.
    func startObserving() {
        if let observer { store.stop(observer) }
        observer = nil
        guard HealthSync.isAvailable else { return }
        let type = HKObjectType.workoutType()
        guard enabled else {
            store.disableBackgroundDelivery(for: type) { _, _ in }
            return
        }
        let query = HKObserverQuery(sampleType: type, predicate: nil) { _, completion, error in
            guard error == nil else { return completion() }
            nonisolated(unsafe) let done = completion
            Task { @MainActor in
                await WorkoutSync.shared.sync()
                // A finished workout ticks off today's session on the widgets.
                await WidgetSync.refreshInBackground()
                done()
            }
        }
        store.execute(query)
        observer = query
        store.enableBackgroundDelivery(for: type, frequency: .immediate) { _, _ in }
    }

    func sync() async {
        guard HealthSync.isAvailable, enabled else { return }
        if syncing {
            rerun = true
            return
        }
        syncing = true
        let now = Date.now
        var sent = defaults.dictionary(forKey: Self.sentKey) as? [String: Date] ?? [:]
        let reader = WorkoutReader(store: store)
        do {
            let since = Calendar.current.date(byAdding: .day, value: -7, to: now)!
            for workout in try await reader.workouts(since: since) where sent[workout.uuid.uuidString] == nil {
                let push = WorkoutPush(workouts: [try await reader.payload(for: workout)])
                _ = try await APIClient.current.send(
                    "POST", Self.pushPath, body: try APIClient.encoder.encode(push), as: WorkoutPushResult.self, timeout: 30
                )
                sent[workout.uuid.uuidString] = now
                // Saved after each workout, so a failure part way through doesn't resend the rest.
                defaults.set(sent.filter { now.timeIntervalSince($0.value) < 30 * 86_400 }, forKey: Self.sentKey)
            }
            lastSuccess = now
            failed = false
            defaults.set(now, forKey: Self.lastSuccessKey)
        } catch {
            failed = true
        }
        syncing = false
        if rerun {
            rerun = false
            await sync()
        }
    }
}

/// HealthKit reads for one workout: its summary statistics, route and in-workout samples.
struct WorkoutReader: Sendable {
    let store: HKHealthStore

    static let readTypes: [HKObjectType] = [
        HKObjectType.workoutType(),
        HKSeriesType.workoutRoute(),
        HKQuantityType(.heartRate),
        HKQuantityType(.activeEnergyBurned),
        HKQuantityType(.distanceWalkingRunning),
        HKQuantityType(.distanceCycling),
        HKQuantityType(.cyclingPower),
        HKQuantityType(.cyclingCadence),
        HKQuantityType(.cyclingSpeed),
        HKQuantityType(.runningPower),
        HKQuantityType(.runningSpeed),
    ]

    func workouts(since start: Date) async throws -> [HKWorkout] {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.workout(HKQuery.predicateForSamples(withStart: start, end: nil))],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        return try await descriptor.result(for: store).filter {
            WorkoutKind.isAppleRecorded(bundle: $0.sourceRevision.source.bundleIdentifier)
        }
    }

    func payload(for workout: HKWorkout) async throws -> WorkoutPush.Workout {
        let activity = workout.workoutActivityType
        let indoor = workout.metadata?[HKMetadataKeyIndoorWorkout] as? Bool ?? false
        let bpm = HKUnit.count().unitDivided(by: .minute())
        let distanceType: HKQuantityType? = switch activity {
        case .cycling: HKQuantityType(.distanceCycling)
        case .running, .walking, .hiking: HKQuantityType(.distanceWalkingRunning)
        default: nil
        }
        let powerType = activity == .running ? HKQuantityType(.runningPower) : HKQuantityType(.cyclingPower)
        let elevation = (workout.metadata?[HKMetadataKeyElevationAscended] as? HKQuantity)?.doubleValue(for: .meter())

        var payload = WorkoutPush.Workout(
            uuid: workout.uuid.uuidString,
            type: WorkoutKind.type(activity),
            name: WorkoutKind.name(activity, indoor: indoor),
            start: HealthPush.timestamp(workout.startDate),
            end: HealthPush.timestamp(workout.endDate),
            durationS: workout.duration.rounded(),
            distanceM: distanceType.flatMap { workout.statistics(for: $0)?.sumQuantity()?.doubleValue(for: .meter()) },
            energyKcal: workout.statistics(for: HKQuantityType(.activeEnergyBurned))?.sumQuantity()?.doubleValue(for: .kilocalorie()),
            elevationM: elevation,
            avgHr: workout.statistics(for: HKQuantityType(.heartRate))?.averageQuantity()?.doubleValue(for: bpm),
            maxHr: workout.statistics(for: HKQuantityType(.heartRate))?.maximumQuantity()?.doubleValue(for: bpm),
            avgWatts: workout.statistics(for: powerType)?.averageQuantity()?.doubleValue(for: .watt()),
            sourceBundle: workout.sourceRevision.source.bundleIdentifier,
            device: workout.sourceRevision.productType
        )
        let speedType = activity == .running ? HKQuantityType(.runningSpeed) : HKQuantityType(.cyclingSpeed)
        payload.streams = WorkoutStreamBuilder().build(
            start: workout.startDate,
            locations: try await route(of: workout),
            heartRate: try await samples(.heartRate, bpm, during: workout),
            power: try await samples(powerType, .watt(), during: workout),
            cadence: activity == .cycling ? try await samples(.cyclingCadence, bpm, during: workout) : [],
            speed: try await samples(speedType, .meter().unitDivided(by: .second()), during: workout)
        )
        return payload
    }

    private func samples(
        _ id: HKQuantityTypeIdentifier, _ unit: HKUnit, during workout: HKWorkout
    ) async throws -> [WorkoutStreamBuilder.Sample] {
        try await samples(HKQuantityType(id), unit, during: workout)
    }

    private func samples(
        _ type: HKQuantityType, _ unit: HKUnit, during workout: HKWorkout
    ) async throws -> [WorkoutStreamBuilder.Sample] {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: type, predicate: HKQuery.predicateForSamples(
                withStart: workout.startDate, end: workout.endDate, options: .strictStartDate
            ))],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        return try await descriptor.result(for: store).map {
            WorkoutStreamBuilder.Sample(date: $0.startDate, value: $0.quantity.doubleValue(for: unit))
        }
    }

    private func route(of workout: HKWorkout) async throws -> [WorkoutStreamBuilder.Location] {
        let routes = try await HKSampleQueryDescriptor(
            predicates: [.workoutRoute(HKQuery.predicateForObjects(from: workout))],
            sortDescriptors: [SortDescriptor(\.startDate)]
        ).result(for: store)
        var locations: [WorkoutStreamBuilder.Location] = []
        for route in routes {
            for try await location in HKWorkoutRouteQueryDescriptor(route).results(for: store) {
                locations.append(.init(
                    date: location.timestamp,
                    latitude: location.coordinate.latitude,
                    longitude: location.coordinate.longitude,
                    altitude: location.altitude,
                    speed: location.speed >= 0 ? location.speed : nil
                ))
            }
        }
        return locations
    }
}
