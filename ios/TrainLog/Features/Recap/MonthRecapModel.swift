import Foundation
import Observation
import SwiftUI

/// The month in review: is the training working? Time and days as a calendar, the letter's wins,
/// then weight, lifts, rides and run as one card each. Opened from Today on the first seven days
/// of a month (for the month before) and from the week recap's header.
@MainActor
@Observable
final class MonthRecapModel {
    private(set) var report: MonthReport?
    private(set) var loaded = false
    private(set) var offline = false
    private(set) var syncedAt: Date?
    private(set) var error: String?
    /// `YYYY-MM` of the month shown; nil asks the server for the current month.
    private(set) var month: String?

    private let client: () -> APIClient

    init(month: String? = nil, client: @escaping () -> APIClient = { .current }) {
        self.month = month
        self.client = client
    }

    #if DEBUG
    /// A fixed report for screenshots; never reaches the server.
    init(demo report: MonthReport) {
        self.month = report.month
        self.client = { .current }
        self.report = report
        self.loaded = true
    }
    #endif

    /// `day` is the phone's date: the container clock is UTC.
    nonisolated static func path(_ month: String?, day: String) -> String {
        "/reviews/monthly/report?" + (month.map { "month=\($0)&" } ?? "") + "day=\(day)"
    }

    func load(now: Date = .now) async {
        #if DEBUG
        if MonthRecapDemo.isOn { return }
        #endif
        let api = client()
        let path = Self.path(month, day: FoodFormat.iso(now))
        if report == nil, let cached = api.cached(path, as: MonthReport.self) {
            report = cached.value
            syncedAt = cached.syncedAt
            loaded = true
        }
        do {
            let result = try await api.get(path, as: MonthReport.self, timeout: 15)
            report = result.value
            syncedAt = result.syncedAt
            offline = result.fromCache
            error = nil
        } catch {
            offline = report != nil
            self.error = error.localizedDescription
        }
        loaded = true
    }

    /// Steps to another month (the report's previous or next).
    func show(_ month: String) async {
        self.month = month
        report = nil
        loaded = false
        await load()
    }
}

enum MonthRecapFormat {
    /// The month Today offers on its first seven days: the one that just ended.
    static func offer(today iso: String) -> (month: String, label: String)? {
        guard let date = FoodFormat.parse(iso) else { return nil }
        let calendar = Calendar(identifier: .gregorian)
        guard calendar.component(.day, from: date) <= 7,
              let previous = calendar.date(byAdding: .month, value: -1, to: date) else { return nil }
        return (monthKey(previous), "\(monthName(previous)) in review")
    }

    /// "1–31 OCT" for a `YYYY-MM`.
    static func offerRange(_ month: String) -> String {
        guard let start = FoodFormat.parse(month + "-01"),
              let days = Calendar(identifier: .gregorian).range(of: .day, in: .month, for: start)?.count else { return month }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM"
        return "1–\(days) \(formatter.string(from: start))".uppercased()
    }

    /// The month a week belongs to (its Thursday decides, as ISO weeks do).
    static func month(ofWeek weekStart: String) -> String? {
        FoodFormat.parse(weekStart).flatMap { Calendar(identifier: .gregorian).date(byAdding: .day, value: 3, to: $0) }.map(monthKey)
    }

    static func monthKey(_ date: Date) -> String {
        let c = Calendar(identifier: .gregorian).dateComponents([.year, .month], from: date)
        return String(format: "%04d-%02d", c.year ?? 0, c.month ?? 0)
    }

    static func monthName(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMMM"
        return formatter.string(from: date)
    }

    /// "1–31 OCT".
    static func range(_ report: MonthReport) -> String {
        guard let end = FoodFormat.parse(report.endDate) else { return report.label }
        let day = Calendar(identifier: .gregorian).component(.day, from: end)
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM"
        return "1–\(day) \(formatter.string(from: end))".uppercased()
    }

    static func name(_ report: MonthReport) -> String {
        FoodFormat.parse(report.startDate).map(monthName) ?? report.label
    }

    /// Blank cells before the 1st in a Monday-first grid.
    static func leadingBlanks(_ report: MonthReport) -> Int {
        guard let start = FoodFormat.parse(report.startDate) else { return 0 }
        return (Calendar(identifier: .gregorian).component(.weekday, from: start) + 5) % 7
    }

    /// The calendar's sport colours.
    static func sport(_ key: String?) -> Sport? {
        switch key {
        case "cycling": .ride
        case "running": .run
        case "strength": .strength
        case "hiking": .hike
        case "mobility", "walking": .mobility
        case nil: nil
        default: .other
        }
    }

    /// Cell brightness by time: short days are faint, an hour or more is full colour.
    static func intensity(_ minutes: Int) -> Double {
        minutes < 30 ? 0.38 : minutes < 60 ? 0.62 : 1
    }

    /// Training against the usual (three months before; to the same day while the month runs).
    static func versusUsual(_ report: MonthReport) -> (usual: Double, pct: Int)? {
        let usual = report.finished ? report.priorAverage?.minutes : report.priorAverage?.minutesToDate
        guard let usual, usual >= 1 else { return nil }
        return (usual, Int(((Double(report.totals.minutes) - usual) / usual * 100).rounded()))
    }

    // MARK: Weight

    enum WeightMood: Equatable { case gaining, fast, flat, losing }

    static func weightMood(_ status: String?) -> WeightMood {
        switch status {
        case "gentle_gain": .gaining
        case "fast_gain": .fast
        case "losing": .losing
        default: .flat
        }
    }

    /// One plain line under the weight chart; the under-eating goal means a fast gain is never scolded.
    static func weightLine(_ weight: MonthReport.Weight) -> (lead: String, rest: String) {
        let rate = String(format: "%.2f", abs(weight.kgPerWeek ?? 0))
        let lane = (weight.laneKgPerWeek ?? []).map { String(format: "%.2f", $0) }.joined(separator: "–")
        switch weightMood(weight.status) {
        case .gaining: return ("Lean gain.", "\(rate) kg a week, inside the lane (\(lane)).")
        case .fast: return ("Gaining.", "\(rate) kg a week, just over the lane (\(lane)). Keep eating; one month is noisy.")
        case .flat: return ("Holding.", "\(rate) kg a week; the lane is \(lane). Room for a bit more food.")
        case .losing: return ("Losing.", "\(rate) kg a week down; muscle needs the lane (\(lane)). Eat more.")
        }
    }

    static func signed(_ value: Double, digits: Int = 1) -> String {
        let text = String(format: "%.\(digits)f", abs(value))
        return value >= 0 ? "+\(text)" : "−\(text)"
    }

    // MARK: Lifts

    /// Exercise names shortened for one row ("Standing Dumbbell Shoulder Press" → "Shoulder press").
    static func liftName(_ name: String) -> String {
        var words = name.split(separator: " ").map(String.init)
        words.removeAll { ["Standing", "Seated", "Bent", "Over"].contains($0) }
        if words.count > 2 { words.removeAll { ["Dumbbell", "Barbell"].contains($0) } }
        if words.isEmpty { return name }
        let joined = words.joined(separator: " ")
        return joined.prefix(1).uppercased() + joined.dropFirst().lowercased()
    }

    /// "Incline bench press −9.5, Back squat −3.0 kg".
    static func droppedLine(_ lifts: [MonthReport.Lift]) -> String {
        lifts.prefix(4).map { "\(liftName($0.name)) \(signed($0.changeKg))" }.joined(separator: ", ") + " kg"
    }

    // MARK: Verdict chips

    struct Verdict: Identifiable, Equatable {
        enum Direction { case up, down, flat }
        let id: String
        let title: String
        let word: String
        let direction: Direction
        let sport: Sport
    }

    /// One word per signal, never the numbers (the cards below carry those). Only for a finished
    /// month: a few days against a whole month would call everything softer.
    static func verdicts(_ report: MonthReport) -> [Verdict] {
        guard report.finished else { return [] }
        var result: [Verdict] = []
        if let weight = report.weight, weight.available {
            let (word, direction): (String, Verdict.Direction) = switch weightMood(weight.status) {
            case .gaining, .fast: ("Gaining", .up)
            case .flat: ("Holding", .flat)
            case .losing: ("Losing", .down)
            }
            result.append(Verdict(id: "body", title: "Body", word: word, direction: direction, sport: .mobility))
        }
        if let strength = report.strength, strength.up + strength.held + strength.down > 0 {
            let (word, direction): (String, Verdict.Direction) = strength.up > strength.down ? ("Stronger", .up)
                : strength.down > strength.up ? ("Softer", .down) : ("Holding", .flat)
            result.append(Verdict(id: "lifts", title: "Lifts", word: word, direction: direction, sport: .strength))
        }
        if let rides = report.rides, rides.minutes > 0 || rides.previousMinutes > 0 {
            let ratio = Double(rides.minutes) / Double(max(rides.previousMinutes, 1))
            let (word, direction): (String, Verdict.Direction) = rides.previousMinutes == 0 ? ("Building", .up)
                : ratio >= 1.1 ? ("Building", .up) : ratio <= 0.9 ? ("Lighter", .down) : ("Steady", .flat)
            result.append(Verdict(id: "base", title: "Base", word: word, direction: direction, sport: .ride))
        }
        if let run = report.run {
            let (word, direction): (String, Verdict.Direction) = run.runs == 0 ? ("Paused", .flat)
                : (run.vdot - (run.previousVdot ?? run.vdot)) >= 0.5 ? ("Rising", .up)
                : (run.vdot - (run.previousVdot ?? run.vdot)) <= -0.5 ? ("Slipping", .down) : ("Steady", .flat)
            result.append(Verdict(id: "run", title: "Run", word: word, direction: direction, sport: .run))
        }
        return result
    }

    // MARK: Rides

    static let intensities: [(key: String, label: String)] = [
        ("recovery", "Recovery"), ("z2", "Endurance"), ("sweet_spot", "Sweet spot"), ("vo2", "VO2"),
    ]

    static func hours(_ minutes: Int) -> String {
        String(format: "%.1f", Double(minutes) / 60)
    }

    // MARK: Run

    static func vdotChange(_ run: MonthReport.Run) -> Double? {
        guard run.runs > 0, let previous = run.previousVdot else { return nil }
        return run.vdot - previous
    }

    /// The line under the VDOT track.
    static func runLine(_ run: MonthReport.Run, month: String) -> String {
        guard run.runs > 0 else {
            var line = "No runs in \(month)."
            if let date = run.lastEstimateDate { line += " Last estimate \(shortDate(date))." }
            if let projected = run.projected, projected > run.vdot { line += " One easy run a week brings it back toward \(Int(projected.rounded()))." }
            return line
        }
        let km = run.km >= 10 ? "\(Int(run.km.rounded())) km" : String(format: "%.1f km", run.km)
        return "\(run.runs) \(run.runs == 1 ? "run" : "runs"), \(km) in \(month)."
    }

    /// "9 Sep".
    static func shortDate(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return iso }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "d MMM"
        return formatter.string(from: date)
    }
}
