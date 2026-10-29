import Foundation

/// `GET /phone/body` (backend/app/services/phone_body.py).
struct PhoneBody: Decodable, Sendable, Equatable {
    let date: String
    let readiness: Readiness
    var sleep: Sleep?
    let vitals: Vitals
    let load: Load

    struct Readiness: Decodable, Sendable, Equatable {
        let level: String
        let label: String
        var advice: String?
        var points: Int?
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
    }

    /// The latest reading and the mean of the 30 days before it.
    struct Vital: Decodable, Sendable, Equatable {
        let date: String
        let value: Double
        var baseline: Double?
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
