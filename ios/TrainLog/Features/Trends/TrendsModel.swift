import Foundation
import Observation

/// Trends, opened from Activities: the year-so-far charts from the web dashboard and the Apple
/// Health recovery metrics (sleep, HRV, resting HR, steps).
@MainActor
@Observable
final class TrendsModel {
    private(set) var history: TrainingHistory?
    private(set) var health: HealthSummary?
    private(set) var loaded = false
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    /// How many days of health data the charts show.
    var range = 30

    private let client: () -> APIClient

    init(client: @escaping () -> APIClient = { .current }) {
        self.client = client
    }

    static let historyPath = "/metrics/training-history"
    /// Always 90 days, so switching the range doesn't need the network.
    static let healthPath = "/metrics/health-summary?days=90"

    var years: [SportYear] {
        guard let history else { return [] }
        return [
            TrendsFormat.year(.ride, history.rideYearSeries),
            TrendsFormat.year(.run, history.runYearSeries),
            TrendsFormat.year(.strength, history.strengthYearSeries),
        ]
    }

    var metrics: [HealthTrend] {
        guard let metrics = health?.metrics else { return [] }
        return HealthKind.allCases.compactMap { kind in
            let metric: HealthMetric? = switch kind {
            case .sleep: metrics.sleep
            case .hrv: metrics.hrv
            case .restingHr: metrics.restingHr
            case .steps: metrics.steps
            }
            guard let metric, metric.available else { return nil }
            // The export runs mid-morning, so that day's steps are only a few hundred.
            let partialDay = kind == .steps ? health?.lastImport?.exportDate.map { String($0.prefix(10)) } : nil
            return TrendsFormat.trend(kind, metric.history.filter { $0.date != partialDay }, days: range)
        }
    }

    func load() async {
        let api = client()
        if history == nil {
            history = api.cached(Self.historyPath, as: TrainingHistory.self)?.value
            let cachedHealth = api.cached(Self.healthPath, as: HealthSummary.self)
            health = cachedHealth?.value
            syncedAt = cachedHealth?.syncedAt
            loaded = history != nil
        }
        async let historyResult = capture { try await api.get(Self.historyPath, as: TrainingHistory.self) }
        async let healthResult = capture { try await api.get(Self.healthPath, as: HealthSummary.self, timeout: 12) }
        let (h, m) = await (historyResult, healthResult)
        var failure: Error?
        var fromCache = false
        switch h {
        case .success(let loaded): history = loaded.value; fromCache = fromCache || loaded.fromCache
        case .failure(let error): failure = error
        }
        switch m {
        case .success(let loaded):
            health = loaded.value
            syncedAt = loaded.syncedAt
            fromCache = fromCache || loaded.fromCache
        case .failure(let error): failure = failure ?? error
        }
        offline = fromCache || (failure != nil && history != nil)
        error = failure?.localizedDescription
        loaded = true
    }
}

private func capture<T>(_ body: () async throws -> T) async -> Result<T, Error> {
    do { return .success(try await body()) } catch { return .failure(error) }
}

/// One sport's year so far, laid out for the card: 12 month slots, the past ones filled.
struct SportYear: Identifiable, Equatable {
    struct Month: Identifiable, Equatable {
        let index: Int
        let letter: String
        let name: String
        /// km for ride and run, hours for strength.
        let value: Double
        let cumulative: Double
        let hours: Double
        let sessions: Int
        var id: Int { index }
    }

    let sport: Sport
    let caption: String
    let unit: String
    let total: Double
    let months: [Month]
    var id: Sport { sport }

    var title: String {
        switch sport {
        case .ride: "Cycling"
        case .run: "Running"
        default: sport.label
        }
    }

    var best: Month? { months.filter { $0.value > 0 }.max { $0.value < $1.value } }
    var current: Month? { months.last }
    var maxMonthly: Double { months.map(\.value).max() ?? 0 }
}

enum HealthKind: CaseIterable {
    case sleep, hrv, restingHr, steps

    var title: String {
        switch self {
        case .sleep: "Sleep"
        case .hrv: "HRV"
        case .restingHr: "Resting HR"
        case .steps: "Steps"
        }
    }

    var unit: String {
        switch self {
        case .sleep: "h"
        case .hrv: "ms"
        case .restingHr: "bpm"
        case .steps: ""
        }
    }

    /// Whether a rise is good news (lower is better for resting HR).
    var higherIsBetter: Bool { self != .restingHr }
}

/// A health metric over the chosen range, oldest first, with the last week against the weeks before.
struct HealthTrend: Identifiable, Equatable {
    struct Day: Identifiable, Equatable {
        let date: Date
        let value: Double
        var stages: SleepStages?
        var id: Date { date }
    }

    let kind: HealthKind
    let days: [Day]
    let latest: Day?
    /// Mean of the 7 days up to the latest reading.
    let weekAverage: Double?
    /// Mean of the 30 days before that week.
    let baseline: Double?
    var id: HealthKind { kind }

    var delta: Double? {
        guard let weekAverage, let baseline else { return nil }
        return weekAverage - baseline
    }
}

enum TrendsFormat {
    private static let letters = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    static let monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    static func year(_ sport: Sport, _ series: [YearMonth]) -> SportYear {
        let byHours = sport == .strength
        let months = series.prefix(12).enumerated().map { offset, month in
            SportYear.Month(
                index: offset + 1,
                letter: letters[offset],
                name: monthNames[offset],
                value: byHours ? month.monthlyHours : month.monthlyKm ?? 0,
                cumulative: byHours ? month.cumulativeHours : month.cumulativeKm ?? 0,
                hours: month.monthlyHours,
                sessions: month.monthlySessions
            )
        }
        return SportYear(
            sport: sport,
            caption: byHours ? "Hours this year" : "Distance this year",
            unit: byHours ? "h" : "km",
            total: months.last?.cumulative ?? 0,
            months: months
        )
    }

    static func trend(_ kind: HealthKind, _ history: [HealthPoint], days: Int) -> HealthTrend {
        let points = history
            .compactMap { point in FoodFormat.parse(point.date).map { HealthTrend.Day(date: $0, value: point.value, stages: point.stages) } }
            .filter { $0.value > 0 }
            .sorted { $0.date < $1.date }
        guard let latest = points.last else {
            return HealthTrend(kind: kind, days: [], latest: nil, weekAverage: nil, baseline: nil)
        }
        let calendar = Calendar(identifier: .gregorian)
        let ago = { (n: Int) in calendar.date(byAdding: .day, value: -n, to: latest.date) ?? latest.date }
        let week = points.filter { $0.date > ago(7) }
        let before = points.filter { $0.date <= ago(7) && $0.date > ago(37) }
        return HealthTrend(
            kind: kind,
            days: points.filter { $0.date > ago(days) },
            latest: latest,
            weekAverage: mean(week),
            // A baseline needs more than a handful of nights to mean anything.
            baseline: before.count >= 5 ? mean(before) : nil
        )
    }

    private static func mean(_ days: [HealthTrend.Day]) -> Double? {
        days.isEmpty ? nil : days.map(\.value).reduce(0, +) / Double(days.count)
    }

    /// "5,160", "258.1", "130.9": thousands without decimals, smaller totals with one.
    static func total(_ value: Double) -> String {
        if value >= 1000 {
            return value.formatted(.number.precision(.fractionLength(0)).locale(Locale(identifier: "en_US")))
        }
        return value.formatted(ActivityFormat.oneDecimal)
    }

    /// The month's number for the footer: "618 km", "7.5 h".
    static func monthValue(_ value: Double, unit: String) -> String {
        let number = unit == "h"
            ? value.formatted(ActivityFormat.oneDecimal)
            : value.formatted(.number.precision(.fractionLength(0)).locale(Locale(identifier: "en_US")))
        return "\(number) \(unit)"
    }

    /// "6 h 20", "54", "57", "8,412".
    static func health(_ value: Double, _ kind: HealthKind) -> String {
        switch kind {
        case .sleep:
            let minutes = Int((value * 60).rounded())
            return "\(minutes / 60) h \(String(format: "%02d", minutes % 60))"
        case .steps:
            return value.formatted(.number.precision(.fractionLength(0)).locale(Locale(identifier: "en_US")))
        case .hrv, .restingHr:
            return "\(Int(value.rounded()))"
        }
    }

    /// "+4 ms vs 30 d", "−0 h 25 vs 30 d", and whether that is good news.
    static func delta(_ trend: HealthTrend) -> (text: String, good: Bool?)? {
        guard let delta = trend.delta else { return nil }
        let kind = trend.kind
        let sign = delta < 0 ? "−" : "+"
        let size = abs(delta)
        let amount: String = switch kind {
        case .sleep: "\(Int((size * 60).rounded())) min"
        case .steps: health(size, .steps)
        case .hrv, .restingHr: "\(Int(size.rounded())) \(kind.unit)"
        }
        // Inside normal day-to-day noise: say so rather than colour it.
        let flat = switch kind {
        case .sleep: size < 0.25
        case .steps: size < 500
        case .hrv, .restingHr: size < 1.5
        }
        if flat { return ("Steady vs 30 d", nil) }
        return ("\(sign)\(amount) vs 30 d", (delta > 0) == kind.higherIsBetter)
    }

    /// "2026 · day 301 of 365".
    static func dayOfYear(_ date: Date = .now) -> String {
        let calendar = Calendar(identifier: .gregorian)
        let year = calendar.component(.year, from: date)
        let day = calendar.ordinality(of: .day, in: .year, for: date) ?? 0
        let length = calendar.range(of: .day, in: .year, for: date)?.count ?? 365
        return "\(year) · day \(day) of \(length)"
    }
}
