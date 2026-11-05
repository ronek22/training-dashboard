import Foundation

/// `GET /reviews/monthly/report`: one calendar month's signals (weight, lifts, rides, run) beside
/// its time and days. Only the parts the month recap draws.
struct MonthReport: Decodable, Sendable, Equatable {
    let month: String
    let label: String
    let startDate: String
    let endDate: String
    let finished: Bool
    var previousMonth: String?
    var nextMonth: String?
    let totals: Totals
    var priorAverage: Prior?
    var streakDays: Int?
    var plan: PlanDone?
    var days: [Day] = []
    var records: [Record] = []
    var weight: Weight?
    var strength: Strength?
    var rides: Rides?
    var run: Run?
    var wins: [WeekWins.Win] = []
    var focus: WeekWins.Focus?

    struct Totals: Decodable, Sendable, Equatable {
        /// Training minutes; walks are left out, hikes count.
        let minutes: Int
        let sessions: Int
        let activeDays: Int
        let days: Int
        var elapsedDays: Int?
    }

    struct Prior: Decodable, Sendable, Equatable {
        let minutes: Double
        var minutesToDate: Double?
    }

    struct PlanDone: Decodable, Sendable, Equatable {
        let planned: Int
        let done: Int
    }

    struct Day: Decodable, Sendable, Equatable, Identifiable {
        let date: String
        let minutes: Int
        /// cycling, running, strength, hiking, mobility, walking or other; nil on a day off.
        var sport: String?
        var sick: Bool = false
        var record: Bool = false
        var future: Bool = false
        var id: String { date }
    }

    struct Record: Decodable, Sendable, Equatable {
        let date: String
        let name: String
        let display: String
    }

    struct Weight: Decodable, Sendable, Equatable {
        var weighIns: [WeighIn] = []
        let available: Bool
        var status: String?
        var startKg: Double?
        var endKg: Double?
        var changeKg: Double?
        var kgPerWeek: Double?
        var lanePctPerWeek: [Double]?
        var laneKgPerWeek: [Double]?
        var needed: Int?

        struct WeighIn: Decodable, Sendable, Equatable {
            let date: String
            let kg: Double
            let avgKg: Double
        }
    }

    struct Strength: Decodable, Sendable, Equatable {
        let up: Int
        let held: Int
        let down: Int
        var top: [Lift] = []
        var dropped: [Lift] = []
        let liftDays: Int
        var weeks: [LiftWeek] = []
        var perWeekTarget: Int = 3
    }

    struct Lift: Decodable, Sendable, Equatable, Identifiable {
        let name: String
        let e1rmKg: Double
        let previousKg: Double
        let changeKg: Double
        let trend: String
        var id: String { name }
    }

    struct LiftWeek: Decodable, Sendable, Equatable, Identifiable {
        let weekStart: String
        let weekNumber: Int
        let days: Int
        var sick: Bool = false
        var id: String { weekStart }
    }

    struct Rides: Decodable, Sendable, Equatable {
        let rides: Int
        let minutes: Int
        var byIntensity: [String: Int] = [:]
        let previousMinutes: Int
        var previousByIntensity: [String: Int] = [:]
        var hikingMinutes: Int = 0
    }

    struct Run: Decodable, Sendable, Equatable {
        let vdot: Double
        var peak: Double?
        var shareOfPeakPct: Int?
        var projected: Double?
        var runs: Int = 0
        var km: Double = 0
        var previousVdot: Double?
        var lastEstimateDate: String?
    }
}

extension MonthReport.Day {
    // Booleans the server always sends, defaulted so trimmed fixtures still decode.
    private enum CodingKeys: String, CodingKey { case date, minutes, sport, sick, record, future }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        minutes = try c.decodeIfPresent(Int.self, forKey: .minutes) ?? 0
        sport = try c.decodeIfPresent(String.self, forKey: .sport)
        sick = try c.decodeIfPresent(Bool.self, forKey: .sick) ?? false
        record = try c.decodeIfPresent(Bool.self, forKey: .record) ?? false
        future = try c.decodeIfPresent(Bool.self, forKey: .future) ?? false
    }
}
