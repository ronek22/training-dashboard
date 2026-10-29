import Foundation
import Observation
import SwiftUI

/// The Sunday recap: one week's time, sports, days, wins, goals and recovery, plus the focus for
/// next week. Opened from Today (a card on Sunday and Monday, or the week card any day) and from
/// the Sunday evening nudge.
@MainActor
@Observable
final class WeekRecapModel {
    private(set) var report: WeekReport?
    private(set) var wins: WeekWins?
    private(set) var loaded = false
    private(set) var offline = false
    private(set) var syncedAt: Date?
    private(set) var error: String?
    /// Monday of the week shown; nil asks the server for the current week.
    private(set) var weekStart: String?

    private let client: () -> APIClient

    init(weekStart: String? = nil, client: @escaping () -> APIClient = { .current }) {
        self.weekStart = weekStart
        self.client = client
    }

    /// `day` is the phone's date: the container clock is UTC, so late on Sunday it'd still be Saturday there.
    nonisolated static func reportPath(_ weekStart: String?, day: String) -> String {
        "/reviews/weekly/report?" + query(weekStart, day: day)
    }

    nonisolated static func winsPath(_ weekStart: String?, day: String) -> String {
        "/reviews/weekly/wins?" + query(weekStart, day: day)
    }

    private nonisolated static func query(_ weekStart: String?, day: String) -> String {
        (weekStart.map { "week_start=\($0)&" } ?? "") + "day=\(day)"
    }

    func load(now: Date = .now) async {
        let api = client()
        let day = FoodFormat.iso(now)
        let reportPath = Self.reportPath(weekStart, day: day)
        let winsPath = Self.winsPath(weekStart, day: day)
        if report == nil, let cached = api.cached(reportPath, as: WeekReport.self) {
            report = cached.value
            wins = api.cached(winsPath, as: WeekWins.self)?.value
            syncedAt = cached.syncedAt
            loaded = true
        }
        async let reportResult = capture { try await api.get(reportPath, as: WeekReport.self, timeout: 12) }
        async let winsResult = capture { try await api.get(winsPath, as: WeekWins.self) }
        let (r, w) = await (reportResult, winsResult)
        switch r {
        case .success(let loaded):
            report = loaded.value
            syncedAt = loaded.syncedAt
            offline = loaded.fromCache
            error = nil
        case .failure(let failure):
            offline = report != nil
            error = failure.localizedDescription
        }
        if case .success(let loaded) = w { wins = loaded.value }
        loaded = true
    }

    /// Steps to another week (the report's previous or next week).
    func show(_ weekStart: String) async {
        self.weekStart = weekStart
        report = nil
        wins = nil
        loaded = false
        await load()
    }
}

private func capture<T>(_ body: () async throws -> T) async -> Result<T, Error> {
    do { return .success(try await body()) } catch { return .failure(error) }
}

enum RecapFormat {
    /// One sport's share of the week, biggest first.
    struct SportShare: Identifiable, Equatable {
        let sport: Sport
        let label: String
        let minutes: Int
        let sessions: Int
        var id: String { label }
    }

    /// The report's sport keys, mapped to the app's sports.
    static func sport(_ key: String) -> Sport {
        switch key {
        case "cycling": .ride
        case "running": .run
        case "strength": .strength
        case "walking": .walk
        default: .other
        }
    }

    static func sportLabel(_ key: String) -> String {
        switch key {
        case "cycling": "Cycling"
        case "running": "Running"
        case "strength": "Strength"
        case "walking": "Walks & hikes"
        default: "Other"
        }
    }

    static func shares(_ totals: WeekReport.Totals) -> [SportShare] {
        totals.bySport
            .filter { $0.value.minutes > 0 }
            .map { SportShare(sport: sport($0.key), label: sportLabel($0.key), minutes: $0.value.minutes, sessions: $0.value.sessions) }
            .sorted { $0.minutes == $1.minutes ? $0.label < $1.label : $0.minutes > $1.minutes }
    }

    /// Every minute moved, walks and hikes included: a mountain week is a big week.
    static func movedMinutes(_ totals: WeekReport.Totals) -> Int {
        max(totals.movementMinutes ?? 0, totals.minutes)
    }

    /// Every activity in the week, walks and hikes included (the totals count training only).
    static func activityCount(_ report: WeekReport) -> Int {
        report.days.reduce(0) { $0 + $1.activities.count }
    }

    static func distanceKm(_ report: WeekReport) -> Double {
        let walked = report.days.flatMap(\.activities).compactMap(\.distanceKm).reduce(0, +)
        return max(walked, report.totals.distanceKm ?? 0)
    }

    /// How training time compares with a usual week (to the same weekday while the week runs).
    /// Nil without a norm.
    static func versusUsual(_ report: WeekReport) -> Int? {
        let usual = report.finished ? report.norm?.minutes : report.norm?.minutesToDate
        guard let usual, usual >= 1 else { return nil }
        return Int(((Double(report.totals.minutes) - usual) / usual * 100).rounded())
    }

    /// Minutes per sport for one day, in the order they were done, merged by sport.
    static func daySegments(_ day: WeekReport.Day) -> [(sport: Sport, minutes: Int)] {
        var result: [(sport: Sport, minutes: Int)] = []
        for activity in day.activities where activity.durationMin > 0 {
            let sport = sport(activity.sport)
            if let index = result.firstIndex(where: { $0.sport == sport }) {
                result[index].minutes += activity.durationMin
            } else {
                result.append((sport, activity.durationMin))
            }
        }
        return result
    }

    /// "19–25 OCT", or "28 SEP – 4 OCT" across a month.
    static func range(_ start: String, _ end: String) -> String {
        guard let from = FoodFormat.parse(start), let to = FoodFormat.parse(end) else { return start }
        let calendar = Calendar(identifier: .gregorian)
        let month = DateFormatter()
        month.locale = Locale(identifier: "en_US_POSIX")
        month.dateFormat = "MMM"
        let d1 = calendar.component(.day, from: from)
        let d2 = calendar.component(.day, from: to)
        if calendar.component(.month, from: from) == calendar.component(.month, from: to) {
            return "\(d1)–\(d2) \(month.string(from: to))".uppercased()
        }
        return "\(d1) \(month.string(from: from)) – \(d2) \(month.string(from: to))".uppercased()
    }

    static func weekEnd(_ start: String) -> String {
        FoodFormat.parse(start).flatMap { Calendar(identifier: .gregorian).date(byAdding: .day, value: 6, to: $0) }
            .map(FoodFormat.iso) ?? start
    }

    static func weekNumber(_ start: String) -> Int? {
        FoodFormat.parse(start).map { Calendar(identifier: .iso8601).component(.weekOfYear, from: $0) }
    }

    static func dayLetter(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return "" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "EEEEE"
        return formatter.string(from: date)
    }

    /// The week Today offers a recap of: this one on Sunday, last one on Monday, none otherwise.
    static func offer(today iso: String) -> (weekStart: String, label: String)? {
        guard let date = FoodFormat.parse(iso) else { return nil }
        let calendar = Calendar(identifier: .gregorian)
        switch calendar.component(.weekday, from: date) {
        case 1:
            return calendar.date(byAdding: .day, value: -6, to: date).map { (FoodFormat.iso($0), "Your week in review") }
        case 2:
            return calendar.date(byAdding: .day, value: -7, to: date).map { (FoodFormat.iso($0), "Last week in review") }
        default:
            return nil
        }
    }

    static func number(_ value: Double) -> String {
        value.rounded() == value || value >= 100 ? String(Int(value.rounded())) : String(format: "%.1f", value)
    }

    static func winSymbol(_ kind: String) -> String {
        switch kind {
        case "progress": "arrow.up.right"
        case "consistency": "flame.fill"
        case "plan": "checkmark.seal.fill"
        case "goal": "target"
        default: "star.fill"
        }
    }

    /// One recovery number against its own 28-day baseline.
    struct VitalChange: Identifiable, Equatable {
        enum Mood { case better, worse, steady }

        let title: String
        let value: String
        let unit: String
        let change: String
        let mood: Mood
        var id: String { title }
    }

    static func vitals(_ recovery: WeekReport.Recovery?) -> [VitalChange] {
        guard let recovery else { return [] }
        let rows: [(String, WeekReport.Vital?, String, Bool, (Double) -> String)] = [
            ("Sleep", recovery.sleep, "h", true, { String(format: "%.1f", $0) }),
            ("HRV", recovery.hrv, "ms", true, { String(Int($0.rounded())) }),
            ("Resting HR", recovery.restingHr, "bpm", false, { String(Int($0.rounded())) }),
            ("Steps", recovery.steps, "/day", true, { $0 >= 10000 ? String(format: "%.1fk", $0 / 1000) : String(Int($0.rounded())) }),
        ]
        return rows.compactMap { title, vital, unit, higherIsBetter, format in
            guard let value = vital?.value else { return nil }
            guard let base = vital?.baseline, base > 0 else {
                return VitalChange(title: title, value: format(value), unit: unit, change: "no baseline yet", mood: .steady)
            }
            let pct = (value - base) / base * 100
            let mood: VitalChange.Mood = abs(pct) < 3 ? .steady : (pct > 0) == higherIsBetter ? .better : .worse
            let change = abs(pct) < 1 ? "on your usual" : "\(pct > 0 ? "+" : "−")\(Int(abs(pct).rounded()))% vs usual"
            return VitalChange(title: title, value: format(value), unit: unit, change: change, mood: mood)
        }
    }
}
