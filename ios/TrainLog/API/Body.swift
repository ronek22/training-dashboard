import Foundation

/// `GET /phone/body` (backend/app/services/phone_body.py).
struct PhoneBody: Decodable, Sendable, Equatable {
    let date: String
    let readiness: Readiness
    var sleep: Sleep?
    let vitals: Vitals
    let load: Load
    var sleepDebt: SleepDebt?
    /// Every session of the last 7 days, any sport (older caches don't have it).
    var training: [TrainingSession]?
    /// Active injuries that protect a body area.
    var issues: [Issue]?

    /// Hours short over the last nights, against the personal need (`needH`).
    struct SleepDebt: Decodable, Sendable, Equatable {
        let hours: Double
        var nights: Int?
        var needH: Double?
        var status: String?
    }

    struct TrainingSession: Decodable, Sendable, Equatable {
        let date: String
        /// strength, ride, run, rehab, mobility, walk, hike or other.
        let sport: String
        var title: String?
        var minutes: Int?
        var exercises: [Exercise]?
    }

    /// A lift and its working sets; the phone maps the name to muscles (MuscleRules).
    struct Exercise: Decodable, Sendable, Equatable {
        let name: String
        let sets: Int
    }

    struct Issue: Decodable, Sendable, Equatable, Identifiable {
        let id: Int
        let title: String
        var side: String?
        var since: String?
        /// Backend body-area keys: knee, heel, hip, lower_back, shoulder, elbow, wrist, neck.
        let areas: [String]
    }

    struct Readiness: Decodable, Sendable, Equatable {
        let level: String
        let label: String
        var advice: String?
        let factors: [Factor]
    }

    /// One signal behind the readiness read; tone is steady, caution or risk.
    struct Factor: Decodable, Sendable, Equatable, Identifiable {
        let key: String
        let label: String
        let detail: String
        let tone: String
        var points: Int?
        var id: String { key }
    }

    /// Last night from the source with stages (the watch). Timestamps are UTC ISO strings.
    struct Sleep: Decodable, Sendable, Equatable {
        let date: String
        let asleepH: Double
        let stages: SleepStages
        let start: String
        let end: String
        var baselineH: Double?
        let segments: [Segment]
    }

    struct Segment: Decodable, Sendable, Equatable {
        /// awake, rem, core, deep or asleep_unspecified.
        let stage: String
        let start: String
        let end: String
    }

    struct Vitals: Decodable, Sendable, Equatable {
        var restingHr: Vital?
        var hrv: Vital?
        var steps: Vital?
        var sleep: Vital?
    }

    /// The latest reading, the mean of the 30 days before it and that month's typical range
    /// (its middle 80%), plus the last 7 days with a reading.
    struct Vital: Decodable, Sendable, Equatable {
        let date: String
        let value: Double
        var baseline: Double?
        var typicalLow: Double?
        var typicalHigh: Double?
        var days: [Day]?
    }

    struct Day: Decodable, Sendable, Equatable {
        let date: String
        let value: Double
    }

    struct Load: Decodable, Sendable, Equatable {
        let fitness: Double
        let fatigue: Double
        let form: Double
        let ratio: Double
        let ratioStatus: String
        /// The last 42 days, oldest first.
        let chart: [LoadDay]
    }

    struct LoadDay: Decodable, Sendable, Equatable {
        let date: String
        let load: Double
        let fitness: Double
        let fatigue: Double
        let form: Double
    }
}
