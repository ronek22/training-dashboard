import Foundation
import HealthKit
import Observation

/// Saves indoor rides (Zwift, MyWhoosh…) into Apple Health, so they count in Fitness. They reach
/// the Mac through Strava, which can't write to Health; this replaces dropping the Zwift .fit file
/// into HealthFit by hand.
///
/// Runs when the app comes to the foreground and with the background widget refresh. A ride is
/// skipped when Health already has a cycling workout at that time (an earlier HealthFit import, a
/// heart-rate app's own workout, or one saved here before a reinstall).
@MainActor
@Observable
final class RideExport {
    static let shared = RideExport()

    static let enabledKey = "healthAddIndoorRides"
    private static let savedKey = "healthIndoorRidesSaved"
    private static let lastSuccessKey = "healthIndoorRidesLastSave"
    static let path = "/integrations/indoor-rides"
    /// How far back the first run reaches, for rides that never made it into Health.
    static let window = 60

    private(set) var syncing = false
    private(set) var lastSuccess: Date?
    private(set) var lastSaved: Int?
    private(set) var failed = false

    private let store = HKHealthStore()
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        lastSuccess = defaults.object(forKey: Self.lastSuccessKey) as? Date
    }

    var enabled: Bool { defaults.bool(forKey: Self.enabledKey) }

    func requestAccess() async {
        guard HealthSync.isAvailable, enabled else { return }
        try? await store.requestAuthorization(toShare: RideWriter.shareTypes, read: [HKObjectType.workoutType()])
    }

    func sync(now: Date = .now) async {
        guard HealthSync.isAvailable, enabled, !syncing else { return }
        syncing = true
        defer { syncing = false }
        var saved = defaults.dictionary(forKey: Self.savedKey) as? [String: Date] ?? [:]
        let since = Calendar.current.date(byAdding: .day, value: -Self.window, to: now)!
        let writer = RideWriter(store: store)
        var count = 0
        do {
            // Per-second streams for every ride in the window: give it longer than a screen read.
            let rides = try await APIClient.current.send(
                "GET", "\(Self.path)?since=\(FoodFormat.iso(since))", as: IndoorRides.self, timeout: 30
            ).rides
            for ride in rides where saved[ride.id] == nil {
                guard let samples = RideSamples(ride) else { continue }
                if try await !writer.hasCyclingWorkout(from: samples.start, to: samples.end) {
                    try await writer.save(ride, samples)
                    count += 1
                }
                saved[ride.id] = now
                defaults.set(saved.filter { now.timeIntervalSince($0.value) < 90 * 86_400 }, forKey: Self.savedKey)
            }
            lastSuccess = now
            lastSaved = count
            failed = false
            defaults.set(now, forKey: Self.lastSuccessKey)
        } catch {
            // Mac out of reach, or Health locked while the phone is locked; the next run retries.
            failed = true
        }
    }
}

struct IndoorRides: Decodable, Sendable {
    let rides: [Ride]

    struct Ride: Decodable, Sendable {
        let id: String
        let name: String?
        /// UTC, "2026-10-29T17:57:37Z".
        let start: String
        let durationS: Double
        let distanceM: Double?
        let energyKcal: Double?
        let streams: Streams?

        var startDate: Date? { try? Date(start, strategy: .iso8601) }
    }

    struct Streams: Decodable, Sendable {
        let time: [Double]
        let heartrate: [Double?]?
        let watts: [Double?]?
        let cadence: [Double?]?
        let distance: [Double?]?
    }
}

/// A ride's streams as HealthKit samples: heart rate, power and cadence at each second, distance
/// and energy in one-minute slices (energy split by the work done in each, evenly without power).
struct RideSamples: Equatable {
    struct Point: Equatable {
        let date: Date
        let value: Double
    }

    struct Slice: Equatable {
        let start: Date
        let end: Date
        let value: Double
    }

    static let sliceSeconds: Double = 60

    let start: Date
    let end: Date
    var heartRate: [Point] = []
    var power: [Point] = []
    var cadence: [Point] = []
    var distance: [Slice] = []
    var energy: [Slice] = []

    init?(_ ride: IndoorRides.Ride) {
        guard ride.durationS > 0, let begin = ride.startDate else { return nil }
        start = begin
        end = begin.addingTimeInterval(ride.durationS)
        guard let streams = ride.streams, !streams.time.isEmpty else {
            if let meters = ride.distanceM, meters > 0 { distance = [.init(start: start, end: end, value: meters)] }
            if let kcal = ride.energyKcal, kcal > 0 { energy = [.init(start: start, end: end, value: kcal)] }
            return
        }
        let time = streams.time
        func points(_ values: [Double?]?, keep: (Double) -> Bool) -> [Point] {
            guard let values, values.count == time.count else { return [] }
            return zip(time, values).compactMap { offset, value in
                guard let value, keep(value) else { return nil }
                return Point(date: start.addingTimeInterval(offset), value: value)
            }
        }
        heartRate = points(streams.heartrate) { $0 > 0 }
        power = points(streams.watts) { $0 >= 0 }
        cadence = points(streams.cadence) { $0 >= 0 }

        // Slice edges: indices where a new minute starts, plus the last sample.
        var edges = [0]
        for index in time.indices.dropFirst() where time[index] - time[edges.last!] >= Self.sliceSeconds {
            edges.append(index)
        }
        if edges.last != time.count - 1 { edges.append(time.count - 1) }
        let ranges = zip(edges, edges.dropFirst()).map { $0...$1 }

        if let meters = streams.distance, meters.count == time.count {
            distance = ranges.compactMap { range in
                guard let from = meters[range.lowerBound], let to = meters[range.upperBound], to > from else { return nil }
                return slice(range, time, to - from)
            }
        }
        if let kcal = ride.energyKcal, kcal > 0 {
            let watts = streams.watts.flatMap { $0.count == time.count ? $0 : nil }
            let shares = ranges.map { range in
                guard let watts else { return time[range.upperBound] - time[range.lowerBound] }
                return range.dropFirst().reduce(0.0) { sum, index in
                    sum + (watts[index] ?? 0) * min(max(time[index] - time[index - 1], 0), 10)
                }
            }
            let total = shares.reduce(0, +)
            if total > 0 {
                energy = zip(ranges, shares).compactMap { range, share in
                    share > 0 ? slice(range, time, kcal * share / total) : nil
                }
            }
        }
    }

    private func slice(_ range: ClosedRange<Int>, _ time: [Double], _ value: Double) -> Slice {
        Slice(start: start.addingTimeInterval(time[range.lowerBound]), end: start.addingTimeInterval(time[range.upperBound]), value: value)
    }

    /// "Zwift - Endurance 60" → Zwift, shown as the workout's app in Fitness.
    static func brand(_ name: String?) -> String? {
        guard let name else { return nil }
        if name.hasPrefix("Zwift") { return "Zwift" }
        if name.localizedCaseInsensitiveContains("MyWhoosh") { return "MyWhoosh" }
        return nil
    }
}

/// HealthKit writes for one ride.
struct RideWriter: Sendable {
    let store: HKHealthStore

    static let shareTypes: Set<HKSampleType> = [
        HKObjectType.workoutType(),
        HKQuantityType(.heartRate),
        HKQuantityType(.activeEnergyBurned),
        HKQuantityType(.distanceCycling),
        HKQuantityType(.cyclingPower),
        HKQuantityType(.cyclingCadence),
    ]

    func hasCyclingWorkout(from start: Date, to end: Date) async throws -> Bool {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.workout(NSCompoundPredicate(andPredicateWithSubpredicates: [
                HKQuery.predicateForSamples(withStart: start, end: end),
                HKQuery.predicateForWorkouts(with: .cycling),
            ]))],
            sortDescriptors: []
        )
        return try await !descriptor.result(for: store).isEmpty
    }

    func save(_ ride: IndoorRides.Ride, _ samples: RideSamples) async throws {
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .cycling
        configuration.locationType = .indoor
        let builder = HKWorkoutBuilder(healthStore: store, configuration: configuration, device: nil)
        try await builder.beginCollection(at: samples.start)

        let bpm = HKUnit.count().unitDivided(by: .minute())
        var quantities: [HKSample] = []
        func add(_ id: HKQuantityTypeIdentifier, _ unit: HKUnit, _ points: [RideSamples.Point]) {
            quantities += points.map {
                HKQuantitySample(type: HKQuantityType(id), quantity: HKQuantity(unit: unit, doubleValue: $0.value), start: $0.date, end: $0.date)
            }
        }
        func add(_ id: HKQuantityTypeIdentifier, _ unit: HKUnit, _ slices: [RideSamples.Slice]) {
            quantities += slices.map {
                HKQuantitySample(type: HKQuantityType(id), quantity: HKQuantity(unit: unit, doubleValue: $0.value), start: $0.start, end: $0.end)
            }
        }
        add(.heartRate, bpm, samples.heartRate)
        add(.cyclingPower, .watt(), samples.power)
        add(.cyclingCadence, bpm, samples.cadence)
        add(.distanceCycling, .meter(), samples.distance)
        add(.activeEnergyBurned, .kilocalorie(), samples.energy)
        if !quantities.isEmpty { try await builder.addSamples(quantities) }

        var metadata: [String: Any] = [
            HKMetadataKeyIndoorWorkout: true,
            HKMetadataKeyExternalUUID: "trainlog:\(ride.id)",
        ]
        if let brand = RideSamples.brand(ride.name) { metadata[HKMetadataKeyWorkoutBrandName] = brand }
        try await builder.addMetadata(metadata)
        try await builder.endCollection(at: samples.end)
        _ = try await builder.finishWorkout()
    }
}
