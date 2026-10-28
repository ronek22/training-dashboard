import SwiftUI
import WidgetKit

@main
struct TrainLogWidgets: WidgetBundle {
    var body: some Widget {
        TodayWidget()
        WeekWidget()
        FoodWidget()
        StrengthLiveActivity()
    }
}

struct SnapshotEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
}

/// Every widget reads the same snapshot: refreshed from the server every half hour when the Mac is
/// reachable, otherwise the app's last write. A midnight entry blanks yesterday's food and session.
struct SnapshotProvider: TimelineProvider {
    func placeholder(in context: Context) -> SnapshotEntry {
        SnapshotEntry(date: .now, snapshot: .preview)
    }

    func getSnapshot(in context: Context, completion: @escaping (SnapshotEntry) -> Void) {
        let stored = WidgetStore.load()
        let usePreview = context.isPreview && stored.today == nil
        completion(SnapshotEntry(date: .now, snapshot: usePreview ? .preview : stored))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<SnapshotEntry>) -> Void) {
        // WidgetKit calls the completion once from any thread.
        nonisolated(unsafe) let completion = completion
        Task {
            let snapshot = await WidgetRefresh.run()
            let now = Date.now
            let midnight = Calendar.current.date(byAdding: .day, value: 1, to: Calendar.current.startOfDay(for: now)) ?? now
            let entries = [SnapshotEntry(date: now, snapshot: snapshot), SnapshotEntry(date: midnight, snapshot: snapshot)]
            completion(Timeline(entries: entries, policy: .after(min(midnight, now.addingTimeInterval(30 * 60)))))
        }
    }
}

/// Reads today and food straight from the Mac, so the widgets move when a meal or ride is logged
/// elsewhere. Keeps the stored copy when the server can't be reached.
enum WidgetRefresh {
    static func run() async -> WidgetSnapshot {
        guard let base = WidgetStore.load().baseURL else { return WidgetStore.load() }
        let day = WidgetSnapshot.iso(.now)
        async let phone = fetch(PhoneToday.self, base + "/phone/today")
        async let food = fetch(FoodDay.self, base + "/nutrition/food?date=\(day)")
        let (today, eaten) = await (phone, food)
        WidgetStore.update(reloadWidgets: false) { snapshot in
            if let today { snapshot.today = .init(today) }
            if let eaten { snapshot.food = .init(eaten, eaten: eaten.totals) }
        }
        return WidgetStore.load()
    }

    private static func fetch<T: Decodable>(_ type: T.Type, _ address: String) async -> T? {
        guard let url = URL(string: address),
              let (data, response) = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 6)),
              (response as? HTTPURLResponse)?.statusCode == 200
        else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(T.self, from: data)
    }
}

extension WidgetSnapshot {
    /// The artboard's numbers, for the widget gallery.
    static let preview = WidgetSnapshot(
        today: Today(
            date: iso(.now), title: "Workout B", sport: "strength", durationMin: 45, isDone: false,
            readiness: "green", streakDays: 6, weekDoneMin: 167, weekPlannedMin: 370,
            weekBySport: [.init(sport: "strength", minutes: 98), .init(sport: "ride", minutes: 45), .init(sport: "mobility", minutes: 24)]
        ),
        food: Food(date: iso(.now), eatenKcal: 1862, targetKcal: 2780, proteinG: 96, proteinTargetG: 140)
    )
}
