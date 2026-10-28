import Foundation
import Observation
import UIKit

/// The Plan tab: read this week, page to the weeks around it, move a session to another day.
/// Writing and adjusting plans stays on the Mac.
@MainActor
@Observable
final class PlanModel {
    /// Saved weeks, oldest first.
    private(set) var weeks: [WeeklyPlan] = []
    private(set) var selected: String?
    private(set) var loaded = false
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    private(set) var today = PlanModel.todayISO

    private let client: () -> APIClient
    private var templates: [StrengthTemplateSummary]?

    init(client: @escaping () -> APIClient = { .current }) {
        self.client = client
    }

    /// `-todayDate 2026-10-28` as a launch argument previews another day (DEBUG only), as on Today.
    static var todayISO: String {
        #if DEBUG
        if let day = UserDefaults.standard.string(forKey: "todayDate") { return day }
        #endif
        return FoodFormat.iso(.now)
    }

    var week: WeeklyPlan? { weeks.first { $0.weekStart == selected } }

    private var index: Int? { weeks.firstIndex { $0.weekStart == selected } }
    var hasPrevious: Bool { (index ?? 0) > 0 }
    var hasNext: Bool { index.map { $0 < weeks.count - 1 } ?? false }

    /// True when the newest saved week is already behind us: there's nothing to page forward to.
    var nextWeekMissing: Bool {
        guard let last = weeks.last else { return false }
        return PlanFormat.addingDays(6, to: last.weekStart) <= PlanFormat.addingDays(6, to: PlanFormat.weekStart(of: today))
    }

    func day(_ date: String) -> PlanDay? {
        weeks.lazy.flatMap(\.days).first { $0.date == date }
    }

    static let weeksPath = "/plans/weekly?limit=4"

    func load() async {
        today = Self.todayISO
        if weeks.isEmpty, let cached = client().cached(Self.weeksPath, as: [WeeklyPlan].self) {
            weeks = cached.value.sorted { $0.weekStart < $1.weekStart }
            syncedAt = cached.syncedAt
            selected = PlanFormat.currentWeek(weeks.map(\.weekStart), today: today)
        }
        do {
            // Four covers next week (when it's saved) and a few back; each week is large.
            let result = try await client().get(Self.weeksPath, as: [WeeklyPlan].self)
            weeks = result.value.sorted { $0.weekStart < $1.weekStart }
            syncedAt = result.syncedAt
            offline = result.fromCache
            error = nil
        } catch {
            offline = !weeks.isEmpty
            self.error = error.localizedDescription
        }
        if week == nil {
            selected = PlanFormat.currentWeek(weeks.map(\.weekStart), today: today)
        }
        loaded = true
    }

    func page(_ step: Int) {
        guard let index, weeks.indices.contains(index + step) else { return }
        selected = weeks[index + step].weekStart
    }

    /// Swaps two days on the server, then reloads. Moves aren't queued offline: the server checks
    /// that both days are still free, so it has to answer now. Returns an error to show.
    func move(from: String, to: String) async -> String? {
        let body = try? APIClient.encoder.encode(PlanSwap(fromDate: from, toDate: to))
        do {
            try await client().send("POST", "/plans/weekly/swap", body: body)
        } catch APIError.unreachable {
            return "Can't reach the server. Moves need it online."
        } catch APIError.status(400) {
            return "That day can't change: it's in the past or already has an activity."
        } catch {
            return error.localizedDescription
        }
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        await load()
        return nil
    }

    /// The strength template the planned day names, for Start session.
    func templateId(for day: PlanDay) async -> Int? {
        if templates == nil {
            templates = try? await client().get("/strength/workouts/templates", as: [StrengthTemplateSummary].self).value
        }
        let names = Set([day.templateLabel, day.title].compactMap { $0 })
        return templates?.first { names.contains($0.name) }?.id
    }

    /// Ticks a rehab exercise for the day. Shown straight away; the server accepts today or earlier.
    func tick(_ routine: RehabRoutine, index: Int, done: Bool, on date: String) async {
        update(routine, on: date) { ticked in
            if done { ticked.append(index) } else { ticked.removeAll { $0 == index } }
        }
        let body = try? APIClient.encoder.encode(RehabTick(day: date, index: index, done: done))
        do {
            try await client().send("PUT", "/recovery/issues/\(routine.issueId)/ticks", body: body)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        } catch {
            update(routine, on: date) { ticked in
                if done { ticked.removeAll { $0 == index } } else { ticked.append(index) }
            }
            self.error = error.localizedDescription
        }
    }

    private func update(_ routine: RehabRoutine, on date: String, _ change: (inout [Int]) -> Void) {
        for w in weeks.indices {
            guard let d = weeks[w].days.firstIndex(where: { $0.date == date }),
                  let r = weeks[w].days[d].rehab?.firstIndex(where: { $0.routineId == routine.routineId }) else { continue }
            var days = weeks[w].days
            var rehab = days[d].rehab ?? []
            change(&rehab[r].ticked)
            days[d] = days[d].with(rehab: rehab)
            weeks[w] = WeeklyPlan(weekStart: weeks[w].weekStart, title: weeks[w].title, focus: weeks[w].focus, days: days)
        }
    }
}

private extension PlanDay {
    func with(rehab: [RehabRoutine]) -> PlanDay {
        PlanDay(sessionId: sessionId, date: date, label: label, sessionType: sessionType, workoutIntent: workoutIntent,
                workoutIntentLabel: workoutIntentLabel, templateLabel: templateLabel, title: title, details: details,
                check: check, steps: steps, cues: cues, fallback: fallback, targetDurationMin: targetDurationMin,
                targetDistanceKm: targetDistanceKm, cyclingWorkoutName: cyclingWorkoutName, comparison: comparison,
                rehab: rehab)
    }
}

/// One calendar day of the week: the planned session, or nothing (a rest day).
struct PlanSlot: Identifiable {
    let date: String
    let day: PlanDay?

    var id: String { date }
}

enum PlanDayStatus: Equatable {
    case done, replaced, skipped, missed, planned, rest
}

/// Pure labels and rules for the Plan screens (unit-tested).
enum PlanFormat {
    private static let doneStatuses: Set = ["matched", "linked", "partially_matched", "rest_day_changed"]

    /// Same colour families as the server's `sport_of` (phone_today.py) for planned session types.
    static func sport(_ day: PlanDay) -> Sport {
        let kind = day.sessionType.replacingOccurrences(of: " ", with: "").lowercased()
        switch kind {
        case "ride", "virtualride", "ebikeride", "gravelride", "mountainbikeride": return .ride
        case "run", "trailrun", "virtualrun": return .run
        case "weighttraining", "strength", "crossfit", "workout": return .strength
        case "yoga", "pilates", "mobility", "recovery", "rehab", "stretching": return .mobility
        default: break
        }
        if ["mobility", "recovery", "rehab"].contains(day.workoutIntent?.lowercased() ?? "") { return .mobility }
        switch kind {
        case "walk": return .walk
        case "hike": return .hike
        case "rest": return .rest
        default: return .other
        }
    }

    static func status(_ day: PlanDay?, today: String) -> PlanDayStatus {
        guard let day, sport(day) != .rest else { return .rest }
        let status = day.comparison?.status ?? ""
        if doneStatuses.contains(status) { return .done }
        if status == "replaced" { return .replaced }
        if status == "skipped" { return .skipped }
        return day.date < today ? .missed : .planned
    }

    /// Monday to Sunday, with empty slots for days the plan leaves free.
    static func slots(_ week: WeeklyPlan) -> [PlanSlot] {
        (0..<7).map { offset in
            let date = addingDays(offset, to: week.weekStart)
            return PlanSlot(date: date, day: week.days.first { $0.date == date })
        }
    }

    /// The saved week containing today; else the last one before it; else the first.
    static func currentWeek(_ starts: [String], today: String) -> String? {
        let current = weekStart(of: today)
        return starts.last { $0 <= current } ?? starts.first
    }

    static func weekStart(of iso: String) -> String {
        guard let date = FoodFormat.parse(iso),
              let start = ActivityFormat.mondayCalendar.dateInterval(of: .weekOfYear, for: date)?.start else { return iso }
        return FoodFormat.iso(start)
    }

    static func addingDays(_ days: Int, to iso: String) -> String {
        guard let date = FoodFormat.parse(iso),
              let moved = ActivityFormat.mondayCalendar.date(byAdding: .day, value: days, to: date) else { return iso }
        return FoodFormat.iso(moved)
    }

    /// "Week 44 · Oct 26 – Nov 1".
    static func weekKicker(_ weekStart: String) -> String {
        guard let date = FoodFormat.parse(weekStart) else { return weekStart }
        let number = ActivityFormat.mondayCalendar.component(.weekOfYear, from: date)
        return "Week \(number) · \(ActivityFormat.weekRange(date))"
    }

    /// The headline part of a plan title: "Knee calm-down week" from "Knee calm-down week: upper-body…".
    static func shortTitle(_ title: String?) -> String? {
        guard let title, !title.isEmpty else { return nil }
        return title.split(separator: ":", maxSplits: 1).first.map { String($0).trimmingCharacters(in: .whitespaces) }
    }

    /// "Recovery spin + rehab" from "Recovery spin (knee-gated) + rehab": the brackets go to the meta line.
    static func rowTitle(_ title: String) -> String {
        title.replacingOccurrences(of: #"\s*\([^)]*\)"#, with: "", options: .regularExpression)
    }

    static func doneMinutes(_ day: PlanDay) -> Double {
        (day.comparison?.completedActivities ?? []).reduce(0) { $0 + ($1.durationMin ?? 0) }
    }

    /// The line under a row title.
    static func meta(_ day: PlanDay, today: String) -> String {
        let isToday = day.date == today
        switch status(day, today: today) {
        case .done:
            let minutes = doneMinutes(day)
            let parts = [isToday ? "Today · done" : "Done", minutes > 0 ? ActivityFormat.compactDuration(minutes) : nil]
            return parts.compactMap { $0 }.joined(separator: " · ")
        case .replaced: return "Replaced by another session"
        case .skipped: return "Skipped"
        case .missed: return "Missed · " + plannedMeta(day)
        case .planned: return (isToday ? "Today · " : "") + plannedMeta(day)
        case .rest: return "Rest"
        }
    }

    /// "Easy · 60 min · 28 km".
    static func plannedMeta(_ day: PlanDay) -> String {
        var parts: [String] = []
        if let intent = day.workoutIntentLabel { parts.append(intent) }
        if let minutes = day.targetDurationMin { parts.append("\(minutes) min") }
        if let km = day.targetDistanceKm, km > 0 { parts.append("\(TodayFormat.number(km)) km") }
        return parts.joined(separator: " · ")
    }

    struct Summary: Equatable {
        let done: Int
        let sessions: Int
        let doneMinutes: Int
        let plannedMinutes: Int
        /// Done minutes per sport, largest first, for the progress bar.
        let bySport: [Part]

        struct Part: Equatable {
            let sport: Sport
            let minutes: Int
        }
    }

    static func summary(_ week: WeeklyPlan, today: String) -> Summary {
        let sessions = week.days.filter { sport($0) != .rest }
        var minutes: [Sport: Double] = [:]
        var done = 0
        for day in sessions where status(day, today: today) == .done {
            done += 1
            minutes[sport(day), default: 0] += doneMinutes(day)
        }
        let parts = minutes.map { Summary.Part(sport: $0.key, minutes: Int($0.value.rounded())) }
            .filter { $0.minutes > 0 }
            .sorted { ($0.minutes, $0.sport.rawValue) > ($1.minutes, $1.sport.rawValue) }
        return Summary(
            done: done,
            sessions: sessions.count,
            doneMinutes: parts.reduce(0) { $0 + $1.minutes },
            plannedMinutes: sessions.reduce(0) { $0 + ($1.targetDurationMin ?? 0) },
            bySport: parts
        )
    }

    /// A session can move from a future-or-today day that hasn't been trained yet.
    static func canMove(_ day: PlanDay?, today: String) -> Bool {
        guard let day else { return false }
        return day.date >= today && [.planned].contains(status(day, today: today))
    }

    /// A target day is open when it's today or later and nothing's been done there.
    static func canReceive(_ slot: PlanSlot, today: String) -> Bool {
        guard slot.date >= today else { return false }
        guard let day = slot.day else { return true }
        return ![.done, .replaced].contains(status(day, today: today))
    }

    /// What the move will do, for the sheet's sentence and button.
    static func moveDescription(_ source: PlanDay, to target: PlanSlot) -> (sentence: String, button: String) {
        let from = ActivityFormat.shortDay(source.date)
        let to = ActivityFormat.shortDay(target.date)
        let fromLabel = String(from.prefix(3))
        let toLabel = String(to.prefix(3))
        if let other = target.day, sport(other) != .rest {
            return ("The two days swap: \(rowTitle(other.title)) moves to \(from), \(rowTitle(source.title)) to \(to).",
                    "Swap \(fromLabel) ↔ \(toLabel)")
        }
        return ("\(rowTitle(source.title)) moves to \(to); \(from) becomes a free day.", "Move to \(toLabel)")
    }

    /// The fallback without its own "Short on time:" lead, since the card already says it.
    static func fallback(_ text: String?) -> String? {
        guard let text else { return nil }
        let trimmed = text.replacingOccurrences(of: #"^\s*short on time\s*:\s*"#, with: "", options: [.regularExpression, .caseInsensitive])
        guard let first = trimmed.first else { return nil }
        return first.uppercased() + trimmed.dropFirst()
    }

    /// "Ride · Thu 29 Oct · Recovery".
    static func dayKicker(_ day: PlanDay) -> String {
        [sport(day).label, ActivityFormat.longDay(day.date), day.workoutIntentLabel].compactMap { $0 }.joined(separator: " · ")
    }
}
