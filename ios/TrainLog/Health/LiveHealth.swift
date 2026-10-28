import Foundation
import HealthKit

/// Today's steps and heart rate hour by hour, read straight from Apple Health for the Body screen.
/// Nothing here goes to the Mac; the backend only keeps daily totals.
struct LiveDay: Sendable, Equatable {
    struct Hour: Sendable, Equatable, Identifiable {
        let start: Date
        let value: Double
        var id: Date { start }
    }

    struct HeartHour: Sendable, Equatable, Identifiable {
        let start: Date
        let low: Double
        let high: Double
        var id: Date { start }
    }

    var steps: [Hour] = []
    var heart: [HeartHour] = []
    var latestHeartRate: Double?
    var latestHeartRateAt: Date?

    var stepTotal: Double { steps.map(\.value).reduce(0, +) }
    var isEmpty: Bool { steps.isEmpty && heart.isEmpty }
}

enum LiveHealth {
    /// Read but never observed in the background: heart rate arrives every few minutes.
    static let types: [HKSampleType] = [HKQuantityType(.heartRate)]

    private static let store = HKHealthStore()

    /// Nil when Health isn't on this device or nothing could be read (simulator, access denied).
    static func today(now: Date = .now) async -> LiveDay? {
        guard HealthSync.isAvailable else { return nil }
        let calendar = Calendar.current
        let start = calendar.startOfDay(for: now)
        var day = LiveDay()
        if let steps = try? await hourly(.stepCount, options: .cumulativeSum, from: start, to: now) {
            day.steps = steps.compactMap { stats in
                stats.sumQuantity().map { LiveDay.Hour(start: stats.startDate, value: $0.doubleValue(for: .count())) }
            }
        }
        let bpm = HKUnit.count().unitDivided(by: .minute())
        if let heart = try? await hourly(.heartRate, options: [.discreteMin, .discreteMax, .mostRecent], from: start, to: now) {
            day.heart = heart.compactMap { stats in
                guard let low = stats.minimumQuantity(), let high = stats.maximumQuantity() else { return nil }
                return LiveDay.HeartHour(start: stats.startDate, low: low.doubleValue(for: bpm), high: high.doubleValue(for: bpm))
            }
            if let last = heart.last(where: { $0.mostRecentQuantity() != nil }) {
                day.latestHeartRate = last.mostRecentQuantity()?.doubleValue(for: bpm)
                day.latestHeartRateAt = last.mostRecentQuantityDateInterval()?.end
            }
        }
        return day.isEmpty ? nil : day
    }

    private static func hourly(
        _ id: HKQuantityTypeIdentifier, options: HKStatisticsOptions, from start: Date, to end: Date
    ) async throws -> [HKStatistics] {
        let descriptor = HKStatisticsCollectionQueryDescriptor(
            predicate: .quantitySample(type: HKQuantityType(id), predicate: HKQuery.predicateForSamples(withStart: start, end: end)),
            options: options,
            anchorDate: start,
            intervalComponents: DateComponents(hour: 1)
        )
        return try await descriptor.result(for: store).statistics()
    }
}
