import Foundation
import SwiftUI

/// The Body map's two layers: readiness (what can I train?) or sets this week (what did I miss?).
enum BodyMapLayer: String, CaseIterable, Sendable {
    case readiness, sets

    var label: String { rawValue.capitalized }
}

/// Pure: this week's hard sets per group against the target, and the one-line nudge that names
/// the planned lift day closing the biggest gap (unit-tested).
struct CoverageSummary: Equatable, Sendable {
    struct Row: Equatable, Sendable {
        enum Hold: Equatable, Sendable { case none, protected, hiking }
        let key: String
        let label: String
        let done: Int
        let planned: Int
        let hold: Hold
    }

    let target: Int
    let rows: [Row]
    /// "Chest 3/8 · Friday and Saturday close it."
    let headline: String
    /// A second line only when no day can be named.
    let detail: String?
    /// Every group that counts reached the target: the headline is a win.
    let isWin: Bool
    /// Logged sets per muscle this week (the Sets layer's colours).
    let muscleSets: [Muscle: Int]

    init(coverage: PhoneBody.Coverage, training: [PhoneBody.TrainingSession], today: String) {
        target = coverage.target
        rows = coverage.groups.map { group in
            let hold: Row.Hold = switch group.status {
            case "protected": .protected
            case "hiking": .hiking
            default: .none
            }
            return Row(key: group.key, label: group.label, done: group.doneSets, planned: group.plannedSets, hold: hold)
        }
        muscleSets = Self.muscleSets(training: training, weekStart: coverage.weekStart, today: today)

        let target = coverage.target
        let open = rows.filter { $0.hold == .none && $0.done < target }
        guard let gap = open.min(by: { ($0.done, $0.planned) < ($1.done, $1.planned) }) else {
            isWin = true
            detail = nil
            headline = rows.contains { $0.hold != .none } ? "Everything else hit \(target). Week covered." : "Every group hit \(target). Week covered."
            return
        }
        isWin = false
        let lead = "\(gap.label) \(gap.done)/\(target)"
        let ahead = coverage.days
            .filter { ($0.state == "planned" || $0.state == "light") && $0.date >= today }
            .sorted { $0.date < $1.date }
        if ahead.isEmpty {
            if coverage.hasPlan {
                headline = "\(lead) · no lift days left this week."
                detail = "Start next week with \(gap.label.lowercased())."
            } else {
                headline = "\(lead) · no lift planned yet."
                detail = "Plan the week on the Mac to see what’s coming."
            }
            return
        }
        detail = nil
        var total = gap.done
        var helping: [String] = []
        for day in ahead {
            let sets = day.groupSets[gap.key] ?? 0
            guard sets > 0 else { continue }
            total += sets
            helping.append(day.date)
            if total >= target { break }
        }
        let names = helping.map { Self.dayName($0, today: today) }
        if helping.isEmpty {
            headline = "\(lead) · no planned lift trains it."
        } else if total < target {
            headline = names.count == 1
                ? "\(lead) · \(names[0])’s lift takes it to \(total)."
                : "\(lead) · the lifts ahead take it to \(total)."
        } else {
            headline = switch names.count {
            case 1: "\(lead) · \(names[0])’s lift can fix it."
            case 2: "\(lead) · \(names[0]) and \(names[1].lowercasedIfRelative) close it."
            default: "\(lead) · the next \(names.count) lifts close it."
            }
        }
    }

    /// "Today", "Tomorrow" or the weekday.
    static func dayName(_ date: String, today: String) -> String {
        switch BodyMapSummary.days(from: today, to: date) {
        case 0: return "Today"
        case 1: return "Tomorrow"
        default:
            let format = Date.ISO8601FormatStyle().year().month().day()
            guard let day = try? Date(String(date.prefix(10)), strategy: format) else { return date }
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = TimeZone(identifier: "UTC")!
            let names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            return names[calendar.component(.weekday, from: day) - 1]
        }
    }

    /// Primary-muscle working sets of lifts logged since Monday.
    static func muscleSets(training: [PhoneBody.TrainingSession], weekStart: String, today: String) -> [Muscle: Int] {
        var sets: [Muscle: Int] = [:]
        for session in training where session.sport == "strength" && session.date >= weekStart && session.date <= today {
            for count in MuscleSummary((session.exercises ?? []).map { ($0.name, $0.sets) }).counts where count.primary > 0 {
                sets[count.muscle, default: 0] += count.primary
            }
        }
        return sets
    }
}

private extension String {
    /// "Tomorrow" mid-sentence reads "tomorrow"; weekdays stay capitalised.
    var lowercasedIfRelative: String { self == "Tomorrow" || self == "Today" ? lowercased() : self }
}

/// Grey at 0 sets, pale pink at 1, full strength pink at the target and above.
enum CoverageRamp {
    static let empty = (r: 0x34, g: 0x3B, b: 0x4A)
    private static let low = (r: 0x5B, g: 0x35, b: 0x50)
    private static let full = (r: 0xFF, g: 0x4D, b: 0x9A)

    /// RGB 0–255 for a set count (tested), so the swatches in the legend match the map.
    static func rgb(_ sets: Int, target: Int = 8) -> (r: Int, g: Int, b: Int) {
        guard sets > 0 else { return empty }
        let t = target > 1 ? Double(min(sets, target) - 1) / Double(target - 1) : 1
        func mix(_ a: Int, _ b: Int) -> Int { Int((Double(a) + (Double(b) - Double(a)) * t).rounded()) }
        return (mix(low.r, full.r), mix(low.g, full.g), mix(low.b, full.b))
    }

    static func color(_ sets: Int, target: Int = 8) -> Color {
        let c = rgb(sets, target: target)
        return Color(red: Double(c.r) / 255, green: Double(c.g) / 255, blue: Double(c.b) / 255)
    }
}
