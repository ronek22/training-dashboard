import SwiftUI

/// Full-screen look back at one month: time as a calendar, the wins, then one card per signal
/// that moves over months (weight, lifts, aerobic base, run). Frames in iOSMonthRecap.dc.html (A v2).
struct MonthRecapView: View {
    @State private var model: MonthRecapModel
    @Environment(\.dismiss) private var dismiss

    init(month: String? = nil) {
        #if DEBUG
        if let demo = MonthRecapDemo.report(month: month) {
            _model = State(initialValue: MonthRecapModel(demo: demo))
            return
        }
        #endif
        _model = State(initialValue: MonthRecapModel(month: month))
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Space.m) {
                    header
                    if model.offline, let syncedAt = model.syncedAt {
                        OfflineNote(syncedAt: syncedAt)
                    }
                    if let report = model.report {
                        MonthContent(report: report) { id in
                            withAnimation(Motion.layout) { proxy.scrollTo(id, anchor: .top) }
                        }
                        // A new month replays the count-ups and reveals.
                        .id(report.month)
                    } else if model.loaded {
                        SyncStateCard(kicker: "Month not loaded", message: model.error ?? "No month on the server yet.")
                    } else {
                        LoadingCards(blocks: [340, 160, 200])
                    }
                }
                .padding(.horizontal, Space.gutter)
                .padding(.bottom, 32)
            }
        }
        .scrollIndicators(.hidden)
        .overlay(alignment: .top) {
            // Keeps scrolled cards from running under the status bar, as on the week recap.
            Color.bg.frame(height: 0).background(Color.bg).allowsHitTesting(false)
        }
        .background(Color.bg)
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
        .task { await model.load() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                monthButton("chevron.left", to: model.report?.previousMonth, label: "Previous month")
                monthButton("chevron.right", to: model.report?.nextMonth, label: "Next month")
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Color.ink)
                        .frame(width: 34, height: 34)
                        .background(Color.raised, in: Circle())
                        .frame(width: 44, height: 44)
                        .contentShape(Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Close")
            }
            VStack(alignment: .leading, spacing: 4) {
                Kicker(kicker)
                Text(title).font(AppFont.title(44)).foregroundStyle(Color.ink).textCase(.uppercase).lineLimit(1).minimumScaleFactor(0.7)
            }
            .padding(.horizontal, 4)
        }
        .padding(.top, 6)
    }

    private var kicker: String {
        guard let report = model.report else { return " " }
        if report.finished { return "\(report.label) · \(report.totals.days) days" }
        return "\(report.label) · day \(report.totals.elapsedDays ?? 1) of \(report.totals.days)"
    }

    private var title: String {
        guard let report = model.report else { return "Your month" }
        let name = MonthRecapFormat.name(report)
        return report.finished ? "Your \(name)" : "\(name) so far"
    }

    private func monthButton(_ symbol: String, to month: String?, label: String) -> some View {
        Button {
            if let month { Task { await model.show(month) } }
        } label: {
            Image(systemName: symbol)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(month == nil ? Color.dim : Color.ink)
                .frame(width: 34, height: 34)
                .overlay(Circle().strokeBorder(Color.outline, lineWidth: 1))
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(month == nil)
        .accessibilityLabel(label)
    }
}

// MARK: - Content

private struct MonthContent: View {
    let report: MonthReport
    let onJump: (String) -> Void

    var body: some View {
        let verdicts = MonthRecapFormat.verdicts(report)
        VStack(alignment: .leading, spacing: Space.m) {
            MonthHeroCard(report: report).reveal(0)
            if !report.wins.isEmpty {
                // The letter's consistency win is the month's volume, not a streak: give it the seal.
                WinsCard(wins: report.wins.map { win in
                    win.kind == "consistency" ? WeekWins.Win(kind: "plan", headline: win.headline, detail: win.detail) : win
                }).reveal(1)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("Is it working?").font(AppFont.title(30)).foregroundStyle(Color.ink).textCase(.uppercase)
                Text("The things that move over months, not weeks.").font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
            }
            .padding(.horizontal, 4)
            .padding(.top, 14)
            .reveal(2)
            if !verdicts.isEmpty {
                VerdictStrip(verdicts: verdicts, onJump: onJump).reveal(2)
            }
            if let weight = report.weight {
                WeightCard(weight: weight, report: report).id("body").reveal(3)
            }
            if let strength = report.strength, strength.liftDays > 0 || strength.up + strength.held + strength.down > 0 {
                LiftsCard(strength: strength, previousName: previousName).id("lifts").reveal(4)
            }
            if let rides = report.rides, rides.minutes > 0 {
                RidesCard(rides: rides, report: report).id("base").reveal(5)
            }
            if let run = report.run {
                RunCard(run: run, month: MonthRecapFormat.name(report)).id("run").reveal(6)
            }
            if let focus = report.focus {
                FocusCard(focus: focus, kicker: nextName).reveal(7)
            }
        }
    }

    private var previousName: String {
        report.previousMonth.flatMap { FoodFormat.parse($0 + "-01") }.map(MonthRecapFormat.monthName) ?? "last month"
    }

    private var nextName: String {
        FoodFormat.parse(report.startDate)
            .flatMap { Calendar(identifier: .gregorian).date(byAdding: .month, value: 1, to: $0) }
            .map(MonthRecapFormat.monthName) ?? "Next month"
    }
}

/// Giant training time, the month as a calendar, then sessions, days, plan and streak.
private struct MonthHeroCard: View {
    let report: MonthReport

    var body: some View {
        let minutes = report.totals.minutes
        VStack(alignment: .leading, spacing: 0) {
            Kicker("Time training", color: .volt)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                CountUp(value: Double(minutes / 60)) { "\(Int($0))" }
                    .font(AppFont.number(96))
                    .foregroundStyle(Color.ink)
                Text("h").font(AppFont.number(34, weight: .semibold)).foregroundStyle(Color.muted)
                CountUp(value: Double(minutes % 60), delay: 0.15) { String(format: "%02d", Int($0)) }
                    .font(AppFont.number(96))
                    .foregroundStyle(Color.ink)
                Text("m").font(AppFont.number(34, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.top, -6)
            usualLine.padding(.top, -4)
            MonthCalendar(report: report).padding(.top, 18)
            HStack(spacing: 0) {
                stat(Double(report.totals.sessions), "sessions") { "\(Int($0))" }
                stat(Double(report.totals.activeDays), "active days") { "\(Int($0))/\(report.totals.elapsedDays ?? report.totals.days)" }
                if let plan = report.plan {
                    stat(Double(plan.done), "plan done") { "\(Int($0))/\(plan.planned)" }
                }
                if let streak = report.streakDays, streak > 1 {
                    stat(Double(streak), "day streak") { "\(Int($0))" }
                }
            }
            .padding(.top, 16)
        }
        .card()
    }

    @ViewBuilder
    private var usualLine: some View {
        if let versus = MonthRecapFormat.versusUsual(report) {
            let usualText = "usual \(TodayFormat.duration(Int(versus.usual.rounded())))\(report.finished ? "" : " by now")"
            if versus.pct > 0 {
                HStack(spacing: 8) {
                    Pill(text: "+\(versus.pct)% training", color: .volt)
                    Text(usualText).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            } else {
                Text(usualText).font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
        }
    }

    private func stat(_ value: Double, _ label: String, format: @escaping (Double) -> String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            CountUp(value: value, delay: 0.3, format: format)
                .font(AppFont.number(28))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Monday-first month grid: each day tinted by its sport, brighter for longer days; sick days get
/// a dot, record days a volt ring. Cells fill in day by day.
private struct MonthCalendar: View {
    let report: MonthReport
    @State private var shown = false

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: 7)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            LazyVGrid(columns: columns, spacing: 6) {
                ForEach(Array(["M", "T", "W", "T", "F", "S", "S"].enumerated()), id: \.offset) { _, letter in
                    Text(letter).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.faint)
                }
                ForEach(0..<MonthRecapFormat.leadingBlanks(report), id: \.self) { _ in Color.clear.frame(height: 34) }
                ForEach(Array(report.days.enumerated()), id: \.element.id) { index, day in
                    cell(day, number: index + 1)
                        .scaleEffect(shown ? 1 : 0.6)
                        .opacity(shown ? 1 : 0)
                        .animation(Motion.pop.delay(0.25 + Double(index) * 0.025), value: shown)
                }
            }
            legend
        }
        .onAppear { shown = true }
    }

    private func cell(_ day: MonthReport.Day, number: Int) -> some View {
        let sport = MonthRecapFormat.sport(day.sport)
        let level = MonthRecapFormat.intensity(day.minutes)
        let shape = RoundedRectangle(cornerRadius: 9, style: .continuous)
        return ZStack(alignment: .bottomLeading) {
            if day.future {
                shape.strokeBorder(Color.raised, style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
            } else if let sport {
                shape.fill(sport.color.opacity(level))
            } else {
                shape.fill(Color.inset).overlay(shape.strokeBorder(Color.cardBorder, lineWidth: 1))
            }
            Text("\(number)")
                .font(AppFont.number(11, weight: .semibold))
                .foregroundStyle(sport != nil && !day.future ? (level == 1 ? Color.bg : Color.ink) : Color.dim)
                .padding(.leading, 6)
                .padding(.bottom, 4)
        }
        .frame(height: 34)
        .overlay(alignment: .topTrailing) {
            if day.record {
                Image(systemName: "star.fill").font(.system(size: 8, weight: .bold)).foregroundStyle(Color.bg.opacity(0.75)).padding(4)
            } else if day.sick {
                Circle().fill(Color.warning).frame(width: 5, height: 5).padding(4)
            }
        }
        .overlay {
            if day.record {
                shape.inset(by: -3.5).strokeBorder(Color.volt, lineWidth: 1.5)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibility(day, number: number))
    }

    private func accessibility(_ day: MonthReport.Day, number: Int) -> String {
        var parts = ["\(number)"]
        parts.append(day.minutes > 0 ? TodayFormat.duration(day.minutes) : day.future ? "to come" : "rest")
        if let sport = MonthRecapFormat.sport(day.sport) { parts.append(sport.label) }
        if day.sick { parts.append("sick") }
        if day.record { parts.append("record") }
        return parts.joined(separator: ", ")
    }

    private var legend: some View {
        let present = Set(report.days.compactMap { MonthRecapFormat.sport($0.sport) })
        var items: [(Color, String)] = [(Sport.strength, "Lift"), (.ride, "Ride"), (.run, "Run"), (.hike, "Mountains"), (.mobility, "Walk")]
            .filter { present.contains($0.0) }
            .map { ($0.0.color, $0.1) }
        if report.days.contains(where: \.sick) { items.append((.warning, "Sick")) }
        if report.days.contains(where: \.record) { items.append((.volt, "Record")) }
        return HStack(spacing: 12) {
            ForEach(items, id: \.1) { color, label in
                HStack(spacing: 5) {
                    RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
                    Text(label).font(AppFont.body(11)).foregroundStyle(Color.inkSoft)
                }
            }
        }
        .lineLimit(1)
        .minimumScaleFactor(0.8)
    }
}

/// One word per signal; tapping a chip scrolls to its card.
private struct VerdictStrip: View {
    let verdicts: [MonthRecapFormat.Verdict]
    let onJump: (String) -> Void

    var body: some View {
        HStack(spacing: 6) {
            ForEach(verdicts) { verdict in
                Button {
                    Haptics.selection()
                    onJump(verdict.id)
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 5) {
                            Image(systemName: symbol(verdict.direction))
                                .font(.system(size: 11, weight: .heavy))
                                .foregroundStyle(verdict.direction == .flat ? Color.faint : verdict.sport.color)
                            Text(verdict.title).font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                        }
                        Text(verdict.word).font(AppFont.number(20)).foregroundStyle(Color.ink).lineLimit(1).minimumScaleFactor(0.7)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
                }
                .buttonStyle(PressableStyle())
                .accessibilityLabel("\(verdict.title): \(verdict.word)")
            }
        }
    }

    private func symbol(_ direction: MonthRecapFormat.Verdict.Direction) -> String {
        switch direction {
        case .up: "arrow.up"
        case .down: "arrow.down"
        case .flat: "minus"
        }
    }
}

// MARK: - Signals

/// The 7-day average against the lean-gain lane, with each weigh-in as a dot.
private struct WeightCard: View {
    let weight: MonthReport.Weight
    let report: MonthReport
    @State private var drawn = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Body weight")
                Spacer()
                Text(weight.weighIns.count == 1 ? "1 weigh-in" : "\(weight.weighIns.count) weigh-ins\(weight.available ? " · 7-day avg" : "")")
                    .font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
            }
            if weight.available, let change = weight.changeKg, let start = weight.startKg, let end = weight.endKg {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    CountUp(value: change, delay: 0.2) { MonthRecapFormat.signed($0) }
                        .font(AppFont.number(56)).foregroundStyle(Color.ink)
                    Text("kg").font(AppFont.number(22, weight: .semibold)).foregroundStyle(Color.muted)
                    Text(String(format: "%.1f → %.1f kg", start, end)).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                }
                .padding(.top, 6)
            }
            chart.frame(height: weight.available ? 128 : 90).padding(.top, 10)
            if weight.available {
                HStack(spacing: 12) {
                    legendItem(Color.ink, "7-day average")
                    legendItem(Color.mobility.opacity(0.4), "Lean-gain lane")
                    legendItem(Color.muted, "Weigh-in")
                }
                .padding(.top, 10)
                let line = MonthRecapFormat.weightLine(weight)
                (Text(line.lead).foregroundStyle(Color.mobility).fontWeight(.semibold) + Text(" " + line.rest).foregroundStyle(Color.inkSoft))
                    .font(AppFont.body(13))
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 8)
            } else {
                let more = max((weight.needed ?? 3) - weight.weighIns.count, 1)
                Text(weight.weighIns.count >= (weight.needed ?? 3) ? "Spread the weigh-ins over a week and the trend appears."
                     : "\(more == 1 ? "One more weigh-in" : "\(more) more weigh-ins") and the trend appears.")
                    .font(AppFont.body(13)).foregroundStyle(Color.inkSoft).padding(.top, 8)
            }
        }
        .card()
        .onAppear { withAnimation(Motion.grow.delay(0.35)) { drawn = true } }
    }

    private func legendItem(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 5) {
            RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
            Text(label).font(AppFont.body(11)).foregroundStyle(Color.inkSoft)
        }
    }

    private var chart: some View {
        let points = weight.weighIns.compactMap { item -> (day: Double, kg: Double, avg: Double)? in
            guard let date = FoodFormat.parse(item.date) else { return nil }
            return (Double(Calendar(identifier: .gregorian).component(.day, from: date)), item.kg, item.avgKg)
        }
        let days = Double(report.totals.days)
        let values = points.flatMap { [$0.kg, $0.avg] }
        let laneTop = weight.available ? (weight.startKg ?? 0) * (1 + (weight.lanePctPerWeek?.last ?? 0.35) / 100 * Double(laneSpan(points)) / 7) : 0
        let lo = floor((values.min() ?? 78) - 0.3)
        let hi = ceil(max(values.max() ?? 80, laneTop) + 0.3)
        return GeometryReader { proxy in
            let w = proxy.size.width, h = proxy.size.height
            let left = 22.0, bottom = 18.0
            let x = { (day: Double) in left + (day - 1) / max(days - 1, 1) * (w - left - 6) }
            let y = { (kg: Double) in 6 + (hi - kg) / max(hi - lo, 0.1) * (h - bottom - 6) }
            ZStack(alignment: .topLeading) {
                ForEach(Array(stride(from: lo, through: hi, by: hi - lo > 4 ? 2 : 1)), id: \.self) { kg in
                    Path { path in
                        path.move(to: CGPoint(x: left, y: y(kg)))
                        path.addLine(to: CGPoint(x: w, y: y(kg)))
                    }
                    .stroke(Color.cardBorder, lineWidth: 1)
                    Text("\(Int(kg))").font(AppFont.number(10, weight: .semibold)).foregroundStyle(Color.subtle)
                        .position(x: 8, y: y(kg))
                }
                if weight.available, let first = points.first, let start = weight.startKg, let pct = weight.lanePctPerWeek, pct.count == 2 {
                    let weeks = (days - first.day) / 7
                    Path { path in
                        path.move(to: CGPoint(x: x(first.day), y: y(start)))
                        path.addLine(to: CGPoint(x: x(days), y: y(start * (1 + pct[1] / 100 * weeks))))
                        path.addLine(to: CGPoint(x: x(days), y: y(start * (1 + pct[0] / 100 * weeks))))
                        path.closeSubpath()
                    }
                    .fill(Color.mobility.opacity(0.16))
                    .opacity(drawn ? 1 : 0)
                }
                if weight.available, points.count > 1 {
                    Path { path in
                        for (index, point) in points.enumerated() {
                            let p = CGPoint(x: x(point.day), y: y(point.avg))
                            index == 0 ? path.move(to: p) : path.addLine(to: p)
                        }
                    }
                    .trim(from: 0, to: drawn ? 1 : 0)
                    .stroke(Color.ink, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    if let last = points.last {
                        Circle().fill(Color.ink).frame(width: 9, height: 9)
                            .overlay(Circle().strokeBorder(Color.card, lineWidth: 2))
                            .position(x: x(last.day), y: y(last.avg))
                            .opacity(drawn ? 1 : 0)
                    }
                }
                ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                    Circle().fill(Color.muted.opacity(weight.available ? 0.8 : 0.5)).frame(width: 6, height: 6)
                        .position(x: x(point.day), y: y(point.kg))
                }
                let name = MonthRecapFormat.range(report).split(separator: " ").last.map(String.init) ?? ""
                ForEach([(1.0, "1 \(name)"), ((days + 1) / 2, "\(Int((days + 1) / 2))"), (days, "\(Int(days))")], id: \.1) { day, label in
                    Text(label).font(AppFont.body(10, weight: .semibold)).tracking(0.6).foregroundStyle(Color.faint)
                        .fixedSize()
                        .position(x: min(max(x(day), left + 16), w - 8), y: h - 5)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(weight.available ? "Weight trend, \(MonthRecapFormat.weightLine(weight).lead)" : "Weigh-ins")
    }

    private func laneSpan(_ points: [(day: Double, kg: Double, avg: Double)]) -> Int {
        Int(Double(report.totals.days) - (points.first?.day ?? 1))
    }
}

/// Best estimated 1RM against last month: the tally, the most-trained lifts with last month as a
/// tick, what dropped, then lift days per week for the 3x anchor.
private struct LiftsCard: View {
    let strength: MonthReport.Strength
    let previousName: String
    @State private var grown = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Strength")
                Spacer()
                Text("best e1RM vs \(previousName)").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
            }
            if strength.up + strength.held + strength.down > 0 {
                HStack(alignment: .firstTextBaseline, spacing: 16) {
                    tally(strength.up, "up", big: true)
                    tally(strength.held, "held")
                    tally(strength.down, "down")
                }
                .padding(.top, 6)
                let peak = strength.top.map { max($0.e1rmKg, $0.previousKg) }.max() ?? 1
                VStack(spacing: 0) {
                    ForEach(Array(strength.top.enumerated()), id: \.element.id) { index, lift in
                        row(lift, peak: peak, index: index)
                    }
                }
                .padding(.top, 8)
                if !strength.dropped.isEmpty {
                    (Text("Down: ").foregroundStyle(Color.danger).fontWeight(.semibold)
                        + Text(MonthRecapFormat.droppedLine(strength.dropped)).foregroundStyle(Color.inkSoft))
                        .font(AppFont.body(13))
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 6)
                }
                Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.vertical, 12)
            }
            HStack(alignment: .firstTextBaseline) {
                Text("Lift \(strength.perWeekTarget)× a week").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink)
                Text("ANCHOR").font(AppFont.body(9, weight: .bold)).tracking(0.9).foregroundStyle(Color.strength)
                Spacer()
                Text("\(strength.liftDays) lift days").font(AppFont.number(16)).foregroundStyle(Color.inkSoft)
            }
            .padding(.top, strength.up + strength.held + strength.down > 0 ? 0 : 10)
            HStack(spacing: 6) {
                ForEach(strength.weeks) { week in weekChip(week) }
            }
            .padding(.top, 8)
        }
        .card()
        .onAppear { withAnimation(Motion.grow.delay(0.4)) { grown = true } }
    }

    private func tally(_ count: Int, _ label: String, big: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            CountUp(value: Double(count), delay: 0.2) { "\(Int($0))" }
                .font(AppFont.number(big ? 56 : 32))
                .foregroundStyle(big && count > 0 ? Color.volt : Color.ink)
            Text(label).font(AppFont.body(big ? 13 : 12, weight: big ? .semibold : .regular)).foregroundStyle(big ? Color.inkSoft : Color.muted)
        }
    }

    private func row(_ lift: MonthReport.Lift, peak: Double, index: Int) -> some View {
        let up = lift.trend == "up"
        let width = 96.0
        return HStack(spacing: 10) {
            Text(MonthRecapFormat.liftName(lift.name)).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink)
                .lineLimit(1).minimumScaleFactor(0.85)
                .frame(maxWidth: .infinity, alignment: .leading)
            ZStack(alignment: .leading) {
                Capsule().fill(Color.track)
                Capsule().fill(Color.dim).frame(width: width * lift.previousKg / peak)
                Capsule().fill(Color.strength.opacity(up ? 1 : 0.55))
                    .frame(width: grown ? width * lift.e1rmKg / peak : 0)
                    .animation(Motion.grow.delay(0.4 + Double(index) * 0.06), value: grown)
                RoundedRectangle(cornerRadius: 1).fill(Color.muted).frame(width: 2, height: 12)
                    .offset(x: width * lift.previousKg / peak - 1)
            }
            .frame(width: width, height: 6)
            Text(String(format: "%.1f", lift.e1rmKg)).font(AppFont.number(17)).foregroundStyle(Color.ink).frame(width: 44, alignment: .trailing)
            Text(lift.trend == "held" ? "held" : MonthRecapFormat.signed(lift.changeKg))
                .font(AppFont.body(12, weight: .bold))
                .foregroundStyle(up ? Color.volt : lift.trend == "down" ? Color.danger : Color.muted)
                .frame(width: 38, alignment: .trailing)
        }
        .padding(.vertical, 7)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(lift.name), \(String(format: "%.1f", lift.e1rmKg)) kilograms, \(lift.trend)")
    }

    private func weekChip(_ week: MonthReport.LiftWeek) -> some View {
        let met = week.days >= strength.perWeekTarget
        return VStack(spacing: 6) {
            HStack(spacing: 3) {
                ForEach(0..<strength.perWeekTarget, id: \.self) { index in
                    Circle().fill(index < week.days ? Color.strength : Color.outline).frame(width: 7, height: 7)
                }
                if week.days > strength.perWeekTarget {
                    Text("+\(week.days - strength.perWeekTarget)").font(AppFont.number(11)).foregroundStyle(Color.strength)
                }
            }
            .frame(height: 12)
            Text("W\(week.weekNumber)").font(AppFont.body(10, weight: .semibold)).tracking(0.6)
                .foregroundStyle(week.sick ? Color.warning : Color.faint)
        }
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.row, style: .continuous)
            .strokeBorder(met ? Color.strength.opacity(0.35) : Color.cardBorder, lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Week \(week.weekNumber): \(week.days) lift days\(week.sick ? ", sick" : "")")
    }
}

/// Ride hours by intensity, this month over last month's faded bar.
private struct RidesCard: View {
    let rides: MonthReport.Rides
    let report: MonthReport
    @State private var grown = false

    private static let shades: [String: Color] = [
        "recovery": Color(hex: 0x9CC4FF), "z2": .ride, "sweet_spot": Color(hex: 0x1F5FCC), "vo2": Color(hex: 0x123C85),
    ]

    var body: some View {
        let scale = Double(max(rides.minutes, rides.previousMinutes, 1))
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Winter base")
                Spacer()
                Text("\(rides.rides) \(rides.rides == 1 ? "ride" : "rides") · by intensity").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
            }
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                CountUp(value: Double(rides.minutes) / 60, delay: 0.2) { String(format: "%.1f", $0) }
                    .font(AppFont.number(56)).foregroundStyle(Color.ink)
                Text("h ridden").font(AppFont.number(22, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.top, 6)
            VStack(spacing: 10) {
                bar(label: monthAbbrev(report.startDate), byIntensity: rides.byIntensity, minutes: rides.minutes, scale: scale, ghost: false)
                if rides.previousMinutes > 0, let previous = report.previousMonth {
                    bar(label: monthAbbrev(previous + "-01"), byIntensity: rides.previousByIntensity, minutes: rides.previousMinutes, scale: scale, ghost: true)
                }
            }
            .padding(.top, 12)
            HStack(spacing: 12) {
                ForEach(MonthRecapFormat.intensities.filter { (rides.byIntensity[$0.key] ?? 0) + (rides.previousByIntensity[$0.key] ?? 0) > 0 }, id: \.key) { item in
                    HStack(spacing: 5) {
                        RoundedRectangle(cornerRadius: 3).fill(Self.shades[item.key] ?? .ride).frame(width: 10, height: 10)
                        Text(item.label).font(AppFont.body(11)).foregroundStyle(Color.inkSoft)
                    }
                }
            }
            .padding(.top, 12)
            if rides.hikingMinutes >= 120, rides.minutes < rides.previousMinutes {
                (Text("The mountains took the hours: ").foregroundStyle(Color.inkSoft)
                    + Text("\(MonthRecapFormat.hours(rides.hikingMinutes)) h").foregroundStyle(Color.other).fontWeight(.semibold)
                    + Text(" hiking.").foregroundStyle(Color.inkSoft))
                    .font(AppFont.body(13))
                    .padding(.top, 10)
            }
        }
        .card()
        .onAppear { withAnimation(Motion.grow.delay(0.35)) { grown = true } }
    }

    private func bar(label: String, byIntensity: [String: Int], minutes: Int, scale: Double, ghost: Bool) -> some View {
        HStack(spacing: 10) {
            Text(label).font(AppFont.body(11, weight: .semibold)).tracking(0.6).foregroundStyle(Color.muted).frame(width: 34, alignment: .leading)
            GeometryReader { proxy in
                HStack(spacing: 2) {
                    ForEach(MonthRecapFormat.intensities, id: \.key) { item in
                        let part = byIntensity[item.key] ?? 0
                        if part > 0 {
                            Rectangle().fill(Self.shades[item.key] ?? .ride)
                                .frame(width: max(2, proxy.size.width * Double(part) / scale - 2))
                        }
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .frame(width: grown ? proxy.size.width * Double(minutes) / scale : 0, alignment: .leading)
                .clipped()
            }
            .frame(height: 14)
            .opacity(ghost ? 0.45 : 1)
            Text("\(MonthRecapFormat.hours(minutes)) h").font(AppFont.number(15)).foregroundStyle(ghost ? Color.faint : Color.ink)
                .frame(width: 48, alignment: .trailing)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(MonthRecapFormat.hours(minutes)) hours")
    }

    private func monthAbbrev(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return "" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM"
        return formatter.string(from: date).uppercased()
    }
}

/// VDOT on a track up to the all-time peak; last month as a ring when the dot moved.
private struct RunCard: View {
    let run: MonthReport.Run
    let month: String
    @State private var placed = false

    var body: some View {
        let paused = run.runs == 0
        let change = MonthRecapFormat.vdotChange(run)
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Run comeback")
                Spacer()
                if let share = run.shareOfPeakPct {
                    Text("\(share)% of peak").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                CountUp(value: run.vdot, delay: 0.2) { paused ? "\(Int($0.rounded()))" : String(format: "%.1f", $0) }
                    .font(AppFont.number(56)).foregroundStyle(paused ? Color.inkSoft : Color.ink)
                Text("VDOT").font(AppFont.number(22, weight: .semibold)).foregroundStyle(paused ? Color.faint : Color.muted)
                if paused {
                    Pill(text: "no runs", color: .muted)
                } else if let change, abs(change) >= 0.5 {
                    Pill(text: MonthRecapFormat.signed(change), color: change > 0 ? .volt : .danger)
                }
            }
            .padding(.top, 6)
            track(paused: paused).frame(height: 46).padding(.top, 6)
            Text(MonthRecapFormat.runLine(run, month: month))
                .font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 10)
        }
        .card()
        .onAppear { withAnimation(Motion.enter.delay(0.4)) { placed = true } }
    }

    private func track(paused: Bool) -> some View {
        let peak = run.peak ?? max(run.vdot, 50)
        let lo = 30.0, hi = max(peak + 3, run.vdot + 3)
        return GeometryReader { proxy in
            let w = proxy.size.width
            let x = { (v: Double) in (min(max(v, lo), hi) - lo) / (hi - lo) * w }
            ZStack(alignment: .topLeading) {
                Capsule().fill(Color.track).frame(height: 6).offset(y: 18)
                Capsule().fill(Color.run.opacity(paused ? 0.35 : 1)).frame(width: placed ? x(run.vdot) : 0, height: 6).offset(y: 18)
                if !paused, let previous = run.previousVdot {
                    Circle().strokeBorder(Color.muted, lineWidth: 2).background(Circle().fill(Color.card)).frame(width: 8, height: 8)
                        .offset(x: x(previous) - 4, y: 17)
                }
                Group {
                    if paused {
                        Circle().strokeBorder(Color.run, lineWidth: 2.5).background(Circle().fill(Color.card))
                    } else {
                        Circle().fill(Color.run).overlay(Circle().strokeBorder(Color.card, lineWidth: 2.5))
                    }
                }
                .frame(width: 16, height: 16)
                .offset(x: (placed ? x(run.vdot) : 0) - 8, y: 13)
                if let peak = run.peak {
                    RoundedRectangle(cornerRadius: 1).fill(Color.ink).frame(width: 2, height: 22).offset(x: x(peak) - 1, y: 10)
                    Text("PEAK \(Int(peak.rounded()))").font(AppFont.body(10, weight: .semibold)).tracking(0.6).foregroundStyle(Color.inkSoft)
                        .fixedSize()
                        .frame(width: 80)
                        .offset(x: min(x(peak) - 40, w - 80), y: 34)
                }
                Text("\(Int(lo))").font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.subtle).offset(y: 34)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("VDOT \(String(format: "%.1f", run.vdot)) of a peak of \(Int((run.peak ?? 0).rounded()))")
    }
}

#Preview {
    MonthRecapView(month: "2026-10").preferredColorScheme(.dark)
}
