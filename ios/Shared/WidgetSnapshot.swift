import Foundation
import WidgetKit

/// What the widgets show. The app writes it whenever Today or Food loads; the widget extension
/// reads it from the shared App Group and refreshes it from the server when the Mac is reachable.
struct WidgetSnapshot: Codable, Sendable, Equatable {
    var baseURL: String?
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
            weekBySport: phone.weekMinutes.bySport.map { .init(sport: $0.sport.rawValue, minutes: $0.minutes) }
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
}
