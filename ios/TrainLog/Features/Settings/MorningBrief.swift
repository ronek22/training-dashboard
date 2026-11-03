import Foundation
import UserNotifications
import os

private let logger = Logger(subsystem: "com.ronek22.trainlog", category: "brief")

/// One push when last night's sleep lands: today's session as the title, the why as the body.
/// It rides on the morning check-in reminder: when it goes out, that day's fixed-time check-in
/// nudge is dropped; when sleep never syncs, the fixed time still fires.
enum MorningBrief {
    static let sentKey = "brief.sent"
    /// Hours when a sleep sync counts as waking up.
    static let window = 4..<11

    struct Message: Equatable, Sendable {
        let title: String
        let body: String
        let link: String
    }

    static func isDue(now: Date, lastSent: String?, calendar: Calendar = .current) -> Bool {
        window.contains(calendar.component(.hour, from: now)) && lastSent != FoodFormat.iso(now)
    }

    static func message(_ today: PhoneToday) -> Message {
        let body = [why(today), today.checkinDone ? nil : "Tap to check in."].compactMap { $0 }.joined(separator: " ")
        return Message(title: title(today), body: body, link: today.checkinDone ? "trainlog://today" : "trainlog://checkin")
    }

    static func title(_ today: PhoneToday) -> String {
        if today.sick != nil { return "Sick mode" }
        guard let session = today.today, session.sport != .rest else { return "Rest day" }
        if session.sport == .mobility, let rehab = today.rehab {
            return "Rehab · \(minutes(rehab.durationMin))"
        }
        let name = session.intentLabel ?? session.title ?? "Today's session"
        return session.durationMin.map { "\(name) · \(minutes($0))" } ?? name
    }

    /// Sleep, then why: the plan's purpose on a good day, the off signals and the short version on
    /// a poor one.
    static func why(_ today: PhoneToday) -> String? {
        let sleep = (today.vitals.ranges?.first { $0.key == "sleep" }?.value ?? today.vitals.sleepH)
            .map { "Slept \(String(format: "%.1f", $0)) h" }
        if today.sick != nil {
            return [sleep.map { $0 + "." }, "Rest and eat well; nothing to train today."].compactMap { $0 }.joined(separator: " ")
        }
        let session = today.today.flatMap { $0.sport == .rest ? nil : $0 }
        let off = offSignals(today.readiness)
        switch today.readiness.level {
        case "red", "amber":
            let red = today.readiness.level == "red"
            let advice = red ? (session == nil ? "so take it easy" : "so keep it short") : "so go easy"
            let lead = off.isEmpty ? "readiness is low" : "\(list(off)) \(off.count == 1 ? "is" : "are") off"
            let first = sleep.map { "\($0), but \(lead), \(advice)." } ?? "\(lead.prefix(1).uppercased())\(lead.dropFirst()), \(advice)."
            let fallback = red ? session?.fallback.map { "Short version: \($0)" } : nil
            return [first, fallback].compactMap { $0 }.joined(separator: " ")
        default:
            let first = sleep.map { "\($0), good to go." } ?? (today.readiness.level == "green" ? "Good to go." : nil)
            return [first, session?.purpose].compactMap { $0 }.joined(separator: " ").nilIfEmpty
        }
    }

    /// Signals pulling readiness down, by the names the readiness card uses.
    static func offSignals(_ readiness: PhoneToday.Readiness) -> [String] {
        let tones: Set<String> = readiness.level == "red" ? ["risk"] : ["risk", "caution"]
        return (readiness.factors ?? []).filter { tones.contains($0.tone) }.map { factor in
            // "Resting HR" reads as "resting HR" mid-sentence; acronyms keep their capitals.
            factor.label.split(separator: " ").map { $0.uppercased() == $0 ? String($0) : $0.lowercased() }.joined(separator: " ")
        }
    }

    private static func list(_ items: [String]) -> String {
        items.count <= 1 ? items.joined() : items.dropLast().joined(separator: ", ") + " and " + (items.last ?? "")
    }

    private static func minutes(_ value: Int) -> String {
        value < 60 ? "\(value) min" : TodayFormat.duration(value)
    }

    // MARK: Sending

    /// Called when HealthKit hands over new sleep. Sends once a day in the morning window, while the
    /// morning check-in reminder is on.
    static func sendAfterSleep(_ api: APIClient = .current, defaults: UserDefaults = .standard, now: Date = .now) async {
        guard Reminders.enabled(defaults).morning != nil,
              isDue(now: now, lastSent: defaults.string(forKey: sentKey)),
              let today = try? await api.getLive(TodayModel.path, as: PhoneToday.self),
              today.date == FoodFormat.iso(now) else { return }
        let message = message(today)
        let content = UNMutableNotificationContent()
        content.title = message.title
        content.body = message.body
        content.sound = .default
        content.userInfo = ["link": message.link]
        do {
            try await UNUserNotificationCenter.current()
                .add(UNNotificationRequest(identifier: "brief." + today.date, content: content, trigger: nil))
        } catch {
            logger.error("Morning brief not sent: \(error)")
            return
        }
        defaults.set(today.date, forKey: sentKey)
        // One morning push: the fixed-time check-in nudge for today goes.
        Reminders.note { $0.briefSent = true }
    }
}
