import SwiftUI
import WidgetKit

// Home Screen and Lock Screen widgets (artboard frame 7: week hours ring and kcal to go).

struct TodayWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "today", provider: SnapshotProvider()) { entry in
            TodayWidgetView(entry: entry).widgetBackground()
        }
        .configurationDisplayName("Today")
        .description("Today's session, with week hours and food alongside.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular, .accessoryInline])
    }
}

struct WeekWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "week", provider: SnapshotProvider()) { entry in
            WeekWidgetView(entry: entry).widgetBackground()
        }
        .configurationDisplayName("Week hours")
        .description("Training time done this week against the plan.")
        .supportedFamilies([.accessoryCircular, .systemSmall])
    }
}

struct FoodWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "food", provider: SnapshotProvider()) { entry in
            FoodWidgetView(entry: entry).widgetBackground()
        }
        .configurationDisplayName("Kcal to go")
        .description("What's left to eat today, and protein.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .systemSmall])
    }
}

private extension View {
    func widgetBackground() -> some View {
        containerBackground(for: .widget) { Color.card }
    }
}

// MARK: Today

struct TodayWidgetView: View {
    let entry: SnapshotEntry
    @Environment(\.widgetFamily) private var family

    private var today: WidgetSnapshot.Today? { entry.snapshot.today(on: entry.date) }
    private var food: WidgetSnapshot.Food? { entry.snapshot.food(on: entry.date) }

    var body: some View {
        Group {
            switch family {
            case .accessoryInline: inline
            case .accessoryRectangular: rectangular
            case .systemMedium:
                HStack(spacing: 14) {
                    TodaySession(today: today, date: entry.date)
                    Rectangle().fill(Color.cardBorder).frame(width: 1)
                    VStack(alignment: .leading, spacing: 12) {
                        WeekMini(today: today)
                        FoodMini(food: food)
                    }
                    .frame(width: 128)
                }
            default: TodaySession(today: today, date: entry.date)
            }
        }
        .widgetURL(URL(string: "trainlog://today"))
    }

    private var inline: some View {
        let sport = Sport(rawValue: today?.sport ?? "") ?? .rest
        var parts = [today.map { $0.isDone ? "\(title) done" : title } ?? "TrainLog"]
        if let toGo = food?.kcalToGo, toGo > 0 { parts.append("\(WidgetFormat.kcal(toGo)) kcal to go") }
        return Label(parts.joined(separator: " · "), systemImage: sport.symbol)
    }

    private var rectangular: some View {
        let sport = Sport(rawValue: today?.sport ?? "") ?? .rest
        return VStack(alignment: .leading, spacing: 1) {
            Label {
                Text(today?.isDone == true ? "DONE" : "TODAY")
            } icon: {
                Image(systemName: today?.isDone == true ? "checkmark.circle.fill" : sport.symbol)
            }
            .font(AppFont.body(11, weight: .bold))
            .widgetAccentable()
            Text(title)
                .font(AppFont.title(20))
                .textCase(.uppercase)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(detail)
                .font(AppFont.body(12, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var title: String {
        guard let today else { return "Open TrainLog" }
        return today.title ?? "Rest day"
    }

    private var detail: String {
        var parts: [String] = []
        if let minutes = today?.durationMin, minutes > 0 { parts.append(WidgetFormat.duration(minutes)) }
        if let toGo = food?.kcalToGo { parts.append(toGo > 0 ? "\(WidgetFormat.kcal(toGo)) kcal to go" : "kcal target hit") }
        return parts.isEmpty ? "Nothing planned" : parts.joined(separator: " · ")
    }
}

/// The small Today widget, and the left half of the medium one.
private struct TodaySession: View {
    let today: WidgetSnapshot.Today?
    let date: Date

    private var sport: Sport { Sport(rawValue: today?.sport ?? "") ?? .rest }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker(date.formatted(.dateTime.weekday(.abbreviated).day().locale(Locale(identifier: "en_GB"))))
                Spacer()
                if let today { ReadinessDot(level: today.readiness) }
            }
            Spacer(minLength: 6)
            Image(systemName: sport.symbol)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color.bg)
                .frame(width: 28, height: 28)
                .background(sport.color, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .widgetAccentable()
            Text(today.map { $0.title ?? "Rest day" } ?? "Open TrainLog")
                .font(AppFont.title(26))
                .textCase(.uppercase)
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .minimumScaleFactor(0.6)
                .padding(.top, 8)
            status.padding(.top, 3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    @ViewBuilder private var status: some View {
        if today?.isDone == true {
            Label("Done", systemImage: "checkmark")
                .font(AppFont.body(12, weight: .bold))
                .foregroundStyle(Color.volt)
        } else {
            Text(subtitle)
                .font(AppFont.body(12, weight: .medium))
                .foregroundStyle(Color.inkSoft)
                .lineLimit(1)
        }
    }

    private var subtitle: String {
        guard let today else { return "No data yet" }
        if sport == .rest { return today.streakDays > 1 ? "\(today.streakDays)-day streak" : "Recover well" }
        return [sport.label, today.durationMin.map(WidgetFormat.duration)].compactMap { $0 }.joined(separator: " · ")
    }
}

private struct ReadinessDot: View {
    let level: String

    private var color: Color {
        switch level {
        case "green": .mobility
        case "amber": .warning
        case "red": .danger
        default: .dim
        }
    }

    var body: some View {
        Circle().fill(color).frame(width: 8, height: 8)
    }
}

// MARK: Week

struct WeekWidgetView: View {
    let entry: SnapshotEntry
    @Environment(\.widgetFamily) private var family

    private var today: WidgetSnapshot.Today? { entry.snapshot.today }

    var body: some View {
        Group {
            if family == .accessoryCircular {
                ZStack {
                    AccessoryWidgetBackground()
                    Ring(segments: [(.white, share)], lineWidth: 5, track: .white.opacity(0.18), roundCaps: true)
                        .widgetAccentable()
                        .padding(4)
                    VStack(spacing: -1) {
                        Text(WidgetFormat.clock(today?.weekDoneMin ?? 0)).font(AppFont.number(17))
                        Text("of \(WidgetFormat.hours(today?.weekPlannedMin ?? 0))").font(AppFont.body(9, weight: .medium)).opacity(0.7)
                    }
                }
            } else {
                small
            }
        }
        .widgetURL(URL(string: "trainlog://plan"))
    }

    private var share: Double { WidgetFormat.share(today?.weekDoneMin ?? 0, of: today?.weekPlannedMin ?? 0) }

    private var small: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Week")
                Spacer()
                Text("\(Int((share * 100).rounded()))%")
                    .font(AppFont.number(14, weight: .semibold))
                    .foregroundStyle(share >= 1 ? Color.volt : Color.inkSoft)
            }
            Spacer(minLength: 4)
            HStack(spacing: 10) {
                ZStack {
                    Ring(segments: SportRing.segments(today), lineWidth: 9, track: .track, roundCaps: false)
                        .widgetAccentable()
                    VStack(spacing: -2) {
                        Text(WidgetFormat.clock(today?.weekDoneMin ?? 0)).font(AppFont.number(24)).foregroundStyle(Color.ink)
                        Text("of \(WidgetFormat.hours(today?.weekPlannedMin ?? 0))").font(AppFont.body(10, weight: .medium)).foregroundStyle(Color.muted)
                    }
                }
                .frame(width: 80, height: 80)
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array((today?.weekBySport ?? []).prefix(4).enumerated()), id: \.offset) { _, part in
                        let sport = Sport(rawValue: part.sport) ?? .other
                        HStack(spacing: 5) {
                            Circle().fill(sport.color).frame(width: 7, height: 7)
                            Text(WidgetFormat.clock(part.minutes))
                                .font(AppFont.number(13, weight: .semibold))
                                .foregroundStyle(Color.inkSoft)
                                .fixedSize()
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }
    }
}

/// The medium Today widget's week line.
private struct WeekMini: View {
    let today: WidgetSnapshot.Today?

    var body: some View {
        let done = today?.weekDoneMin ?? 0
        let planned = today?.weekPlannedMin ?? 0
        VStack(alignment: .leading, spacing: 5) {
            Kicker("Week")
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(WidgetFormat.clock(done)).font(AppFont.number(22)).foregroundStyle(Color.ink)
                Text("of \(WidgetFormat.hours(planned))").font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            SportBar(today: today)
        }
    }
}

/// Done minutes per sport, laid along the planned week.
private struct SportBar: View {
    let today: WidgetSnapshot.Today?

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 2) {
                ForEach(Array(SportRing.segments(today).enumerated()), id: \.offset) { _, part in
                    Rectangle().fill(part.color).frame(width: max(2, geo.size.width * part.share - 2))
                }
                Spacer(minLength: 0)
            }
            .background(Color.track)
            .clipShape(Capsule())
        }
        .frame(height: 5)
    }
}

enum SportRing {
    static func segments(_ today: WidgetSnapshot.Today?) -> [(color: Color, share: Double)] {
        guard let today, today.weekPlannedMin > 0 else { return [] }
        let total = Double(max(today.weekPlannedMin, today.weekDoneMin))
        return today.weekBySport.filter { $0.minutes > 0 }.map {
            ((Sport(rawValue: $0.sport) ?? .other).color, Double($0.minutes) / total)
        }
    }
}

struct Ring: View {
    let segments: [(color: Color, share: Double)]
    let lineWidth: CGFloat
    let track: Color
    let roundCaps: Bool

    var body: some View {
        ZStack {
            Circle().stroke(track, lineWidth: lineWidth)
            ForEach(Array(starts.enumerated()), id: \.offset) { index, start in
                Circle()
                    .trim(from: start, to: start + segments[index].share)
                    .stroke(segments[index].color, style: StrokeStyle(lineWidth: lineWidth, lineCap: roundCaps ? .round : .butt))
                    .rotationEffect(.degrees(-90))
            }
        }
        .padding(lineWidth / 2)
    }

    private var starts: [Double] {
        segments.indices.map { index in segments[..<index].reduce(0) { $0 + $1.share } }
    }
}

// MARK: Food

struct FoodWidgetView: View {
    let entry: SnapshotEntry
    @Environment(\.widgetFamily) private var family

    private var food: WidgetSnapshot.Food? { entry.snapshot.food(on: entry.date) }
    private var hit: Bool { food?.kcalToGo == 0 }
    private var toGo: String { food?.kcalToGo.map(WidgetFormat.kcal) ?? "–" }

    var body: some View {
        Group {
            switch family {
            case .accessoryCircular: circular
            case .accessoryRectangular: rectangular
            default: small
            }
        }
        .widgetURL(URL(string: "trainlog://food"))
    }

    private var circular: some View {
        ZStack {
            AccessoryWidgetBackground()
            Ring(segments: [(.white, food?.share ?? 0)], lineWidth: 5, track: .white.opacity(0.18), roundCaps: true)
                .widgetAccentable()
                .padding(4)
            VStack(spacing: -1) {
                if hit {
                    Image(systemName: "checkmark").font(.system(size: 18, weight: .bold))
                } else {
                    Text(toGo).font(AppFont.number(17)).minimumScaleFactor(0.7)
                    Text("to go").font(AppFont.body(9, weight: .medium)).opacity(0.7)
                }
            }
        }
    }

    private var rectangular: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("FOOD")
                .font(AppFont.body(10, weight: .bold))
                .tracking(1)
                .foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(hit ? "Target hit" : toGo).font(AppFont.number(24))
                if !hit { Text("kcal to go").font(AppFont.body(13, weight: .medium)).widgetAccentable() }
            }
            LinearBar(share: food?.share ?? 0, fill: .white, track: .white.opacity(0.18), height: 4)
                .widgetAccentable()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var small: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Food")
                Spacer()
                Image(systemName: "fork.knife").font(.system(size: 13, weight: .semibold)).foregroundStyle(Color.muted)
            }
            Spacer(minLength: 4)
            if hit {
                Text("Target hit").font(AppFont.title(30)).textCase(.uppercase).foregroundStyle(Color.volt)
                Text("\(WidgetFormat.kcal(food?.eatenKcal ?? 0)) kcal eaten")
                    .font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.inkSoft)
            } else {
                Text(toGo)
                    .font(AppFont.number(50))
                    .foregroundStyle(food == nil ? Color.muted : Color.warning)
                    .minimumScaleFactor(0.6)
                    .widgetAccentable()
                Text(food == nil ? "Open TrainLog" : "kcal to go")
                    .font(AppFont.body(12, weight: .medium))
                    .foregroundStyle(Color.inkSoft)
                    .padding(.top, -4)
            }
            LinearBar(share: food?.share ?? 0, fill: .volt, track: .track, height: 6)
                .widgetAccentable()
                .padding(.top, 10)
            if let food, let target = food.proteinTargetG {
                HStack(spacing: 4) {
                    Text("Protein").foregroundStyle(Color.muted)
                    Spacer()
                    Text("\(WidgetFormat.kcal(food.proteinG)) / \(WidgetFormat.kcal(target)) g").foregroundStyle(Color.ink)
                }
                .font(AppFont.body(11, weight: .semibold))
                .padding(.top, 8)
            }
        }
    }
}

/// The medium Today widget's food line.
private struct FoodMini: View {
    let food: WidgetSnapshot.Food?

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Kicker("Food")
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                if food?.kcalToGo == 0 {
                    Text("Target hit").font(AppFont.number(22)).foregroundStyle(Color.volt)
                } else {
                    Text(food?.kcalToGo.map(WidgetFormat.kcal) ?? "–").font(AppFont.number(22)).foregroundStyle(Color.ink)
                    Text("kcal to go").font(AppFont.body(11)).foregroundStyle(Color.warning)
                }
            }
            LinearBar(share: food?.share ?? 0, fill: .volt, track: .track, height: 5)
        }
    }
}

struct LinearBar: View {
    let share: Double
    let fill: Color
    let track: Color
    let height: CGFloat

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(track)
                Capsule().fill(fill).frame(width: max(share > 0 ? height : 0, geo.size.width * share))
            }
        }
        .frame(height: height)
    }
}

#Preview("Today", as: .systemMedium) {
    TodayWidget()
} timeline: {
    SnapshotEntry(date: .now, snapshot: .preview)
}

#Preview("Food", as: .accessoryRectangular) {
    FoodWidget()
} timeline: {
    SnapshotEntry(date: .now, snapshot: .preview)
}
