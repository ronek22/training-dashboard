import Foundation

/// `GET /metrics/training-history`: only the three year-so-far series the dashboard draws.
struct TrainingHistory: Decodable, Sendable, Equatable {
    let rideYearSeries: [YearMonth]
    let runYearSeries: [YearMonth]
    let strengthYearSeries: [YearMonth]
}

/// One month of the current year, January up to this month. Strength has hours only.
struct YearMonth: Decodable, Sendable, Equatable {
    let month: String
    var monthlyKm: Double?
    var monthlyHours: Double
    var monthlySessions: Int
    var cumulativeKm: Double?
    var cumulativeHours: Double
}

/// `GET /metrics/health-summary?days=N`: Apple Health imports. Histories are newest first.
struct HealthSummary: Decodable, Sendable, Equatable {
    let metrics: Metrics
    let lastImport: HealthImport?

    struct Metrics: Decodable, Sendable, Equatable {
        var sleep: HealthMetric?
        var hrv: HealthMetric?
        var restingHr: HealthMetric?
        var steps: HealthMetric?
    }
}

struct HealthMetric: Decodable, Sendable, Equatable {
    let available: Bool
    let history: [HealthPoint]
}

struct HealthPoint: Decodable, Sendable, Equatable {
    let date: String
    let value: Double
    var stages: SleepStages?
}

/// Hours per sleep stage.
struct SleepStages: Decodable, Sendable, Equatable {
    var core: Double?
    var deep: Double?
    var rem: Double?
    var awake: Double?
}

struct HealthImport: Decodable, Sendable, Equatable {
    var exportDate: String?
}

/// `GET /metrics/trends`: 12 weeks of hours by sport (oldest first, ending this week) and the
/// year so far against the same date last year.
struct TrendsSummary: Decodable, Sendable, Equatable {
    let weeks: [TrendWeek]
    let sports: [SportToDate]
}

struct TrendWeek: Decodable, Sendable, Equatable {
    let start: String
    /// Keyed ride, strength, run, mobility, other.
    let hours: [String: Double]
    let sessions: Int
    var top: Top?

    /// The activity type with the most time that week, and its share of the week.
    struct Top: Decodable, Sendable, Equatable {
        let type: String
        let sessions: Int
        let share: Double
    }
}

struct SportToDate: Decodable, Sendable, Equatable {
    let sport: Sport
    /// "km" or "h".
    let unit: String
    let total: Double
    let lastYearToDate: Double
    let lastYearMonths: [Double]
    var lastDate: String?
}
