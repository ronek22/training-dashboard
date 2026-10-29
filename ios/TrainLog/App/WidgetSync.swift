import BackgroundTasks
import Foundation
import UIKit

/// Keeps the Home and Lock Screen widgets current while the app isn't open: an hourly background
/// refresh, and a run after HealthKit wakes the app with new samples (sleep in the morning moves
/// readiness; a Watch workout ticks off today). Each run reads today and food from the Mac, writes
/// the snapshot and reloads the widgets when anything they show moved.
@MainActor
enum WidgetSync {
    /// Background refresh for the widgets (Info.plist lists it).
    static let refreshTaskID = "com.ronek22.trainlog.widgets"
    static let refreshInterval: TimeInterval = 60 * 60
    /// Every HealthKit observer fires at once on a wake; one read covers them all.
    static let minimumGap: TimeInterval = 10 * 60

    private static var lastRun: Date?

    /// Reads today and food and publishes them. Skipped within `minimumGap` of the last run unless
    /// `force`, and while the server is known to be out of reach.
    static func refresh(_ api: APIClient = .current, force: Bool = false, now: Date = .now) async {
        if !force, let lastRun, now.timeIntervalSince(lastRun) < minimumGap { return }
        guard !api.reachability.knownOffline else { return }
        lastRun = now
        let date = FoodFormat.iso(now)
        async let phone = try? api.getLive(TodayModel.path, as: PhoneToday.self)
        async let food = try? api.getLive(FoodModel.dayPath(date), as: FoodDay.self)
        let (today, day) = await (phone, food)
        guard today != nil || day != nil else { return }
        WidgetStore.update { snapshot in
            snapshot.setAddresses()
            if let today { snapshot.today = .init(today) }
            if let day, day.date == date { snapshot.food = .init(day, eaten: day.totals) }
        }
    }

    /// After a HealthKit wake pushed new samples. In the foreground Today does this itself.
    static func refreshInBackground() async {
        guard UIApplication.shared.applicationState != .active else { return }
        await refresh()
    }

    /// Asks iOS for the next run; it picks the moment (usually when the phone is in use nearby).
    static func scheduleRefresh(now: Date = .now) {
        let request = BGAppRefreshTaskRequest(identifier: refreshTaskID)
        request.earliestBeginDate = now.addingTimeInterval(refreshInterval)
        try? BGTaskScheduler.shared.submit(request)
    }
}

extension WidgetSnapshot {
    /// The address the app talks to now first, so the extension skips a dead `.local` off Wi-Fi.
    mutating func setAddresses(_ route: ServerRoute = .shared) {
        baseURL = route.active
        fallbackURL = route.active == route.home ? route.remote : route.home
    }
}
