import Foundation

/// Body of `POST /integrations/health-data/push`: the Shortcut payload format the backend already
/// imports (docs/apple-health-shortcut.md), plus the HealthKit source bundle so a night's sleep
/// stays one source. Sleep values are HealthKit's raw stage numbers; steps, distance and flights
/// are one total per local day.
struct HealthPush: Encodable, Sendable, Equatable {
    struct Point: Encodable, Sendable, Equatable {
        let start: String
        var end: String?
        let value: Double
        var unit: String?
        var source: String?
        var sourceBundle: String?
        var device: String?
    }

    let exportedAt: String
    var restingHr: [Point] = []
    var hrv: [Point] = []
    var weight: [Point] = []
    var sleep: [Point] = []
    var steps: [Point] = []
    var walkingRunningDistance: [Point] = []
    var flightsClimbed: [Point] = []

    var sampleCount: Int {
        restingHr.count + hrv.count + weight.count + sleep.count + steps.count + walkingRunningDistance.count + flightsClimbed.count
    }

    /// Local time with its offset ("2026-10-28T07:12:03+01:00"): the backend takes a daily total's
    /// calendar day from the date as written, so it must not be shifted to UTC.
    static func timestamp(_ date: Date, in timeZone: TimeZone = .current) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = timeZone
        return formatter.string(from: date)
    }

    /// How far back a sync reads. Every push re-sends a rolling week, so a missed one is filled in
    /// by the next; after a long gap (phone away from the Mac) it reaches back to a day before the
    /// last good push, up to 30 days.
    static func windowStart(now: Date, lastSuccess: Date?, calendar: Calendar = .current) -> Date {
        let week = calendar.date(byAdding: .day, value: -7, to: calendar.startOfDay(for: now))!
        let limit = calendar.date(byAdding: .day, value: -30, to: calendar.startOfDay(for: now))!
        guard let lastSuccess else { return limit }
        let sinceLast = calendar.date(byAdding: .day, value: -1, to: calendar.startOfDay(for: lastSuccess))!
        return max(limit, min(week, sinceLast))
    }
}

/// What `POST /integrations/health-data/push` answers.
struct HealthPushResult: Decodable, Sendable {
    let samplesSeen: Int
    let samplesInserted: Int
}
