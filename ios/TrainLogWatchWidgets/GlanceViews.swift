import SwiftUI
import WidgetKit

// The Watch widgets' views (docs/design/artboards/WatchWidgets.dc.html). Also compiled into the
// Watch app for its `-watchDemoStage widgets` screen.

struct GlanceEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
    let relevance: TimelineEntryRelevance?

    var today: WidgetSnapshot.Today? { snapshot.today(on: date) }
    var food: WidgetSnapshot.Food? { snapshot.food(on: date) }
}

// MARK: - Today

struct TodayGlance: View {
    let entry: GlanceEntry
    @Environment(\.widgetFamily) private var widgetFamily
    /// Set by the Watch app's demo stage, which has no widget environment.
    var forced: WidgetFamily?
    private var family: WidgetFamily { forced ?? widgetFamily }

    private var today: WidgetSnapshot.Today? { entry.today }
    private var state: WatchGlance.TodayState { WatchGlance.state(today) }
    private var color: Color { Glyph.color(today?.sport ?? "other") }

    var body: some View {
        switch family {
        case .accessoryCircular: circular
        case .accessoryCorner: corner
        case .accessoryInline:
            Label(WatchGlance.inline(today), systemImage: state == .done ? "checkmark" : Glyph.symbol(today?.sport ?? "other"))
        default: rectangular
        }
    }

    @ViewBuilder private var rectangular: some View {
        VStack(alignment: .leading, spacing: 3) {
            switch state {
            case .planned:
                GlanceKicker(today?.kicker ?? "", symbol: Glyph.symbol(today?.sport ?? "other"), color: color,
                             trailing: today?.durationMin.map { "\($0) MIN" }, trailingColor: .time)
                GlanceTitle(today?.shortTitle ?? "")
                if let detail = today.flatMap(WatchGlance.detail) { GlanceLine(detail) }
            case .done:
                GlanceKicker("Done", symbol: "checkmark", color: .volt,
                             trailing: today?.durationMin.map { "\($0) MIN" }, trailingColor: .volt)
                GlanceTitle(today?.shortTitle ?? "")
                TomorrowLine(tomorrow: today?.tomorrow)
            case .rest:
                GlanceKicker("Rest day", symbol: "moon.fill", color: .muted)
                GlanceTitle("Recover")
                TomorrowLine(tomorrow: today?.tomorrow)
            case .sick:
                GlanceKicker("Sick · day \(today?.sickDay ?? 1)", symbol: "thermometer.medium", color: .muted)
                GlanceTitle("Take it easy")
                GlanceLine("Plan paused · walks only")
            case .unknown:
                GlanceKicker("Today", symbol: "figure.strengthtraining.traditional", color: .muted)
                GlanceLine("Open TrainLog on your iPhone")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder private var circular: some View {
        switch state {
        case .planned:
            VStack(spacing: 1) {
                Image(systemName: Glyph.symbol(today?.sport ?? "other")).font(.system(size: 15, weight: .semibold)).foregroundStyle(color)
                Text(today?.durationMin.map(WidgetFormat.duration) ?? "—").font(WatchFont.number(16)).foregroundStyle(Color.time)
            }
            .widgetAccentable()
        case .done:
            ZStack {
                Circle().stroke(Color.volt, lineWidth: 3.5).padding(2)
                VStack(spacing: 0) {
                    Image(systemName: "checkmark").font(.system(size: 16, weight: .bold))
                    Text("DONE").font(WatchFont.body(7, weight: .bold))
                }
                .foregroundStyle(Color.volt)
            }
            .widgetAccentable()
        case .rest, .sick, .unknown:
            VStack(spacing: 2) {
                Image(systemName: state == .sick ? "thermometer.medium" : "moon.fill").font(.system(size: 15))
                Text(state == .sick ? "DAY \(today?.sickDay ?? 1)" : "REST").font(WatchFont.body(7, weight: .bold))
            }
            .foregroundStyle(Color.muted)
        }
    }

    private var corner: some View {
        Image(systemName: state == .done ? "checkmark" : Glyph.symbol(today?.sport ?? "other"))
            .font(.system(size: 18, weight: .semibold))
            .foregroundStyle(state == .done ? Color.volt : color)
            .widgetAccentable()
            .widgetLabel { Text(WatchGlance.inline(today).uppercased()) }
    }
}

private struct TomorrowLine: View {
    let tomorrow: WidgetSnapshot.Tomorrow?

    var body: some View {
        if let tomorrow {
            HStack(spacing: 4) {
                Image(systemName: Glyph.symbol(tomorrow.sport)).font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(Glyph.color(tomorrow.sport))
                Text("Tomorrow · " + WidgetFormat.sportLabel(tomorrow.sport))
                    .font(WatchFont.body(11)).foregroundStyle(Color.subtle)
                if let minutes = tomorrow.durationMin {
                    Text("\(minutes) MIN").font(WatchFont.number(12)).foregroundStyle(Color.time)
                }
            }
            .lineLimit(1)
        }
    }
}

// MARK: - Rehab

struct RehabGlance: View {
    let entry: GlanceEntry
    @Environment(\.widgetFamily) private var widgetFamily
    /// Set by the Watch app's demo stage, which has no widget environment.
    var forced: WidgetFamily?
    private var family: WidgetFamily { forced ?? widgetFamily }

    private var rehab: WidgetSnapshot.Rehab? { entry.today?.rehab }
    private var done: Int { rehab?.done ?? 0 }
    private var total: Int { rehab?.total ?? 0 }

    var body: some View {
        switch family {
        case .accessoryCircular:
            ZStack {
                SegmentRing(done: done, total: total, color: .mobility, track: .mobilityTrack)
                VStack(spacing: 0) {
                    Text(rehab == nil ? "—" : "\(done)/\(total)").font(WatchFont.number(16)).foregroundStyle(Color.mobility)
                    Text("REHAB").font(WatchFont.body(7, weight: .bold)).foregroundStyle(Color.muted)
                }
            }
        case .accessoryCorner:
            Text(rehab == nil ? "—" : "\(done)/\(total)")
                .font(WatchFont.number(17))
                .foregroundStyle(Color.mobility)
                .widgetAccentable()
                .widgetLabel {
                    Gauge(value: Double(done), in: 0...Double(max(total, 1))) { Text("Rehab") }
                        .tint(Color.mobility)
                }
        default:
            VStack(alignment: .leading, spacing: 3) {
                GlanceKicker(rehab?.title ?? "Rehab", symbol: "cross.circle", color: .mobility,
                             trailing: rehab.map { "\($0.done)/\($0.total)" }, trailingColor: .ink)
                if let rehab {
                    SegmentBar(done: rehab.done, total: rehab.total).padding(.vertical, 4)
                    GlanceLine(WatchGlance.rehabLine(rehab))
                } else {
                    GlanceLine("Nothing due today")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - Week

struct WeekGlance: View {
    let entry: GlanceEntry
    @Environment(\.widgetFamily) private var widgetFamily
    /// Set by the Watch app's demo stage, which has no widget environment.
    var forced: WidgetFamily?
    private var family: WidgetFamily { forced ?? widgetFamily }

    private var today: WidgetSnapshot.Today? { entry.today }
    private var share: Double { today.map { WidgetFormat.share($0.weekDoneMin, of: $0.weekPlannedMin) } ?? 0 }
    private var done: String { today.map { WidgetFormat.clock($0.weekDoneMin) } ?? "—" }

    var body: some View {
        switch family {
        case .accessoryCircular:
            ZStack {
                ProgressRing(share: share, color: .time, track: .timeTrack)
                VStack(spacing: 0) {
                    Text(done).font(WatchFont.number(15)).foregroundStyle(Color.time)
                    Text("WEEK").font(WatchFont.body(7, weight: .bold)).foregroundStyle(Color.muted)
                }
            }
        case .accessoryCorner:
            Text(done)
                .font(WatchFont.number(17))
                .foregroundStyle(Color.time)
                .widgetAccentable()
                .widgetLabel {
                    Gauge(value: share) { Text("Week") }.tint(Color.time)
                }
        default:
            VStack(alignment: .leading, spacing: 6) {
                GlanceKicker("Week", symbol: nil, color: .muted,
                             trailing: today.map(WatchGlance.week), trailingColor: .time)
                WeekDots(today: today, date: entry.date).padding(.bottom, 6)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

/// Seven dots: filled = done, ring = planned, dashed = missed, dash = rest; today underlined.
private struct WeekDots: View {
    let today: WidgetSnapshot.Today?
    let date: Date

    private var days: [WidgetSnapshot.Day] { Array((today?.week ?? []).prefix(7)) }

    private var nowIndex: Int {
        if let index = days.firstIndex(where: { $0.status == "today" }) { return index }
        return (Calendar(identifier: .gregorian).component(.weekday, from: date) + 5) % 7
    }

    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<7, id: \.self) { index in
                VStack(spacing: 3) {
                    Text(["M", "T", "W", "T", "F", "S", "S"][index])
                        .font(WatchFont.body(9, weight: .semibold))
                        .foregroundStyle(index == nowIndex ? Color.ink : Color.dim)
                    dot(index < days.count ? days[index] : nil, isNow: index == nowIndex)
                        .frame(width: 10, height: 10)
                }
                .overlay(alignment: .bottom) {
                    if index == nowIndex { Capsule().fill(Color.ink).frame(width: 10, height: 2).offset(y: 5) }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    @ViewBuilder private func dot(_ day: WidgetSnapshot.Day?, isNow: Bool) -> some View {
        if let day {
            let color = Glyph.color(day.doneSports.first ?? day.sport)
            if day.status == "done" || (isNow && today?.isDone == true) {
                Circle().fill(color).widgetAccentable()
            } else if day.sport == "rest" {
                Capsule().fill(Color.dim).frame(width: 7, height: 2)
            } else if day.status == "missed" || day.status == "skipped" {
                Circle().strokeBorder(color.opacity(0.45), style: StrokeStyle(lineWidth: 1.5, dash: [2, 2]))
            } else {
                Circle().strokeBorder(color, lineWidth: 2)
            }
        } else {
            Circle().strokeBorder(Color.dim, lineWidth: 1.5)
        }
    }
}

// MARK: - Food

struct FoodGlance: View {
    let entry: GlanceEntry
    @Environment(\.widgetFamily) private var widgetFamily
    /// Set by the Watch app's demo stage, which has no widget environment.
    var forced: WidgetFamily?
    private var family: WidgetFamily { forced ?? widgetFamily }

    private var food: WidgetSnapshot.Food? { entry.food }
    private var toGo: String { food?.kcalToGo.map(WidgetFormat.kcal) ?? "—" }

    var body: some View {
        switch family {
        case .accessoryCircular:
            ZStack {
                ProgressRing(share: food?.share ?? 0, color: .volt, track: .voltTrack)
                VStack(spacing: 0) {
                    Text(toGo).font(WatchFont.number(15)).foregroundStyle(Color.ink).minimumScaleFactor(0.7)
                    Text("KCAL").font(WatchFont.body(7, weight: .bold)).foregroundStyle(Color.muted)
                }
                .padding(.horizontal, 6)
            }
        case .accessoryCorner:
            Text(toGo)
                .font(WatchFont.number(17))
                .foregroundStyle(Color.ink)
                .widgetLabel {
                    Gauge(value: food?.share ?? 0) { Text("Food") }.tint(Color.volt)
                }
        case .accessoryInline:
            Label(food?.kcalToGo.map { "\(WidgetFormat.kcal($0)) kcal to go" } ?? "Food", systemImage: "fork.knife")
        default:
            VStack(alignment: .leading, spacing: 3) {
                GlanceKicker("Food", symbol: "fork.knife", color: .muted, trailing: protein, trailingColor: .mobility)
                if let food, food.kcalToGo != nil {
                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(toGo).font(WatchFont.number(30)).foregroundStyle(Color.ink)
                        Text("kcal to go").font(WatchFont.body(11, weight: .semibold)).foregroundStyle(Color.ink)
                    }
                    ShareBar(share: food.share)
                } else {
                    GlanceLine("Nothing logged today")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// "P 84/140 G".
    private var protein: String? {
        guard let food else { return nil }
        let eaten = Int(food.proteinG.rounded())
        return food.proteinTargetG.map { "P \(eaten)/\(Int($0.rounded())) G" } ?? "P \(eaten) G"
    }
}

// MARK: - Parts

private struct GlanceKicker: View {
    let text: String
    let symbol: String?
    let color: Color
    var trailing: String?
    var trailingColor: Color = .ink

    init(_ text: String, symbol: String?, color: Color, trailing: String? = nil, trailingColor: Color = .ink) {
        self.text = text
        self.symbol = symbol
        self.color = color
        self.trailing = trailing
        self.trailingColor = trailingColor
    }

    var body: some View {
        HStack(spacing: 4) {
            if let symbol { Image(systemName: symbol).font(.system(size: 9, weight: .bold)) }
            Text(text.uppercased()).font(WatchFont.body(9.5, weight: .bold)).tracking(1.1).lineLimit(1)
                .minimumScaleFactor(0.8)
            Spacer(minLength: 4)
            if let trailing {
                Text(trailing).font(WatchFont.number(14)).foregroundStyle(trailingColor).lineLimit(1).fixedSize()
            }
        }
        .foregroundStyle(color)
        .widgetAccentable()
    }
}

private struct GlanceTitle: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text.uppercased())
            .font(WatchFont.title(24))
            .foregroundStyle(Color.ink)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
    }
}

private struct GlanceLine: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text).font(WatchFont.body(11)).foregroundStyle(Color.muted).lineLimit(1)
    }
}

private struct ShareBar: View {
    let share: Double

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.voltTrack)
                Capsule().fill(Color.volt).frame(width: proxy.size.width * max(0.03, share)).widgetAccentable()
            }
        }
        .frame(height: 5)
    }
}

private struct SegmentBar: View {
    let done: Int
    let total: Int

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<max(total, 1), id: \.self) { index in
                Capsule().fill(index < done ? Color.mobility : Color.mobilityTrack).frame(height: 5)
            }
        }
        .widgetAccentable()
    }
}

private struct ProgressRing: View {
    let share: Double
    let color: Color
    let track: Color

    var body: some View {
        ZStack {
            Circle().stroke(track, lineWidth: 4)
            Circle()
                .trim(from: 0, to: max(0.001, min(1, share)))
                .stroke(color, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .widgetAccentable()
        }
        .padding(2)
    }
}

/// A ring cut into one segment per rehab exercise.
private struct SegmentRing: View {
    let done: Int
    let total: Int
    let color: Color
    let track: Color

    var body: some View {
        let count = max(total, 1)
        let gap = count > 1 ? 0.025 : 0
        ZStack {
            ForEach(0..<count, id: \.self) { index in
                let start = Double(index) / Double(count)
                Circle()
                    .trim(from: start + gap / 2, to: start + 1 / Double(count) - gap / 2)
                    .stroke(index < done ? color : track, lineWidth: 4)
                    .rotationEffect(.degrees(-90))
            }
        }
        .padding(2)
        .widgetAccentable()
    }
}

enum Glyph {
    static func symbol(_ sport: String) -> String {
        switch sport {
        case "strength": "dumbbell.fill"
        case "ride": "bicycle"
        case "run": "figure.run"
        case "mobility": "figure.cooldown"
        case "walk": "figure.walk"
        case "hike": "figure.hiking"
        case "rest": "moon.fill"
        default: "figure.mixed.cardio"
        }
    }

    static func color(_ sport: String) -> Color {
        switch sport {
        case "ride": .ride
        case "run": .run
        case "strength": .strength
        case "mobility", "walk": .mobility
        case "rest": .dim
        default: .other
        }
    }
}

extension Color {
    /// Time is yellow everywhere in the design (widgets v2).
    static let time = Color(hex: 0xFFD24A)
    static let timeTrack = Color(hex: 0x3A3420)
    static let voltTrack = Color(hex: 0x2E3520)
    static let run = Color(hex: 0xFF8A2A)
    static let other = Color(hex: 0x8B7BFF)
    static let subtle = Color(hex: 0xA3ABBC)
    static let dim = Color(hex: 0x3A4150)
}
