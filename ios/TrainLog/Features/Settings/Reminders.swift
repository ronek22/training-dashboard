import BackgroundTasks
import Foundation
import UIKit
import UserNotifications

/// Local reminders from Settings that only fire when something is left to do: the check-in when
/// today's isn't in, rehab when exercises are still open by evening, dinner when you're well under
/// the calorie target. Nudges are booked one day at a time for the next week; what's known about
/// today (from the server, or from this phone logging it) drops today's nudge or fills in its
/// numbers. An afternoon background refresh re-checks, so something done on the web stays quiet.
enum Reminders {
    static let morningEnabledKey = "reminder.morning.enabled"
    static let morningMinutesKey = "reminder.morning.minutes"
    static let rehabEnabledKey = "reminder.rehab.enabled"
    static let dinnerEnabledKey = "reminder.dinner.enabled"
    static let todayKey = "reminder.today"

    static let defaultMorningMinutes = 7 * 60 + 30
    static let rehabMinutes = 19 * 60
    static let dinnerMinutes = 20 * 60 + 30
    /// Dinner nudges while you've eaten less than this share of the calorie target.
    static let lowCalorieShare = 0.9
    /// Background refresh that re-checks today before the evening nudges (Info.plist lists it).
    static let refreshTaskID = "com.ronek22.trainlog.reminders"
    static let refreshMinutes = 17 * 60 + 30

    private static let prefix = "nudge."
    /// Identifiers from before nudges were conditional, cleared on the next apply.
    private static func isLegacy(_ id: String) -> Bool { id == "morning-checkin" || id.hasPrefix("dinner-") }

    enum Kind: String, Sendable {
        case checkin, rehab, dinner

        /// Where tapping the notification lands (handled by `RootView.onOpenURL`).
        var link: String {
            switch self {
            case .checkin, .rehab: "trainlog://today"
            case .dinner: "trainlog://food"
            }
        }
    }

    /// What's known about one day; nil means not known yet.
    struct Today: Codable, Equatable, Sendable {
        var date: String
        var checkinDone: Bool?
        var rehabLeft: Int?
        var eatenKcal: Double?
        var targetKcal: Double?

        /// Progress only moves forward within a day, so a server answer that hasn't seen this
        /// phone's queued writes yet doesn't bring a dropped nudge back.
        func merged(with server: Today) -> Today {
            guard server.date == date else { return server }
            var result = self
            if let done = server.checkinDone { result.checkinDone = done || checkinDone == true }
            if let left = server.rehabLeft { result.rehabLeft = min(left, rehabLeft ?? left) }
            if let eaten = server.eatenKcal { result.eatenKcal = max(eaten, eatenKcal ?? eaten) }
            if let target = server.targetKcal { result.targetKcal = target }
            return result
        }
    }

    struct Enabled: Equatable, Sendable {
        /// Minutes after midnight when the check-in nudge is on.
        var morning: Int?
        var rehab = false
        var dinner = false

        var any: Bool { morning != nil || rehab || dinner }
    }

    struct Nudge: Equatable, Sendable {
        let kind: Kind
        let day: String
        let date: Date
        let title: String
        let body: String

        var id: String { Reminders.prefix + kind.rawValue + "." + day }
    }

    // MARK: Planning

    /// The nudges to book for the next seven days. Check-in and dinner are booked ahead and dropped
    /// for today once done; rehab only for today, once the server says exercises are open.
    static func plan(_ enabled: Enabled, today: Today?, now: Date, calendar: Calendar = .current) -> [Nudge] {
        let start = calendar.startOfDay(for: now)
        let known = today?.date == FoodFormat.iso(start) ? today : nil
        var nudges: [Nudge] = []
        for offset in 0..<7 {
            guard let day = calendar.date(byAdding: .day, value: offset, to: start) else { continue }
            let iso = FoodFormat.iso(day)
            let isToday = offset == 0
            func at(_ minutes: Int) -> Date? {
                calendar.date(byAdding: .minute, value: minutes, to: day).flatMap { $0 > now ? $0 : nil }
            }

            if let minutes = enabled.morning, let time = at(minutes), !(isToday && known?.checkinDone == true) {
                nudges.append(Nudge(kind: .checkin, day: iso, date: time, title: "Morning check-in",
                                    body: "How did you sleep? Ten seconds to log readiness."))
            }

            if enabled.rehab, isToday, let left = known?.rehabLeft, left > 0, let time = at(rehabMinutes) {
                nudges.append(Nudge(kind: .rehab, day: iso, date: time, title: "Rehab still open",
                                    body: left == 1 ? "One exercise left for today. A few minutes keeps the streak."
                                        : "\(left) exercises left for today. A few minutes keeps the streak."))
            }

            if enabled.dinner, let time = at(dinnerMinutes) {
                if isToday, let eaten = known?.eatenKcal, let target = known?.targetKcal, target > 0 {
                    if eaten < target * lowCalorieShare {
                        nudges.append(Nudge(kind: .dinner, day: iso, date: time, title: "Log dinner",
                                            body: "\(kcal(eaten)) of \(kcal(target)) kcal so far, \(kcal(target - eaten)) to go. Snap dinner so it counts."))
                    }
                } else {
                    nudges.append(Nudge(kind: .dinner, day: iso, date: time, title: "Log dinner",
                                        body: "Still under today's calorie target? Snap dinner so it counts."))
                }
            }
        }
        return nudges
    }

    private static func kcal(_ value: Double) -> String {
        String(Int(value.rounded()))
    }

    // MARK: Booking

    /// Asks once; returns whether alerts are allowed.
    static func requestPermission() async -> Bool {
        let center = UNUserNotificationCenter.current()
        switch await center.notificationSettings().authorizationStatus {
        case .authorized, .provisional, .ephemeral: return true
        case .denied: return false
        default: return (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
        }
    }

    /// Books nudges to match the saved settings and what's known about today.
    static func apply(defaults: UserDefaults = .standard, now: Date = .now) async {
        let center = UNUserNotificationCenter.current()
        let pending = await center.pendingNotificationRequests().map(\.identifier)
        center.removePendingNotificationRequests(withIdentifiers: pending.filter { $0.hasPrefix(prefix) || isLegacy($0) })

        for nudge in plan(enabled(defaults), today: stored(defaults), now: now) {
            let content = UNMutableNotificationContent()
            content.title = nudge.title
            content.body = nudge.body
            content.sound = .default
            content.userInfo = ["link": nudge.kind.link]
            let parts = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: nudge.date)
            let trigger = UNCalendarNotificationTrigger(dateMatching: parts, repeats: false)
            try? await center.add(UNNotificationRequest(identifier: nudge.id, content: content, trigger: trigger))
        }
    }

    /// Asks the server how today is going, then rebooks. Called when the app comes to the front and
    /// from the background refresh; what it can't reach stays as last known.
    static func refresh(_ api: APIClient = .current, defaults: UserDefaults = .standard, now: Date = .now) async {
        if enabled(defaults).any {
            let date = FoodFormat.iso(now)
            async let checkin = try? api.getLive("/checkins/today", as: CheckinResponse.self)
            async let food = try? api.getLive(FoodModel.dayPath(date), as: FoodDay.self)
            async let rehab = rehabLeft(api)
            var server = Today(date: date)
            if let checkin = await checkin { server.checkinDone = checkin.checkin?.date == date }
            if let food = await food, food.date == date {
                server.eatenKcal = food.totals.kcal
                server.targetKcal = food.target?.kcal
            }
            server.rehabLeft = await rehab
            store(current(defaults, now: now).merged(with: server), defaults)
        }
        await apply(defaults: defaults, now: now)
    }

    /// Records something logged on this phone (a check-in, rehab finished, a meal) and rebooks.
    static func note(_ change: (inout Today) -> Void) {
        var today = current(.standard, now: .now)
        let before = today
        change(&today)
        guard today != before else { return }
        store(today, .standard)
        Task { await apply() }
    }

    /// Rehab still due today; a 404 means no active routine.
    private static func rehabLeft(_ api: APIClient) async -> Int? {
        do {
            return try await api.getLive("/guided-sessions/rehab", as: GuidedSessionEnvelope.self).session.exercises.count
        } catch APIError.status(404) {
            return 0
        } catch {
            return nil
        }
    }

    // MARK: Background refresh

    /// Asks iOS for a run in the late afternoon, before the evening nudges.
    static func scheduleRefresh(defaults: UserDefaults = .standard, now: Date = .now, calendar: Calendar = .current) {
        guard enabled(defaults).any else {
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: refreshTaskID)
            return
        }
        let request = BGAppRefreshTaskRequest(identifier: refreshTaskID)
        request.earliestBeginDate = nextRefresh(after: now, calendar: calendar)
        try? BGTaskScheduler.shared.submit(request)
    }

    static func nextRefresh(after now: Date, calendar: Calendar = .current) -> Date? {
        let start = calendar.startOfDay(for: now)
        guard let today = calendar.date(byAdding: .minute, value: refreshMinutes, to: start) else { return nil }
        return today > now ? today : calendar.date(byAdding: .day, value: 1, to: today)
    }

    // MARK: Stored state

    static func enabled(_ defaults: UserDefaults = .standard) -> Enabled {
        Enabled(morning: defaults.bool(forKey: morningEnabledKey) ? morningMinutes(defaults) : nil,
                rehab: defaults.bool(forKey: rehabEnabledKey),
                dinner: defaults.bool(forKey: dinnerEnabledKey))
    }

    private static func stored(_ defaults: UserDefaults) -> Today? {
        defaults.data(forKey: todayKey).flatMap { try? JSONDecoder().decode(Today.self, from: $0) }
    }

    private static func current(_ defaults: UserDefaults, now: Date) -> Today {
        let date = FoodFormat.iso(now)
        return stored(defaults).flatMap { $0.date == date ? $0 : nil } ?? Today(date: date)
    }

    private static func store(_ today: Today, _ defaults: UserDefaults) {
        defaults.set(try? JSONEncoder().encode(today), forKey: todayKey)
    }

    static func morningMinutes(_ defaults: UserDefaults = .standard) -> Int {
        defaults.object(forKey: morningMinutesKey) as? Int ?? defaultMorningMinutes
    }

    static func timeLabel(_ minutes: Int) -> String {
        String(format: "%02d:%02d", minutes / 60, minutes % 60)
    }
}

/// Keeps notifications quiet while the app is in front (the rest timer chimes in-app instead) and
/// opens the tab a nudge is about when it's tapped.
final class NotificationRouter: NSObject, UNUserNotificationCenterDelegate, Sendable {
    static let shared = NotificationRouter()

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let link = (response.notification.request.content.userInfo["link"] as? String).flatMap(URL.init(string:))
        completionHandler()
        guard let link else { return }
        Task { @MainActor in UIApplication.shared.open(link) }
    }
}
