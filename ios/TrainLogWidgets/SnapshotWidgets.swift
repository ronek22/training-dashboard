import SwiftUI
import WidgetKit

// Home Screen and Lock Screen widgets (docs/design/artboards/iOSWidgets.dc.html: the wide Today
// widget is direction A, small widgets and Lock Screen accessories as drawn there).

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
        containerBackground(for: .widget) { Color.bg }
    }
}

private extension Color {
    /// Time is yellow everywhere in activity detail D2.
    static let time = Color(hex: 0xFFD24A)
    static let behind = Color(hex: 0xFFC873)
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
            case .systemMedium: WideToday(today: today, food: food, date: entry.date)
            default: SmallToday(today: today, date: entry.date)
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
        return today.shortTitle ?? "Rest day"
    }

    private var detail: String {
        var parts: [String] = []
        if let minutes = today?.durationMin, minutes > 0 { parts.append(WidgetFormat.duration(minutes)) }
        if let toGo = food?.kcalToGo { parts.append(toGo > 0 ? "\(WidgetFormat.kcal(toGo)) kcal to go" : "kcal target hit") }
        return parts.isEmpty ? "Nothing planned" : parts.joined(separator: " · ")
    }
}

/// Direction A: the session across the top, week and food as two meters below.
private struct WideToday: View {
    let today: WidgetSnapshot.Today?
    let food: WidgetSnapshot.Food?
    let date: Date

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // A long focus keeps its words; the date gives way first.
            ViewThatFits(in: .horizontal) {
                header(showDate: true)
                header(showDate: false)
                header(showDate: false, truncate: true)
            }
            SessionTitle(today: today, size: 30, lines: 1)
                .padding(.top, 6)
            SessionLine(today: today)
                .padding(.top, 4)
            Spacer(minLength: 8)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    WeekValue(today: today, size: 22)
                    SportBar(today: today, height: 5)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Rectangle().fill(Color.cardBorder).frame(width: 1)
                VStack(alignment: .leading, spacing: 8) {
                    FoodValue(food: food, date: date, size: 22)
                    LinearBar(share: food?.share ?? 0, fill: .volt.opacity(0.85), track: .track, height: 5)
                        .widgetAccentable()
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .fixedSize(horizontal: false, vertical: true)
            .padding(.top, 12)
        }
    }

    @ViewBuilder private func header(showDate: Bool, truncate: Bool = false) -> some View {
        HStack(spacing: 8) {
            if truncate { SportKicker(today: today) } else { SportKicker(today: today).fixedSize() }
            Spacer(minLength: 4)
            DayStatus(today: today, date: date, showDate: showDate)
        }
    }
}

private struct SmallToday: View {
    let today: WidgetSnapshot.Today?
    let date: Date

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            DayStatus(today: today, date: date)
            if today?.isDone == true {
                Image(systemName: "checkmark")
                    .font(.system(size: 18, weight: .heavy))
                    .foregroundStyle(Color.bg)
                    .frame(width: 40, height: 40)
                    .background(Color.volt, in: Circle())
                    .widgetAccentable()
                    .padding(.top, 10)
            }
            Spacer(minLength: 6)
            SportKicker(today: today)
            SessionTitle(today: today, size: 24, lines: 2)
                .padding(.top, 4)
            SessionLine(today: today)
                .padding(.top, 3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// "Strength · Wide Shoulders" in the sport's colour.
private struct SportKicker: View {
    let today: WidgetSnapshot.Today?

    private var color: Color {
        guard let today else { return .muted }
        if today.sickDay != nil { return .danger }
        return today.sport == "rest" ? .muted : (Sport(rawValue: today.sport) ?? .other).color
    }

    var body: some View {
        Kicker(today?.kicker ?? "TrainLog", color: color)
            .lineLimit(1)
            .widgetAccentable()
    }
}

/// "Fri 30 · ● Ready".
private struct DayStatus: View {
    let today: WidgetSnapshot.Today?
    let date: Date
    var showDate = true

    var body: some View {
        HStack(spacing: 4) {
            if showDate || today == nil {
                Text(date.formatted(.dateTime.weekday(.abbreviated).day().locale(Locale(identifier: "en_GB"))))
                    .foregroundStyle(Color.muted)
            }
            if let level = today?.readiness {
                if showDate { Text("·").foregroundStyle(Color.muted) }
                Circle().fill(ReadinessDot.color(level)).frame(width: 7, height: 7)
                Text(WidgetFormat.readinessWord(level)).foregroundStyle(ReadinessDot.color(level))
            }
        }
        .font(AppFont.body(11, weight: .semibold))
        .lineLimit(1)
        .fixedSize()
    }
}

private struct SessionTitle: View {
    let today: WidgetSnapshot.Today?
    let size: CGFloat
    let lines: Int

    private var text: String {
        guard let today else { return "Open TrainLog" }
        if today.sickDay != nil { return "Sick day" }
        return today.sport == "rest" ? "Rest day" : (today.shortTitle ?? "Rest day")
    }

    var body: some View {
        Text(text)
            .font(AppFont.title(size))
            .textCase(.uppercase)
            .foregroundStyle(Color.ink)
            .lineLimit(lines)
            .minimumScaleFactor(0.6)
    }
}

/// Under the title: duration in yellow, done with the streak, or tomorrow on a rest day.
private struct SessionLine: View {
    let today: WidgetSnapshot.Today?

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            content
        }
        .font(AppFont.body(13, weight: .medium))
        .foregroundStyle(Color.inkSoft)
        .lineLimit(1)
        .minimumScaleFactor(0.8)
    }

    @ViewBuilder private var content: some View {
        if let today {
            if today.sickDay != nil {
                Text("Rest · plan on hold")
            } else if today.isDone {
                Label("Done", systemImage: "checkmark")
                    .labelStyle(DoneLabel())
                    .foregroundStyle(Color.volt)
                if today.streakDays > 1 { Text("· \(today.streakDays)-day streak") }
            } else if today.sport == "rest" {
                if let tomorrow = today.tomorrow, tomorrow.sport != "rest" {
                    Text("Tomorrow")
                    Text(WidgetFormat.sportLabel(tomorrow.sport))
                        .fontWeight(.semibold)
                        .foregroundStyle((Sport(rawValue: tomorrow.sport) ?? .other).color)
                    if let minutes = tomorrow.durationMin { Minutes(minutes) }
                } else {
                    Text(today.streakDays > 1 ? "\(today.streakDays)-day streak" : "Recover well")
                }
            } else {
                if let minutes = today.durationMin { Minutes(minutes) }
                if let lifts = today.liftCount, lifts > 0 { Text("· \(lifts) lifts") }
            }
        } else {
            Text("No data yet")
        }
    }
}

private struct DoneLabel: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 3) {
            configuration.icon.font(.system(size: 11, weight: .heavy))
            configuration.title.fontWeight(.semibold)
        }
    }
}

/// "45 min" in time yellow.
private struct Minutes: View {
    let minutes: Int
    init(_ minutes: Int) { self.minutes = minutes }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 2) {
            Text("\(minutes)").font(AppFont.number(16))
            Text("min").font(AppFont.body(12, weight: .medium))
        }
        .foregroundStyle(Color.time)
    }
}

private enum ReadinessDot {
    static func color(_ level: String) -> Color {
        switch level {
        case "green": .mobility
        case "amber": .warning
        case "red": .danger
        default: .dim
        }
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

    /// Done against planned, uncapped: an over-delivered week reads 109%.
    private var percent: Int {
        guard let today, today.weekPlannedMin > 0 else { return 0 }
        return Int((Double(today.weekDoneMin) / Double(today.weekPlannedMin) * 100).rounded())
    }

    private var weekNumber: Int {
        var calendar = Calendar(identifier: .iso8601)
        calendar.timeZone = .current
        return calendar.component(.weekOfYear, from: entry.date)
    }

    private var small: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Week \(weekNumber)")
                Spacer()
                Text("\(percent)%")
                    .font(AppFont.number(14, weight: .semibold))
                    .foregroundStyle(percent >= 100 ? Color.volt : Color.muted)
            }
            Spacer(minLength: 4)
            WeekValue(today: today, size: 44)
            SportBar(today: today, height: 6)
                .padding(.top, 8)
            WeekStrip(today: today, date: entry.date)
                .padding(.top, 12)
                .padding(.bottom, 4)
        }
    }
}

/// "2:47 of 6h10", time in yellow.
private struct WeekValue: View {
    let today: WidgetSnapshot.Today?
    let size: CGFloat

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text(WidgetFormat.clock(today?.weekDoneMin ?? 0))
                .font(AppFont.number(size))
                .foregroundStyle(Color.time)
            Text("of \(WidgetFormat.hours(today?.weekPlannedMin ?? 0))")
                .font(AppFont.body(size > 30 ? 13 : 12, weight: .medium))
                .foregroundStyle(Color.inkSoft)
        }
        .lineLimit(1)
        .minimumScaleFactor(0.7)
    }
}

/// Done minutes per sport, laid along the planned week.
private struct SportBar: View {
    let today: WidgetSnapshot.Today?
    let height: CGFloat

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
        .frame(height: height)
        .widgetAccentable()
    }
}

/// The week as seven dots: filled = done, ring = planned, dashed = missed, dash = rest.
private struct WeekStrip: View {
    let today: WidgetSnapshot.Today?
    let date: Date

    private var days: [WidgetSnapshot.Day] { Array((today?.week ?? []).prefix(7)) }

    /// Today's place: the day the server marks, else the weekday (Monday first).
    private var nowIndex: Int {
        if let index = days.firstIndex(where: { $0.status == "today" }) { return index }
        return (Calendar(identifier: .gregorian).component(.weekday, from: date) + 5) % 7
    }

    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<7, id: \.self) { index in
                VStack(spacing: 4) {
                    Text(["M", "T", "W", "T", "F", "S", "S"][index])
                        .font(AppFont.body(10, weight: .semibold))
                        .foregroundStyle(index == nowIndex ? Color.ink : Color.faint)
                    dot(index < days.count ? days[index] : nil, isNow: index == nowIndex)
                        .frame(width: 12, height: 12)
                }
                .overlay(alignment: .bottom) {
                    if index == nowIndex { Capsule().fill(Color.ink).frame(width: 12, height: 2).offset(y: 6) }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    @ViewBuilder private func dot(_ day: WidgetSnapshot.Day?, isNow: Bool) -> some View {
        if let day {
            let color = (Sport(rawValue: day.doneSports.first ?? day.sport) ?? .other).color
            if day.status == "done" || (isNow && today?.isDone == true) {
                Circle().fill(color).widgetAccentable()
            } else if day.sport == "rest" {
                Capsule().fill(Color.dim).frame(width: 8, height: 2)
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

    @ViewBuilder private var small: some View {
        if let food, hit {
            VStack(alignment: .leading, spacing: 0) {
                Kicker("Food")
                Image(systemName: "checkmark")
                    .font(.system(size: 18, weight: .heavy))
                    .foregroundStyle(Color.bg)
                    .frame(width: 40, height: 40)
                    .background(Color.volt, in: Circle())
                    .widgetAccentable()
                    .padding(.top, 10)
                Spacer(minLength: 4)
                Text("Fuelled").font(AppFont.title(28)).textCase(.uppercase).foregroundStyle(Color.volt)
                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    Text(WidgetFormat.kcal(food.eatenKcal)).font(AppFont.number(16)).foregroundStyle(Color.ink)
                    Text("kcal ·")
                    Text(WidgetFormat.kcal(food.proteinG)).font(AppFont.number(16)).foregroundStyle(Color.mobility)
                    Text("g protein")
                }
                .font(AppFont.body(12, weight: .medium))
                .foregroundStyle(Color.inkSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .padding(.top, 2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Kicker("Food")
                    Spacer()
                    if let food, food.targetKcal != nil {
                        Text("\(Int((food.share * 100).rounded()))%")
                            .font(AppFont.body(11, weight: .semibold))
                            .foregroundStyle(Color.muted)
                    }
                }
                Spacer(minLength: 4)
                Text(toGo)
                    .font(AppFont.number(52))
                    .foregroundStyle(food == nil ? Color.muted : behind ? Color.behind : Color.ink)
                    .minimumScaleFactor(0.6)
                    .widgetAccentable()
                HStack(spacing: 4) {
                    Text(food == nil ? "Open TrainLog" : "kcal to go")
                    if behind { Text("· behind").foregroundStyle(Color.behind) }
                }
                .font(AppFont.body(13, weight: .medium))
                .foregroundStyle(Color.inkSoft)
                .padding(.top, -2)
                LinearBar(share: food?.share ?? 0, fill: .volt.opacity(0.85), track: .track, height: 6)
                    .widgetAccentable()
                    .padding(.top, 12)
                if let food, let target = food.proteinTargetG {
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text("Protein").font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.mobility)
                        Spacer()
                        Text(WidgetFormat.kcal(food.proteinG)).font(AppFont.number(15)).foregroundStyle(Color.ink)
                        Text("/ \(WidgetFormat.kcal(target)) g").font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.inkSoft)
                    }
                    .padding(.top, 8)
                }
            }
        }
    }

    private var behind: Bool { food.map { WidgetFormat.isBehind($0, at: entry.date) } ?? false }
}

/// Kcal to go for the wide Today widget: white on track, amber when behind, volt when fuelled.
private struct FoodValue: View {
    let food: WidgetSnapshot.Food?
    let date: Date
    let size: CGFloat

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            if food?.kcalToGo == 0 {
                Text("Fuelled").font(AppFont.number(size)).foregroundStyle(Color.volt)
            } else {
                let behind = food.map { WidgetFormat.isBehind($0, at: date) } ?? false
                Text(food?.kcalToGo.map(WidgetFormat.kcal) ?? "–")
                    .font(AppFont.number(size))
                    .foregroundStyle(food == nil ? Color.muted : behind ? Color.behind : Color.ink)
                Text("kcal to go").font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.inkSoft)
            }
        }
        .lineLimit(1)
        .minimumScaleFactor(0.7)
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

#Preview("Week", as: .systemSmall) {
    WeekWidget()
} timeline: {
    SnapshotEntry(date: .now, snapshot: .preview)
}

#Preview("Food", as: .systemSmall) {
    FoodWidget()
} timeline: {
    SnapshotEntry(date: .now, snapshot: .preview)
}
