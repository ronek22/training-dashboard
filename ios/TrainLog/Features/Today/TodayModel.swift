import Foundation
import Observation
import SwiftUI

@MainActor
@Observable
final class TodayModel {
    private(set) var data: PhoneToday?
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    private(set) var loading = false
    /// An open strength workout (started here or on the web), for the Resume banner.
    private(set) var activeWorkout: StrengthSession?
    /// Rehab exercises still due today (ticked and off-day ones left out); nil without a routine.
    private(set) var rehabPending: Int?
    /// Today in Apple Health for the evening day strip; loaded only in the evening.
    private(set) var outside: OutsideDay?
    /// Last month's days for the month-in-review card's strip (first seven days of a month only).
    private(set) var monthStrip: [MonthReport.Day] = []

    private let client: () -> APIClient

    init(client: @escaping () -> APIClient = { .current }) {
        self.client = client
    }

    static var path: String {
        #if DEBUG
        // `-todayDate 2026-10-28` as a launch argument previews another day.
        if let day = UserDefaults.standard.string(forKey: "todayDate") { return "/phone/today?date=\(day)" }
        #endif
        return "/phone/today"
    }

    /// Same request as the month recap, so opening it afterwards is instant from the cache.
    func loadMonthStrip(_ month: String, today: String) async {
        #if DEBUG
        if let demo = MonthRecapDemo.report(month: month) {
            monthStrip = demo.days
            return
        }
        #endif
        let api = client()
        let path = MonthRecapModel.path(month, day: today)
        if monthStrip.isEmpty, let cached = api.cached(path, as: MonthReport.self) {
            monthStrip = cached.value.days
        }
        if let loaded = try? await api.get(path, as: MonthReport.self, timeout: 15) {
            monthStrip = loaded.value.days
        }
    }

    func load() async {
        loading = true
        defer { loading = false }
        let api = client()
        if data == nil, let cached = api.cached(Self.path, as: PhoneToday.self) {
            data = cached.value
            syncedAt = cached.syncedAt
        }
        async let workout = Self.activeWorkout(api)
        async let rehab = Self.rehabPending(api)
        do {
            let loaded = try await api.get(Self.path, as: PhoneToday.self)
            data = Self.eveningDemo(Self.winsDemo(loaded.value))
            syncedAt = loaded.syncedAt
            offline = loaded.fromCache
            error = nil
            let today = WidgetSnapshot.Today(loaded.value)
            WidgetStore.update { $0.setAddresses(); $0.today = today }
        } catch {
            offline = data != nil
            self.error = error.localizedDescription
        }
        let (current, pending) = await (workout, rehab)
        // Leaving the tab cancels the load; a cancelled request isn't "offline", so keep what's shown.
        guard !Task.isCancelled else { return }
        activeWorkout = current
        rehabPending = Self.winsDemoRehab ?? pending
        // A workout finished on the web leaves no open session to end the Live Activity.
        if activeWorkout == nil { StrengthActivity.end() }
    }

    /// Steps, daylight and workouts for the evening strip, straight from Health.
    func loadOutside() async {
        if let demo = Self.eveningDemoOutside() {
            outside = demo
            return
        }
        await OutsideHealth.requestDaylightIfNeeded()
        let day = await OutsideHealth.today()
        guard !Task.isCancelled else { return }
        outside = day
    }

    /// Keeps the Resume banner in step with a workout started, advanced or finished on the web.
    func refreshWorkout() async {
        guard !loading else { return }
        let workout = await Self.activeWorkout(client())
        guard !Task.isCancelled else { return }
        if workout != activeWorkout { activeWorkout = workout }
    }

    #if DEBUG
    /// `-winsDemo midday|rehab|protein|clean` previews the wins for screenshots; nothing is written.
    private static var winsDemoStage: String? { UserDefaults.standard.string(forKey: "winsDemo") }

    static func winsDemo(_ today: PhoneToday) -> PhoneToday {
        guard let stage = winsDemoStage else { return today }
        var today = today
        today.checkinDone = true
        let hit = stage == "protein" || stage == "clean"
        today.protein = PhoneToday.Protein(eatenG: hit ? 132 : 97, targetG: today.protein?.targetG ?? 130, hit: hit)
        if stage == "rehab" || stage == "clean" { today.today?.status = "matched" }
        return today
    }

    static var winsDemoRehab: Int? {
        guard let stage = winsDemoStage else { return nil }
        return stage == "midday" ? 5 : 0
    }

    /// `-eveningDemo done|open|late|rest|sick` previews evening mode at 21:10 (22:55 for late), with
    /// made-up Health data, food and sleep need; nothing is written.
    private static var eveningDemoStage: String? { UserDefaults.standard.string(forKey: "eveningDemo") }

    static var demoNow: Date? {
        guard let stage = eveningDemoStage else { return nil }
        let late = stage == "late"
        return Calendar.current.date(bySettingHour: late ? 22 : 21, minute: late ? 55 : 10, second: 0, of: .now)
    }

    static func eveningDemo(_ today: PhoneToday) -> PhoneToday {
        guard let stage = eveningDemoStage else { return today }
        var today = today
        today.checkinDone = true
        today.protein = PhoneToday.Protein(eatenG: 97, targetG: today.protein?.targetG ?? 130, hit: false)
        today.food = PhoneToday.Food(eatenKcal: stage == "sick" ? 2410 : 1211, targetKcal: 2451)
        if stage == "sick" { today.protein = PhoneToday.Protein(eatenG: 131, targetG: 130, hit: true) }
        today.sleepNeed = today.sleepNeed ?? PhoneToday.SleepNeed(needH: 7.14, debtH: 6)
        switch stage {
        case "done": today.today?.status = "matched"
        case "rest": today.today = nil
        case "sick": today.sick = PhoneToday.Sick(label: "Mild", day: 2)
        default: today.today?.status = "not_completed_yet"
        }
        return today
    }

    static func eveningDemoOutside() -> OutsideDay? {
        guard let stage = eveningDemoStage else { return nil }
        let day = Calendar.current.startOfDay(for: .now)
        let at = { (hour: Double) in day.addingTimeInterval(hour * 3600) }
        let sick = stage == "sick"
        let steps: [Int: Double] = [7: 300, 8: 1800, 9: 400, 10: 200, 11: 350, 12: 2100, 13: 500, 14: 300, 15: 900,
                                    16: 400, 17: 600, 18: 250, 19: 700, 20: 340, 21: 100]
        var outside = OutsideDay()
        outside.steps = steps.keys.sorted().map { LiveDay.Hour(start: at(Double($0)), value: sick ? steps[$0]! / 4 : steps[$0]!) }
        if !sick {
            outside.daylight = [(8 + 5 / 60.0, 15.0), (12 + 20 / 60.0, 25), (15.5, 6)].map {
                OutsideDay.Span(start: at($0.0), end: at($0.0 + $0.1 / 60))
            }
            outside.daylightMinutes = 46
        }
        if stage == "done" {
            outside.workouts = [OutsideDay.Workout(start: at(18 + 10 / 60.0), end: at(18 + 37 / 60.0), sport: .strength)]
        }
        return outside
    }
    #else
    static func winsDemo(_ today: PhoneToday) -> PhoneToday { today }
    static var winsDemoRehab: Int? { nil }
    static var demoNow: Date? { nil }
    static func eveningDemo(_ today: PhoneToday) -> PhoneToday { today }
    static func eveningDemoOutside() -> OutsideDay? { nil }
    #endif

    private static func rehabPending(_ client: APIClient) async -> Int? {
        try? await client.get("/guided-sessions/rehab", as: GuidedSessionEnvelope.self).value.session.exercises.count
    }

    /// The server's open workout; when it's unreachable, the one this phone has in progress.
    static func activeWorkout(_ client: APIClient, store: SessionStore = SessionStore()) async -> StrengthSession? {
        do {
            let live = try await client.getLive("/strength/workouts/sessions/active", as: StrengthSession?.self)
            // A workout finished or deleted on the web while the phone's screen was closed stays on
            // disk as active; drop it once the server confirms it's over, so offline doesn't resurrect it.
            if live == nil, let local = store.load() {
                do {
                    let server = try await client.getLive("/strength/workouts/sessions/\(local.id)", as: StrengthSession.self)
                    if !server.isActive { store.clear() }
                } catch APIError.status(404) {
                    store.clear()
                } catch {}
            }
            return live
        } catch {
            return store.load().flatMap { $0.isActive ? $0 : nil }
        }
    }
}

/// Pure formatting for the Today screen (unit-tested).
enum TodayFormat {
    /// What the session card's volt does.
    enum Next: Equatable {
        case startStrength, openSession, startRehab, allDone
    }

    /// The main part first (the lift, or the ride's steps until the Watch workout syncs), then the
    /// rehab. A rehab-only day goes straight to the rehab. `rehabLeft` is nil on days without rehab.
    static func next(isStrength: Bool, rehabOnly: Bool, mainDone: Bool, rehabLeft: Int?) -> Next {
        let rehabToDo = (rehabLeft ?? 0) > 0
        if rehabOnly { return rehabToDo ? .startRehab : .allDone }
        if !mainDone { return isStrength ? .startStrength : .openSession }
        return rehabToDo ? .startRehab : .allDone
    }

    /// The session card's parts as wins. No session, a rest day or sick mode count as all done, so
    /// the clean day rests on the row alone.
    static func sessionState(_ session: PhoneToday.Session?, hasRehab: Bool, rehabLeft: Int) -> (main: Bool, rehab: Bool, all: Bool) {
        guard let session, session.sport != .rest else { return (false, false, true) }
        let rehabOnly = session.sport == .mobility && hasRehab
        let next = next(isStrength: session.strength != nil, rehabOnly: rehabOnly, mainDone: session.isDone,
                        rehabLeft: hasRehab ? rehabLeft : nil)
        return (!rehabOnly && session.isDone, hasRehab && rehabLeft == 0, next == .allDone)
    }

    static func duration(_ minutes: Int) -> String {
        let hours = minutes / 60
        let rest = minutes % 60
        if hours == 0 { return "\(rest)m" }
        return rest == 0 ? "\(hours)h" : "\(hours)h \(rest)m"
    }

    static func exerciseTarget(_ exercise: PhoneToday.Exercise) -> String {
        if let seconds = exercise.seconds { return "\(exercise.sets) × \(StrengthFormat.hold(seconds))" }
        let reps = exercise.reps.map { "\(exercise.sets) × \($0)" } ?? "\(exercise.sets) sets"
        let load = exercise.weightKg.map { "\(number($0)) kg" } ?? "BW"
        return "\(reps) · \(load)"
    }

    static func number(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(format: "%.1f", value)
    }

    /// "WEDNESDAY · 28 OCTOBER" from "2026-10-28".
    static func dateKicker(_ iso: String) -> String {
        guard let date = parse(iso) else { return iso }
        return date.formatted(.dateTime.weekday(.wide).locale(.en)) + " · " + date.formatted(.dateTime.day().month(.wide).locale(.en))
    }

    /// "Thu 22" for "last done" within the past week, "Thu 17 Sep" before that.
    static func shortDay(_ iso: String, relativeTo today: String) -> String {
        guard let date = parse(iso) else { return iso }
        let recent = parse(today).map { $0.timeIntervalSince(date) < 7 * 86_400 } ?? false
        let day = date.formatted(.dateTime.weekday(.abbreviated).locale(.en)) + " " + date.formatted(.dateTime.day().locale(.en))
        return recent ? day : day + " " + date.formatted(.dateTime.month(.abbreviated).locale(.en))
    }

    static func parse(_ iso: String) -> Date? {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: iso)
    }

    static func readiness(_ level: String) -> (label: String, color: Color) {
        switch level {
        case "green": ("Good to go", .mobility)
        case "amber": ("Go easy", .warning)
        case "red": ("Take it easy", .danger)
        default: ("No read yet", .muted)
        }
    }

    static func painColor(_ pain: Int) -> Color {
        switch pain {
        case ...2: .mobility
        case 3...5: .warning
        default: .danger
        }
    }
}

private extension Locale {
    static let en = Locale(identifier: "en_GB")
}
