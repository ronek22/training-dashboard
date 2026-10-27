import Foundation
import UserNotifications

/// Local reminders from Settings. The morning check-in repeats daily; the dinner nudge is booked
/// one day at a time for the next week, so a day whose calorie target is already met can be dropped.
enum Reminders {
    static let morningEnabledKey = "reminder.morning.enabled"
    static let morningMinutesKey = "reminder.morning.minutes"
    static let dinnerEnabledKey = "reminder.dinner.enabled"
    static let dinnerSkippedKey = "reminder.dinner.skipped"

    static let defaultMorningMinutes = 7 * 60 + 30
    static let dinnerMinutes = 20 * 60 + 30

    private static let morningID = "morning-checkin"
    private static let dinnerPrefix = "dinner-"

    /// Asks once; returns whether alerts are allowed.
    static func requestPermission() async -> Bool {
        let center = UNUserNotificationCenter.current()
        switch await center.notificationSettings().authorizationStatus {
        case .authorized, .provisional, .ephemeral: return true
        case .denied: return false
        default: return (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
        }
    }

    /// Books reminders to match the saved settings. Called from Settings and on launch, which also
    /// keeps the dinner week rolling.
    static func apply(defaults: UserDefaults = .standard, now: Date = .now) async {
        let center = UNUserNotificationCenter.current()
        let pending = await center.pendingNotificationRequests().map(\.identifier)
        center.removePendingNotificationRequests(withIdentifiers: pending.filter { $0 == morningID || $0.hasPrefix(dinnerPrefix) })

        if defaults.bool(forKey: morningEnabledKey) {
            let minutes = morningMinutes(defaults)
            let content = UNMutableNotificationContent()
            content.title = "Morning check-in"
            content.body = "How did you sleep? Ten seconds to log readiness."
            content.sound = .default
            let trigger = UNCalendarNotificationTrigger(dateMatching: DateComponents(hour: minutes / 60, minute: minutes % 60), repeats: true)
            try? await center.add(UNNotificationRequest(identifier: morningID, content: content, trigger: trigger))
        }

        if defaults.bool(forKey: dinnerEnabledKey) {
            for date in dinnerDates(from: now, skipping: defaults.string(forKey: dinnerSkippedKey)) {
                let content = UNMutableNotificationContent()
                content.title = "Log dinner"
                content.body = "You're under today's calorie target. Snap dinner so it counts."
                content.sound = .default
                let parts = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: date)
                let trigger = UNCalendarNotificationTrigger(dateMatching: parts, repeats: false)
                try? await center.add(UNNotificationRequest(identifier: dinnerPrefix + FoodFormat.iso(date), content: content, trigger: trigger))
            }
        }
    }

    /// Called when Food sees today's target met: no nudge tonight.
    static func dinnerTargetMet(date: String, defaults: UserDefaults = .standard) {
        guard defaults.string(forKey: dinnerSkippedKey) != date else { return }
        defaults.set(date, forKey: dinnerSkippedKey)
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [dinnerPrefix + date])
    }

    static func morningMinutes(_ defaults: UserDefaults = .standard) -> Int {
        defaults.object(forKey: morningMinutesKey) as? Int ?? defaultMorningMinutes
    }

    /// The next seven 20:30s still ahead of `now`, minus the day whose target was met.
    static func dinnerDates(from now: Date, skipping skipped: String?, calendar: Calendar = .current) -> [Date] {
        let today = calendar.startOfDay(for: now)
        return (0..<7).compactMap { offset -> Date? in
            guard let day = calendar.date(byAdding: .day, value: offset, to: today),
                  let time = calendar.date(byAdding: .minute, value: dinnerMinutes, to: day),
                  time > now, FoodFormat.iso(day) != skipped else { return nil }
            return time
        }
    }

    static func timeLabel(_ minutes: Int) -> String {
        String(format: "%02d:%02d", minutes / 60, minutes % 60)
    }
}
