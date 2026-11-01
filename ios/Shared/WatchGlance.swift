import Foundation

/// What the Watch widgets show and when each rises in the Smart Stack
/// (docs/design/artboards/WatchWidgets.dc.html). Pure, so it's tested on the phone.
enum WatchGlance {
    enum Kind: String, CaseIterable, Sendable {
        case today, rehab, week, food
    }

    enum TodayState: Equatable, Sendable {
        case planned, done, rest, sick, unknown
    }

    static func state(_ today: WidgetSnapshot.Today?) -> TodayState {
        guard let today else { return .unknown }
        if today.sickDay != nil { return .sick }
        if today.sport == "rest" || today.title == nil { return .rest }
        return today.isDone ? .done : .planned
    }

    /// Smart Stack score (higher is nearer the top). Today leads until the session is done; rehab
    /// still to do rises above it from 18:00; food rises in the evening when under 60 % eaten; on a
    /// rest, sick or finished day the week sits just under Today.
    static func relevance(_ kind: Kind, _ snapshot: WidgetSnapshot, at date: Date, calendar: Calendar = .current) -> Float {
        let today = snapshot.today(on: date)
        let evening = calendar.component(.hour, from: date) >= 18
        switch kind {
        case .today:
            switch state(today) {
            case .planned: return 80
            case .done: return 55
            case .rest, .sick: return 50
            case .unknown: return 0
            }
        case .rehab:
            guard let rehab = today?.rehab else { return 0 }
            if rehab.isDone { return 5 }
            return evening ? 90 : 60
        case .food:
            guard let food = snapshot.food(on: date) else { return 0 }
            return WidgetFormat.isBehind(food, at: date, calendar: calendar) ? 85 : 20
        case .week:
            switch state(today) {
            case .done, .rest, .sick: return 45
            case .planned: return 25
            case .unknown: return 0
            }
        }
    }

    /// Entry dates: now, then each time the clock alone changes a widget (18:00, midnight).
    static func timeline(from date: Date, calendar: Calendar = .current) -> [Date] {
        var dates = [date]
        if let evening = calendar.date(bySettingHour: 18, minute: 0, second: 0, of: date), evening > date {
            dates.append(evening)
        }
        if let midnight = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: date)) {
            dates.append(midnight)
        }
        return dates
    }

    /// "2:47 / 6:10".
    static func week(_ today: WidgetSnapshot.Today) -> String {
        "\(WidgetFormat.clock(today.weekDoneMin)) / \(WidgetFormat.clock(today.weekPlannedMin))"
    }

    /// "5 exercises · Row 34 kg × 10"; the plan's intent for other sports.
    static func detail(_ today: WidgetSnapshot.Today) -> String? {
        if today.sport == "strength", let count = today.liftCount, count > 0 {
            let exercises = count == 1 ? "1 exercise" : "\(count) exercises"
            return [exercises, today.firstLift].compactMap { $0 }.joined(separator: " · ")
        }
        return today.intent
    }

    /// "3 left · ~4 min", or "All done" once every due exercise is ticked.
    static func rehabLine(_ rehab: WidgetSnapshot.Rehab) -> String {
        rehab.isDone ? "All done" : "\(rehab.total - rehab.done) left · ~\(rehab.durationMin) min"
    }

    /// "Workout B · 45 min" for the inline slot above the time.
    static func inline(_ today: WidgetSnapshot.Today?) -> String {
        guard let today else { return "TrainLog" }
        switch state(today) {
        case .sick: return "Sick · day \(today.sickDay ?? 1)"
        case .rest:
            guard let tomorrow = today.tomorrow else { return "Rest day" }
            return "Rest · tmrw " + WidgetFormat.sportLabel(tomorrow.sport)
        case .done:
            guard let tomorrow = today.tomorrow else { return "Done · " + (today.shortTitle ?? "today") }
            return "Done · tmrw " + WidgetFormat.sportLabel(tomorrow.sport)
        case .planned, .unknown:
            let minutes = today.durationMin.map { " · \($0) min" } ?? ""
            return (today.shortTitle ?? WidgetFormat.sportLabel(today.sport)) + minutes
        }
    }
}

extension WidgetSnapshot {
    /// The artboard's numbers: the widget gallery, and the Watch widgets under `-watchDemo YES`.
    static var watchPreview: WidgetSnapshot {
        let date = WidgetSnapshot.iso(.now)
        var today = WidgetSnapshot.Today(
            date: date, title: "Workout B · Back + Core", sport: "strength", durationMin: 45, isDone: false,
            readiness: "green", streakDays: 4, weekDoneMin: 167, weekPlannedMin: 370, weekBySport: []
        )
        today.liftCount = 5
        today.firstLift = "Row 34 kg × 10"
        today.tomorrow = .init(sport: "ride", durationMin: 75)
        today.rehab = .init(title: "Left knee", done: 3, total: 6, durationMin: 4)
        today.week = [
            .init(sport: "ride", status: "done", doneSports: ["ride"]),
            .init(sport: "strength", status: "done", doneSports: ["strength"]),
            .init(sport: "rest", status: "rest", doneSports: []),
            .init(sport: "strength", status: "today", doneSports: []),
            .init(sport: "rest", status: "rest", doneSports: []),
            .init(sport: "ride", status: "upcoming", doneSports: []),
            .init(sport: "run", status: "upcoming", doneSports: []),
        ]
        let food = WidgetSnapshot.Food(date: date, eatenKcal: 1862, targetKcal: 2780, proteinG: 84, proteinTargetG: 140)
        return WidgetSnapshot(today: today, food: food)
    }
}
