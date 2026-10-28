import AudioToolbox
import UIKit
import UserNotifications

/// Tells you the rest is over. In the app: ticks for the last three seconds, then a chime and a
/// buzz. With the phone locked or the app in the background: a local notification booked for the
/// rest's end (iOS doesn't show it while the app is in front, so the two never double up).
@MainActor
enum RestAlarm {
    private static let notificationID = "strength-rest-end"
    /// The system alarm chime; `AudioServicesPlayAlertSound` also vibrates, even on silent.
    private static let chime: SystemSoundID = 1005

    static func schedule(at endsAt: Date, next: String?) {
        cancel()
        let delay = endsAt.timeIntervalSinceNow
        guard delay > 1 else { return }
        Task {
            guard await Reminders.requestPermission() else { return }
            let content = UNMutableNotificationContent()
            content.title = "Rest over · go"
            content.body = next ?? "Time for the next set."
            content.sound = .default
            content.interruptionLevel = .timeSensitive
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: delay, repeats: false)
            try? await UNUserNotificationCenter.current().add(
                UNNotificationRequest(identifier: notificationID, content: content, trigger: trigger)
            )
        }
    }

    static func cancel() {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [notificationID])
        center.removeDeliveredNotifications(withIdentifiers: [notificationID])
    }

    /// Called each second of the countdown while the rest strip is on screen.
    static func countdown(_ secondsLeft: Int) {
        switch secondsLeft {
        case 1...3:
            UIImpactFeedbackGenerator(style: .rigid).impactOccurred(intensity: 0.7)
        case 0:
            AudioServicesPlayAlertSound(chime)
            let buzz = UINotificationFeedbackGenerator()
            buzz.notificationOccurred(.warning)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { buzz.notificationOccurred(.success) }
        default:
            break
        }
    }
}
