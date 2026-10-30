import Foundation
import WidgetKit

/// What the widgets show. The app writes it whenever Today or Food loads and from its background
/// runs; the widget extension reads it from the shared App Group and refreshes it from the server
/// when the Mac is reachable.
struct WidgetSnapshot: Codable, Sendable, Equatable {
    /// The address that answered last, then the other one (home ↔ Tailscale).
    var baseURL: String?
    var fallbackURL: String?
    var today: Today?
    var food: Food?

    struct Today: Codable, Sendable, Equatable {
        let date: String
        let title: String?
        let sport: String
        let durationMin: Int?
        let isDone: Bool
        let readiness: String
        let streakDays: Int
        let weekDoneMin: Int
        let weekPlannedMin: Int
        let weekBySport: [SportMinutes]
        // Added with widgets v2; optional so a snapshot stored by an older build still decodes.
        var intent: String? = nil
        var liftCount: Int? = nil
        var sickDay: Int? = nil
        var tomorrow: Tomorrow? = nil
        var week: [Day]? = nil

        /// "Workout C" from "Workout C · Wide Shoulders (extra upper volume)".
        var shortTitle: String? { title.map(WidgetFormat.shortTitle) }
        /// "Strength · Wide Shoulders": the sport, then the title's focus or the plan's intent.
        var kicker: String {
            if let sickDay { return "Sick · day \(sickDay)" }
            if sport == "rest" || title == nil { return "Recovery" }
            let focus = title.flatMap(WidgetFormat.focus) ?? intent
            return [WidgetFormat.sportLabel(sport), focus].compactMap { $0 }.joined(separator: " · ")
        }
    }

    struct Tomorrow: Codable, Sendable, Equatable {
        let sport: String
        let durationMin: Int?
    }

    /// One day of the week strip: done, today, upcoming, missed or skipped.
    struct Day: Codable, Sendable, Equatable {
        let sport: String
        let status: String
        let doneSports: [String]
    }

    struct SportMinutes: Codable, Sendable, Equatable {
        let sport: String
        let minutes: Int
    }

    struct Food: Codable, Sendable, Equatable {
        let date: String
        let eatenKcal: Double
        let targetKcal: Double?
        let proteinG: Double
        let proteinTargetG: Double?

        var kcalToGo: Double? { targetKcal.map { max(0, $0 - eatenKcal) } }
        var share: Double {
            guard let targetKcal, targetKcal > 0 else { return 0 }
            return min(1, eatenKcal / targetKcal)
        }
    }

    /// Where the extension asks, in order.
    var addresses: [String] {
        [baseURL, fallbackURL].compactMap { $0 }.reduce(into: []) { if !$0.contains($1) { $0.append($1) } }
    }

    /// Today and food only count on the day they were read.
    func today(on day: Date) -> Today? { today.flatMap { $0.date == Self.iso(day) ? $0 : nil } }
    func food(on day: Date) -> Food? { food.flatMap { $0.date == Self.iso(day) ? $0 : nil } }

    static func iso(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}

extension WidgetSnapshot.Today {
    init(_ phone: PhoneToday) {
        self.init(
            date: phone.date,
            title: phone.today?.title,
            sport: (phone.today?.sport ?? .rest).rawValue,
            durationMin: phone.today?.durationMin,
            isDone: phone.today?.isDone ?? false,
            readiness: phone.readiness.level,
            streakDays: phone.streakDays,
            weekDoneMin: phone.weekMinutes.done,
            weekPlannedMin: phone.weekMinutes.planned,
            weekBySport: phone.weekMinutes.bySport.map { .init(sport: $0.sport.rawValue, minutes: $0.minutes) },
            intent: phone.today?.intentLabel,
            liftCount: phone.today?.strength?.exercises.count,
            sickDay: phone.sick.map { $0.day ?? 1 },
            tomorrow: phone.tomorrow.map { .init(sport: ($0.sport ?? .other).rawValue, durationMin: $0.durationMin) },
            week: phone.week.map { .init(sport: $0.sport.rawValue, status: $0.status, doneSports: $0.doneSports.map(\.rawValue)) }
        )
    }
}

extension WidgetSnapshot.Food {
    /// `eaten` includes meals still queued on the phone.
    init(_ day: FoodDay, eaten: Macros) {
        self.init(
            date: day.date,
            eatenKcal: eaten.kcal,
            targetKcal: day.target?.kcal,
            proteinG: eaten.proteinG,
            proteinTargetG: day.proteinTargetG
        )
    }
}

/// The snapshot in the App Group's defaults.
enum WidgetStore {
    static let appGroup = "group.com.ronek22.trainlog"
    private static let key = "widgetSnapshot"

    static func load() -> WidgetSnapshot {
        guard let data = UserDefaults(suiteName: appGroup)?.data(forKey: key),
              let snapshot = try? JSONDecoder().decode(WidgetSnapshot.self, from: data)
        else { return WidgetSnapshot() }
        return snapshot
    }

    /// Saves a change and, from the app, reloads the widgets when anything they show moved.
    static func update(reloadWidgets: Bool = true, _ change: (inout WidgetSnapshot) -> Void) {
        let old = load()
        var new = old
        change(&new)
        guard new != old, let data = try? JSONEncoder().encode(new) else { return }
        UserDefaults(suiteName: appGroup)?.set(data, forKey: key)
        if reloadWidgets { WidgetCenter.shared.reloadAllTimelines() }
    }
}

/// Pure formatting for the widgets (unit-tested).
enum WidgetFormat {
    /// "2:47" for 167 minutes done.
    static func clock(_ minutes: Int) -> String {
        String(format: "%d:%02d", minutes / 60, minutes % 60)
    }

    /// "6h10" or "6h" for the week's planned minutes.
    static func hours(_ minutes: Int) -> String {
        minutes % 60 == 0 ? "\(minutes / 60)h" : String(format: "%dh%02d", minutes / 60, minutes % 60)
    }

    /// "45m" or "1h 30m".
    static func duration(_ minutes: Int) -> String {
        let hours = minutes / 60
        let rest = minutes % 60
        if hours == 0 { return "\(rest)m" }
        return rest == 0 ? "\(hours)h" : "\(hours)h \(rest)m"
    }

    static func kcal(_ value: Double) -> String {
        String(Int(value.rounded()))
    }

    static func share(_ done: Int, of planned: Int) -> Double {
        planned > 0 ? min(1, Double(done) / Double(planned)) : 0
    }

    /// The part before " · ", without asides in brackets.
    static func shortTitle(_ title: String) -> String {
        stripAsides(title.components(separatedBy: " · ").first ?? title)
    }

    /// The part after " · ", without asides in brackets; nil when the title has none.
    static func focus(_ title: String) -> String? {
        let parts = title.components(separatedBy: " · ")
        guard parts.count > 1 else { return nil }
        let focus = stripAsides(parts.dropFirst().joined(separator: " · "))
        return focus.isEmpty ? nil : focus
    }

    private static func stripAsides(_ text: String) -> String {
        text.replacingOccurrences(of: #"\s*\([^)]*\)"#, with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespaces)
    }

    static func sportLabel(_ sport: String) -> String {
        switch sport {
        case "mobility": "Mobility"
        case "rest": "Rest"
        default: sport.capitalized
        }
    }

    /// The headline word the app's Today screen uses for each readiness level.
    static func readinessWord(_ level: String) -> String {
        switch level {
        case "green": "Ready"
        case "amber": "Ease in"
        case "red": "Recover"
        default: "No read"
        }
    }

    /// Evening with under 60% eaten: the one time kcal to go turns amber.
    static func isBehind(_ food: WidgetSnapshot.Food, at date: Date, calendar: Calendar = .current) -> Bool {
        guard food.targetKcal != nil, food.share < 0.6 else { return false }
        return calendar.component(.hour, from: date) >= 18
    }
}
