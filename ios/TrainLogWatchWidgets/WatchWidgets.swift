import SwiftUI
import WidgetKit

// Smart Stack cards and watch-face complications (docs/design/artboards/WatchWidgets.dc.html).
// They draw the iPhone's widget snapshot, which the phone sends over WatchConnectivity and the
// Watch app stores in its App Group (PhoneLink). No network here: the Watch reaches the server
// only through the phone.

@main
struct TrainLogWatchWidgets: WidgetBundle {
    var body: some Widget {
        WatchTodayWidget()
        WatchRehabWidget()
        WatchWeekWidget()
        WatchFoodWidget()
    }
}

/// One entry now, at 18:00 and at midnight, each scored for the Smart Stack. New data arrives
/// with a reload from the Watch app, so the timeline only has to follow the clock.
struct GlanceProvider: TimelineProvider {
    let kind: WatchGlance.Kind

    func placeholder(in context: Context) -> GlanceEntry {
        GlanceEntry(date: .now, snapshot: .watchPreview, relevance: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (GlanceEntry) -> Void) {
        let stored = WidgetStore.load()
        let snapshot = context.isPreview && stored.today == nil ? .watchPreview : stored
        completion(entry(snapshot, at: .now))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<GlanceEntry>) -> Void) {
        let snapshot = WidgetStore.load()
        let dates = WatchGlance.timeline(from: .now)
        completion(Timeline(entries: dates.map { entry(snapshot, at: $0) }, policy: .atEnd))
    }

    private func entry(_ snapshot: WidgetSnapshot, at date: Date) -> GlanceEntry {
        let score = WatchGlance.relevance(kind, snapshot, at: date)
        return GlanceEntry(date: date, snapshot: snapshot, relevance: TimelineEntryRelevance(score: score))
    }
}

// MARK: - Widgets

struct WatchTodayWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "watch.today", provider: GlanceProvider(kind: .today)) { entry in
            TodayGlance(entry: entry).containerBackground(Color.card, for: .widget)
        }
        .configurationDisplayName("Today")
        .description("Today's session; tap to start it on the Watch.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .accessoryCorner, .accessoryInline])
    }
}

struct WatchRehabWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "watch.rehab", provider: GlanceProvider(kind: .rehab)) { entry in
            RehabGlance(entry: entry).containerBackground(Color.card, for: .widget)
        }
        .configurationDisplayName("Rehab")
        .description("Today's rehab exercises ticked off.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .accessoryCorner])
    }
}

struct WatchWeekWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "watch.week", provider: GlanceProvider(kind: .week)) { entry in
            WeekGlance(entry: entry).containerBackground(Color.card, for: .widget)
        }
        .configurationDisplayName("Week")
        .description("Hours done of planned and the seven days.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .accessoryCorner])
    }
}

struct WatchFoodWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "watch.food", provider: GlanceProvider(kind: .food)) { entry in
            FoodGlance(entry: entry).containerBackground(Color.card, for: .widget)
        }
        .configurationDisplayName("Food")
        .description("Kcal to go and protein.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .accessoryCorner, .accessoryInline])
    }
}
