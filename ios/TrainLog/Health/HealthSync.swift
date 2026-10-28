import Foundation
import HealthKit
import Observation

/// Reads Apple Health on the phone and pushes it to the backend, replacing the Health Data Export
/// app's iCloud files. Runs when the app comes to the foreground and whenever HealthKit wakes it
/// in the background with new samples (the watch syncing sleep in the morning, a new HRV reading).
@MainActor
@Observable
final class HealthSync {
    static let shared = HealthSync()

    /// Settings toggles (also read with @AppStorage).
    static let recoveryKey = "healthReadRecovery"
    static let weightKey = "healthReadWeight"
    private static let lastSuccessKey = "healthLastPush"
    private static let lastInsertedKey = "healthLastInserted"
    static let pushPath = "/integrations/health-data/push"

    nonisolated static var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    private(set) var syncing = false
    private(set) var lastSuccess: Date?
    private(set) var lastInserted: Int?
    /// The last attempt couldn't read Health or reach the Mac; the next one re-sends the window.
    private(set) var failed = false

    private let store = HKHealthStore()
    private let defaults: UserDefaults
    private var lastAttempt: Date?
    private var rerun = false
    private var observers: [HKObserverQuery] = []

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        lastSuccess = defaults.object(forKey: Self.lastSuccessKey) as? Date
        lastInserted = defaults.object(forKey: Self.lastInsertedKey) as? Int
    }

    var readsRecovery: Bool { defaults.bool(forKey: Self.recoveryKey) }
    var readsWeight: Bool { defaults.bool(forKey: Self.weightKey) }

    private var types: [HKSampleType] {
        (readsRecovery ? HealthReader.recoveryTypes : []) + (readsWeight ? [HealthReader.weightType] : [])
    }

    /// Shows the Health permission sheet for whatever the toggles now ask for. HealthKit never says
    /// whether reading was allowed; a denied type just reads as empty.
    func requestAccess() async {
        guard Self.isAvailable, !types.isEmpty else { return }
        let live = readsRecovery ? LiveHealth.types : []
        try? await store.requestAuthorization(toShare: [], read: Set(types + live))
    }

    /// Call at launch and after a toggle changes. HealthKit relaunches the app in the background for
    /// new samples only if the observer queries are running again by the time launch finishes.
    func startObserving() {
        observers.forEach(store.stop)
        observers = []
        guard Self.isAvailable else { return }
        let types = types
        guard !types.isEmpty else {
            store.disableAllBackgroundDelivery { _, _ in }
            return
        }
        for type in types {
            let query = HKObserverQuery(sampleType: type, predicate: nil) { _, completion, error in
                guard error == nil else { return completion() }
                // HealthKit allows calling it from any thread; it isn't annotated @Sendable.
                nonisolated(unsafe) let done = completion
                Task { @MainActor in
                    await HealthSync.shared.sync()
                    done()
                }
            }
            store.execute(query)
            observers.append(query)
            // Steps change all day; the rest arrive a few times a day at most.
            let frequency: HKUpdateFrequency = HealthReader.dailyTotalTypes.contains(type) ? .hourly : .immediate
            store.enableBackgroundDelivery(for: type, frequency: frequency) { _, _ in }
        }
    }

    /// Reads the window and pushes it. Overlapping calls (each observer fires at launch) collapse into
    /// one run plus at most one more; outside of `force` a run within a minute of the last is skipped.
    func sync(force: Bool = false) async {
        guard Self.isAvailable, readsRecovery || readsWeight else { return }
        if syncing {
            rerun = true
            return
        }
        if !force, let lastAttempt, Date.now.timeIntervalSince(lastAttempt) < 60 { return }
        syncing = true
        lastAttempt = .now
        let now = Date.now
        let reader = HealthReader(store: store)
        do {
            let push = try await reader.read(
                from: HealthPush.windowStart(now: now, lastSuccess: lastSuccess), to: now,
                recovery: readsRecovery, weight: readsWeight
            )
            let result = try await APIClient.current.send(
                "POST", Self.pushPath, body: try APIClient.encoder.encode(push), as: HealthPushResult.self, timeout: 15
            )
            lastSuccess = now
            lastInserted = result.samplesInserted
            failed = false
            defaults.set(now, forKey: Self.lastSuccessKey)
            defaults.set(result.samplesInserted, forKey: Self.lastInsertedKey)
        } catch {
            failed = true
        }
        syncing = false
        if rerun {
            rerun = false
            await sync(force: true)
        }
    }
}

/// HealthKit queries for one push. Samples keep their own source; steps, distance and flights are
/// HealthKit's de-duplicated daily sums (watch and phone counted once).
struct HealthReader: Sendable {
    let store: HKHealthStore

    static let recoveryTypes: [HKSampleType] = [
        HKQuantityType(.restingHeartRate),
        HKQuantityType(.heartRateVariabilitySDNN),
        HKCategoryType(.sleepAnalysis),
    ] + dailyTotalTypes
    static let dailyTotalTypes: [HKSampleType] = [
        HKQuantityType(.stepCount),
        HKQuantityType(.distanceWalkingRunning),
        HKQuantityType(.flightsClimbed),
    ]
    static let weightType: HKSampleType = HKQuantityType(.bodyMass)

    func read(from start: Date, to end: Date, recovery: Bool, weight: Bool) async throws -> HealthPush {
        var push = HealthPush(exportedAt: HealthPush.timestamp(end))
        let range = HKQuery.predicateForSamples(withStart: start, end: end)
        if recovery {
            push.restingHr = try await samples(.restingHeartRate, .count().unitDivided(by: .minute()), "bpm", range)
            push.hrv = try await samples(.heartRateVariabilitySDNN, .secondUnit(with: .milli), "ms", range)
            push.sleep = try await sleep(range)
            push.steps = try await dailyTotals(.stepCount, .count(), "steps", from: start, to: end)
            push.walkingRunningDistance = try await dailyTotals(.distanceWalkingRunning, .meterUnit(with: .kilo), "km", from: start, to: end)
            push.flightsClimbed = try await dailyTotals(.flightsClimbed, .count(), "flights", from: start, to: end)
        }
        if weight {
            push.weight = try await samples(.bodyMass, .gramUnit(with: .kilo), "kg", range)
        }
        return push
    }

    private func samples(
        _ id: HKQuantityTypeIdentifier, _ unit: HKUnit, _ unitName: String, _ range: NSPredicate
    ) async throws -> [HealthPush.Point] {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: HKQuantityType(id), predicate: range)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        return try await descriptor.result(for: store).map { sample in
            point(sample, value: sample.quantity.doubleValue(for: unit), unit: unitName)
        }
    }

    private func sleep(_ range: NSPredicate) async throws -> [HealthPush.Point] {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.categorySample(type: HKCategoryType(.sleepAnalysis), predicate: range)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        // HealthKit's stage numbers (0 in bed … 5 REM) are the ones the backend stores.
        return try await descriptor.result(for: store).map { point($0, value: Double($0.value), unit: nil) }
    }

    private func dailyTotals(
        _ id: HKQuantityTypeIdentifier, _ unit: HKUnit, _ unitName: String, from start: Date, to end: Date
    ) async throws -> [HealthPush.Point] {
        let calendar = Calendar.current
        let type = HKQuantityType(id)
        let descriptor = HKStatisticsCollectionQueryDescriptor(
            predicate: .quantitySample(type: type, predicate: HKQuery.predicateForSamples(withStart: start, end: end)),
            options: .cumulativeSum,
            anchorDate: calendar.startOfDay(for: end),
            intervalComponents: DateComponents(day: 1)
        )
        return try await descriptor.result(for: store).statistics().compactMap { day in
            guard let sum = day.sumQuantity() else { return nil }
            return HealthPush.Point(
                start: HealthPush.timestamp(day.startDate), end: HealthPush.timestamp(day.endDate),
                value: sum.doubleValue(for: unit), unit: unitName
            )
        }
    }

    private func point(_ sample: HKSample, value: Double, unit: String?) -> HealthPush.Point {
        let revision = sample.sourceRevision
        return HealthPush.Point(
            start: HealthPush.timestamp(sample.startDate),
            end: HealthPush.timestamp(sample.endDate),
            value: value,
            unit: unit,
            source: revision.source.name,
            sourceBundle: revision.source.bundleIdentifier,
            device: revision.productType
        )
    }
}
