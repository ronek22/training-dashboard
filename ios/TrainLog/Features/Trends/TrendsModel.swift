import Observation
import SwiftUI

/// Trends, opened from Activities: the last 12 weeks by sport, the year so far against last year,
/// and the Apple Health recovery metrics (sleep, HRV, resting HR, steps).
@MainActor
@Observable
final class TrendsModel {
    private(set) var history: TrainingHistory?
    private(set) var trends: TrendsSummary?
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
    static let trendsPath = "/metrics/trends"
    /// Always 90 days, so switching the range doesn't need the network.
    static let healthPath = "/metrics/health-summary?days=90"

    var years: [SportYear] {
        guard let history else { return [] }
        return [
            TrendsFormat.year(.ride, history.rideYearSeries),
            TrendsFormat.year(.strength, history.strengthYearSeries),
            TrendsFormat.year(.run, history.runYearSeries),
        ]
    }

    var weekly: WeeklyVolume? {
        guard let weeks = trends?.weeks, weeks.count >= 2 else { return nil }
        return TrendsFormat.weekly(weeks)
    }

    /// The year card's rows: this year's months from the history, last year from the trends.
    var yearRows: [SportYearRow] {
        let byYear = Dictionary(years.map { ($0.sport, $0) }, uniquingKeysWith: { first, _ in first })
        if let sports = trends?.sports {
            return sports.map { SportYearRow(toDate: $0, year: byYear[$0.sport]) }
        }
        return years.map { SportYearRow(year: $0) }
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
            trends = api.cached(Self.trendsPath, as: TrendsSummary.self)?.value
            let cachedHealth = api.cached(Self.healthPath, as: HealthSummary.self)
            health = cachedHealth?.value
            syncedAt = cachedHealth?.syncedAt
            loaded = history != nil
        }
        async let historyResult = capture { try await api.get(Self.historyPath, as: TrainingHistory.self) }
        async let healthResult = capture { try await api.get(Self.healthPath, as: HealthSummary.self, timeout: 12) }
        async let trendsResult = capture { try await api.get(Self.trendsPath, as: TrendsSummary.self) }
        let (h, m, t) = await (historyResult, healthResult, trendsResult)
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
        // An older server has no /metrics/trends: the page falls back to the year rows alone.
        if case .success(let loaded) = t {
            trends = loaded.value
            fromCache = fromCache || loaded.fromCache
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
    /// The month the footer talks about: this one once it has something, else the one just finished.
    var shown: Month? {
        guard let current else { return nil }
        return current.value > 0 || months.count < 2 ? current : months[months.count - 2]
    }
}

/// The weekly chart's sport groups; the keys match `GET /metrics/trends`.
enum VolumeGroup: String, CaseIterable {
    case ride, strength, run, mobility, other

    var color: Color {
        switch self {
        case .ride: .ride
        case .strength: .strength
        case .run: .run
        case .mobility: .mobility
        case .other: .other
        }
    }

    var label: String {
        switch self {
        case .ride: "Ride"
        case .strength: "Strength"
        case .run: "Run"
        case .mobility: "Rehab · walk"
        case .other: "Hike · other"
        }
    }

    var short: String {
        switch self {
        case .mobility: "Rehab"
        case .other: "Hike"
        default: label
        }
    }
}

/// Hours per week by sport, oldest first; the last week is the one in progress.
struct WeeklyVolume: Equatable {
    struct Week: Identifiable, Equatable {
        let index: Int
        let start: Date
        let hours: [VolumeGroup: Double]
        let sessions: Int
        let top: TrendWeek.Top?
        var id: Int { index }
        var total: Double { hours.values.reduce(0, +) }
        var key: String { FoodFormat.iso(start) }
    }

    let weeks: [Week]
    /// Median of the 8 full weeks before last, so one big trip doesn't move it.
    let typical: Double
    let typicalByGroup: [VolumeGroup: Double]
    /// Top of the bar scale. A lone outlier week is cut at this height so it doesn't flatten the rest.
    let cap: Double

    var thisWeek: Week? { weeks.last }
    var lastWeek: Week? { weeks.count >= 2 ? weeks[weeks.count - 2] : nil }
}

/// One row of the year card: the total so far against the same date last year.
struct SportYearRow: Identifiable, Equatable {
    let sport: Sport
    let unit: String
    let total: Double
    let lastYearToDate: Double?
    let lastYearMonths: [Double]
    let lastDate: Date?
    /// This year's months, for the sparkline and the detail page.
    let year: SportYear?
    var id: Sport { sport }

    init(toDate: SportToDate, year: SportYear?) {
        sport = toDate.sport
        unit = toDate.unit
        total = toDate.total
        lastYearToDate = toDate.lastYearToDate
        lastYearMonths = toDate.lastYearMonths
        lastDate = toDate.lastDate.flatMap(FoodFormat.parse)
        self.year = year
    }

    /// Without the trends route (older server): the history's totals, no comparison.
    init(year: SportYear) {
        sport = year.sport
        unit = year.unit
        total = year.total
        lastYearToDate = nil
        lastYearMonths = []
        lastDate = nil
        self.year = year
    }

    var title: String { year?.title ?? sport.label }
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
    /// The 7-day trailing mean for each day in `days`, drawn as the trend line.
    var average: [Day] = []
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
        let shown = points.filter { $0.date > ago(days) }
        let average = shown.compactMap { day -> HealthTrend.Day? in
            let start = calendar.date(byAdding: .day, value: -7, to: day.date) ?? day.date
            return mean(points.filter { $0.date > start && $0.date <= day.date }).map { HealthTrend.Day(date: day.date, value: $0) }
        }
        return HealthTrend(
            kind: kind,
            days: shown,
            average: average,
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

    static func weekly(_ weeks: [TrendWeek]) -> WeeklyVolume {
        let parsed = weeks.enumerated().compactMap { index, week -> WeeklyVolume.Week? in
            guard let start = FoodFormat.parse(week.start) else { return nil }
            let hours = Dictionary(uniqueKeysWithValues: VolumeGroup.allCases.map { ($0, week.hours[$0.rawValue] ?? 0) })
            return WeeklyVolume.Week(index: index, start: start, hours: hours, sessions: week.sessions, top: week.top)
        }
        // The 8 full weeks before last: last week is what the card compares against them.
        let base = Array(parsed.dropLast(2).suffix(8))
        let typicalByGroup = Dictionary(uniqueKeysWithValues: VolumeGroup.allCases.map { group in
            (group, median(base.map { $0.hours[group] ?? 0 }))
        })
        let totals = parsed.map(\.total).sorted(by: >)
        let highest = totals.first ?? 0
        let second = totals.dropFirst().first ?? 0
        let cap = second > 0 && highest > second * 1.4 ? second * 1.15 : max(highest * 1.05, 1)
        return WeeklyVolume(weeks: parsed, typical: median(base.map(\.total)), typicalByGroup: typicalByGroup, cap: cap)
    }

    static func median(_ values: [Double]) -> Double {
        guard !values.isEmpty else { return 0 }
        let sorted = values.sorted()
        let middle = sorted.count / 2
        return sorted.count.isMultiple(of: 2) ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle]
    }

    /// "6h 32", "45 min", "—" for nothing.
    static func hours(_ value: Double) -> String {
        let minutes = Int((value * 60).rounded())
        if minutes == 0 { return "—" }
        return minutes < 60 ? "\(minutes) min" : "\(minutes / 60)h \(String(format: "%02d", minutes % 60))"
    }

    /// "19 – 25 Oct".
    static func weekRange(_ start: Date) -> String {
        let end = Calendar(identifier: .gregorian).date(byAdding: .day, value: 6, to: start) ?? start
        let day = start.formatted(.dateTime.day().locale(Locale(identifier: "en_GB")))
        return "\(day) – \(end.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB"))))"
    }

    private static let activityWords: [String: (verb: String, noun: String)] = [
        "Hike": ("hiking", "hike"), "Ride": ("riding", "ride"), "VirtualRide": ("riding", "ride"),
        "Run": ("running", "run"), "WeightTraining": ("strength", "session"), "Walk": ("walking", "walk"),
        "Workout": ("rehab", "session"),
    ]

    /// "Mostly hiking · 5 hikes" when one type filled most of the week, else "9 sessions".
    static func weekNote(_ week: WeeklyVolume.Week) -> String {
        if let top = week.top, top.share >= 0.6, let words = activityWords[top.type] {
            return "Mostly \(words.verb) · \(top.sessions) \(words.noun)\(top.sessions == 1 ? "" : "s")"
        }
        switch week.sessions {
        case 0: return "Nothing logged"
        case 1: return "1 session"
        default: return "\(week.sessions) sessions"
        }
    }

    /// The line under the title: the last 4 full weeks against the ones before, then strength.
    static func headline(_ volume: WeeklyVolume) -> String? {
        let full = Array(volume.weeks.dropLast())
        guard full.count >= 8 else { return nil }
        let recent = median(full.suffix(4).map(\.total))
        let before = median(full.dropLast(4).map(\.total))
        guard recent > 0 || before > 0 else { return nil }
        var text: String
        if before > 0, abs(recent - before) / before < 0.15 {
            text = "Last 4 weeks: steady at about \(hours(recent)) a week."
        } else {
            text = "Last 4 weeks: about \(hours(recent)) a week, \(recent < before ? "down" : "up") from \(hours(before)) before."
        }
        let strength = median(full.suffix(4).map { $0.hours[.strength] ?? 0 })
        if strength >= 0.5 {
            text += " Strength holding at about \(hours(strength))."
        }
        return text
    }

    /// "+4,780 km vs 2025" or "2.2× 2025" as a green pill; a drop as a plain note ("355 km by now
    /// in 2025"). Nil when last year has too little to compare with.
    static func comparison(_ row: SportYearRow, year: Int) -> (text: String, pill: Bool)? {
        guard let last = row.lastYearToDate, last > 0, last >= row.total * 0.05 else { return nil }
        if row.total >= last {
            let ratio = row.total / last
            if ratio >= 2 && ratio < 4 { return ("\(ratio.formatted(ActivityFormat.oneDecimal))× \(year)", true) }
            return ("+\(total(row.total - last)) \(row.unit) vs \(year)", true)
        }
        return ("\(total(last)) \(row.unit) by now in \(year)", false)
    }

    /// "Last run 9 Sep" once a sport has gone quiet for three weeks.
    static func idleNote(_ row: SportYearRow, today: Date = .now) -> String? {
        guard let last = row.lastDate,
              let days = Calendar(identifier: .gregorian).dateComponents([.day], from: last, to: today).day, days > 21 else { return nil }
        let word = switch row.sport {
        case .ride: "ride"
        case .run: "run"
        default: "session"
        }
        return "Last \(word) \(last.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB"))))"
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
