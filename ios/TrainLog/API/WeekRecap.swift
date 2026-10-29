import Foundation

/// `GET /reviews/weekly/report`: one Monday–Sunday week against the four weeks before it.
/// Only the parts the recap draws.
struct WeekReport: Decodable, Sendable, Equatable {
    let weekStart: String
    let weekEnd: String
    let finished: Bool
    var previousWeek: String?
    var nextWeek: String?
    let totals: Totals
    var norm: Norm?
    var fitness: Fitness?
    var plan: PlanDone?
    var goals: [Goal] = []
    var recovery: Recovery?
    var sickDays: Int?
    var days: [Day] = []
    var history: [HistoryWeek] = []

    struct Totals: Decodable, Sendable, Equatable {
        /// Training minutes; walks and hikes are left out.
        let minutes: Int
        /// Every minute moved, walks and hikes included.
        var movementMinutes: Int?
        let sessions: Int
        let activeDays: Int
        var distanceKm: Double?
        var elevationM: Double?
        var bySport: [String: SportTotal] = [:]
    }

    struct SportTotal: Decodable, Sendable, Equatable {
        let minutes: Int
        let sessions: Int
    }

    struct Norm: Decodable, Sendable, Equatable {
        var minutes: Double?
        var minutesToDate: Double?
        var sessions: Double?
    }

    struct Fitness: Decodable, Sendable, Equatable {
        var start: Double?
        var end: Double?
    }

    struct PlanDone: Decodable, Sendable, Equatable {
        var title: String?
        let planned: Int
        let done: Int
    }

    struct Goal: Decodable, Sendable, Equatable, Identifiable {
        let id: Int
        let title: String
        let done: Double
        let target: Double
        var anchor: Bool?
        let met: Bool
    }

    struct Recovery: Decodable, Sendable, Equatable {
        var sleep: Vital?
        var hrv: Vital?
        var restingHr: Vital?
        var steps: Vital?
    }

    struct Vital: Decodable, Sendable, Equatable {
        var value: Double?
        var baseline: Double?
    }

    struct Day: Decodable, Sendable, Equatable, Identifiable {
        let date: String
        let future: Bool
        var activities: [Activity] = []
        var sick: Bool?
        var tags: [String]?
        var id: String { date }
    }

    struct Activity: Decodable, Sendable, Equatable {
        let sport: String
        let durationMin: Int
        var distanceKm: Double?
    }

    struct HistoryWeek: Decodable, Sendable, Equatable, Identifiable {
        let weekStart: String
        let current: Bool
        let minutes: Int
        var id: String { weekStart }
    }
}

/// `GET /reviews/weekly/wins`: up to three wins and one thing to focus on next.
struct WeekWins: Decodable, Sendable, Equatable {
    var wins: [Win] = []
    var focus: Focus?

    struct Win: Decodable, Sendable, Equatable {
        let kind: String
        let headline: String
        var detail: String?
    }

    struct Focus: Decodable, Sendable, Equatable {
        let headline: String
        var detail: String?
    }
}
