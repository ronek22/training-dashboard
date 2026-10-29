import SwiftUI

/// Full-screen look back at one week. Big numbers count up and cards come in one after another,
/// so it reads as a celebration rather than a report.
struct WeekRecapView: View {
    @State private var model: WeekRecapModel
    @Environment(\.dismiss) private var dismiss

    init(weekStart: String? = nil) {
        _model = State(initialValue: WeekRecapModel(weekStart: weekStart))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if model.offline, let syncedAt = model.syncedAt {
                    Text("Offline · showing \(syncedAt.formatted(date: .abbreviated, time: .shortened)) data")
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                        .padding(.horizontal, 4)
                }
                if let report = model.report {
                    RecapContent(report: report, wins: model.wins)
                        // A new week replays the count-ups and reveals.
                        .id(report.weekStart)
                } else if model.loaded {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not loaded")
                        Text(model.error ?? "No week on the server yet.").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 400)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .overlay(alignment: .top) {
            // Keeps scrolled cards from running under the status bar, as on Today.
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
                weekButton("chevron.left", to: model.report?.previousWeek, label: "Previous week")
                weekButton("chevron.right", to: model.report?.nextWeek, label: "Next week")
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
                Text(model.report.map { $0.finished ? "YOUR WEEK" : "WEEK SO FAR" } ?? "YOUR WEEK")
                    .font(AppFont.title(44))
                    .foregroundStyle(Color.ink)
            }
            .padding(.horizontal, 4)
        }
        .padding(.top, 6)
    }

    private var kicker: String {
        guard let report = model.report else { return " " }
        let range = RecapFormat.range(report.weekStart, report.weekEnd)
        return RecapFormat.weekNumber(report.weekStart).map { "Week \($0) · \(range)" } ?? range
    }

    private func weekButton(_ symbol: String, to week: String?, label: String) -> some View {
        Button {
            if let week { Task { await model.show(week) } }
        } label: {
            Image(systemName: symbol)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(week == nil ? Color.dim : Color.ink)
                .frame(width: 34, height: 34)
                .overlay(Circle().strokeBorder(Color.outline, lineWidth: 1))
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(week == nil)
        .accessibilityLabel(label)
    }
}

// MARK: - Content

private struct RecapContent: View {
    let report: WeekReport
    let wins: WeekWins?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HeroCard(report: report).reveal(0)
            if !RecapFormat.shares(report.totals).isEmpty {
                SportsCard(shares: RecapFormat.shares(report.totals)).reveal(1)
            }
            DaysCard(days: report.days).reveal(2)
            if let wins, !wins.wins.isEmpty {
                WinsCard(wins: wins.wins).reveal(3)
            }
            if (report.plan?.planned ?? 0) > 0 || !report.goals.isEmpty {
                GoalsCard(plan: report.plan, goals: report.goals).reveal(4)
            }
            let vitals = RecapFormat.vitals(report.recovery)
            if !vitals.isEmpty {
                RecoveryCard(vitals: vitals).reveal(5)
            }
            if report.history.count > 1 {
                HistoryCard(history: report.history, fitness: report.fitness).reveal(6)
            }
            if let focus = wins?.focus {
                FocusCard(focus: focus, finished: report.finished).reveal(7)
            }
        }
    }
}

/// Giant moved time, then sessions, distance and climbing.
private struct HeroCard: View {
    let report: WeekReport

    var body: some View {
        let totals = report.totals
        let moved = RecapFormat.movedMinutes(totals)
        VStack(alignment: .leading, spacing: 0) {
            Kicker("Time moving", color: .volt)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                CountUp(value: Double(moved / 60)) { "\(Int($0))" }
                    .font(AppFont.number(96))
                    .foregroundStyle(Color.ink)
                Text("h").font(AppFont.number(34, weight: .semibold)).foregroundStyle(Color.muted)
                CountUp(value: Double(moved % 60), delay: 0.15) { String(format: "%02d", Int($0)) }
                    .font(AppFont.number(96))
                    .foregroundStyle(Color.ink)
                Text("m").font(AppFont.number(34, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.top, -6)
            usualLine.padding(.top, -4)
            HStack(spacing: 0) {
                let count = RecapFormat.activityCount(report)
                stat(Double(count), count == 1 ? "activity" : "activities") { "\(Int($0))" }
                stat(RecapFormat.distanceKm(report), "km") { "\(Int($0.rounded()))" }
                stat(totals.elevationM ?? 0, "m up") { "\(Int($0.rounded()))" }
                stat(Double(totals.activeDays), "active days") { "\(Int($0))/7" }
            }
            .padding(.top, 18)
            if let sick = report.sickDays, sick > 0 {
                Text(sick == 1 ? "1 sick day. Resting was the training." : "\(sick) sick days. Resting was the training.")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted).padding(.top, 12)
            }
        }
        .card()
        .accessibilityElement(children: .combine)
    }

    /// Training against a usual week; a win gets a volt pill, a quiet week just the numbers.
    @ViewBuilder
    private var usualLine: some View {
        if let usual = report.finished ? report.norm?.minutes : report.norm?.minutesToDate {
            let usualText = "usual \(TodayFormat.duration(Int(usual.rounded())))\(report.finished ? "" : " by now")"
            let walks = RecapFormat.movedMinutes(report.totals) > report.totals.minutes
            if let delta = RecapFormat.versusUsual(report), delta > 0 {
                HStack(spacing: 8) {
                    Pill(text: "+\(delta)% training", color: .volt)
                    Text(usualText).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            } else {
                Text("\(walks ? "\(TodayFormat.duration(report.totals.minutes)) training · " : "")\(usualText)")
                    .font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
        }
    }

    private func stat(_ value: Double, _ label: String, format: @escaping (Double) -> String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            CountUp(value: value, delay: 0.3, format: format)
                .font(AppFont.number(28))
                .foregroundStyle(Color.ink)
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// One stacked bar of the week by sport, then a row per sport.
private struct SportsCard: View {
    let shares: [RecapFormat.SportShare]
    @State private var grown = false

    var body: some View {
        let total = Double(max(shares.map(\.minutes).reduce(0, +), 1))
        VStack(alignment: .leading, spacing: 14) {
            Kicker("By sport")
            GeometryReader { proxy in
                HStack(spacing: 3) {
                    ForEach(shares) { share in
                        RoundedRectangle(cornerRadius: 4)
                            .fill(share.sport.color)
                            .frame(width: max(4, (proxy.size.width - 3 * Double(shares.count - 1)) * Double(share.minutes) / total))
                    }
                }
                .frame(width: grown ? proxy.size.width : 0, alignment: .leading)
                .clipped()
            }
            .frame(height: 14)
            VStack(spacing: 10) {
                ForEach(shares) { share in
                    HStack(spacing: 10) {
                        Image(systemName: share.sport.symbol)
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(share.sport.color)
                            .frame(width: 28, height: 28)
                            .background(share.sport.color.opacity(0.14), in: Circle())
                        Text(share.label).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink)
                        Text(share.sessions == 1 ? "1 session" : "\(share.sessions) sessions")
                            .font(AppFont.body(12)).foregroundStyle(Color.muted)
                        Spacer()
                        Text(TodayFormat.duration(share.minutes)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                    }
                }
            }
        }
        .card()
        .onAppear { withAnimation(.easeOut(duration: 0.9).delay(0.35)) { grown = true } }
    }
}

/// Seven columns: how long each day was, coloured by sport, with tags like Mountains.
private struct DaysCard: View {
    let days: [WeekReport.Day]
    @State private var grown = false

    var body: some View {
        let totals = days.map { RecapFormat.daySegments($0).reduce(0) { $0 + $1.minutes } }
        let peak = Double(max(totals.max() ?? 0, 1))
        VStack(alignment: .leading, spacing: 12) {
            Kicker("Day by day")
            HStack(alignment: .bottom, spacing: 8) {
                ForEach(Array(days.enumerated()), id: \.element.id) { index, day in
                    column(day, total: totals[index], peak: peak, index: index)
                }
            }
            let tags = Array(Set(days.flatMap { $0.tags ?? [] })).sorted()
            if !tags.isEmpty {
                HStack(spacing: 6) {
                    ForEach(tags, id: \.self) { Pill(text: $0, color: .other) }
                }
            }
        }
        .card()
        .onAppear { grown = true }
    }

    private func column(_ day: WeekReport.Day, total: Int, peak: Double, index: Int) -> some View {
        let segments = RecapFormat.daySegments(day)
        let height = 110.0
        return VStack(spacing: 6) {
            Text(total > 0 ? TodayFormat.duration(total) : " ")
                .font(AppFont.number(12, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .opacity(grown ? 1 : 0)
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 6).fill(Color.inset).frame(height: height)
                if day.sick == true {
                    Image(systemName: "cross.case.fill").font(.system(size: 12)).foregroundStyle(Color.warning).padding(.bottom, 8)
                } else if total == 0 && !day.future {
                    Circle().fill(Color.dim).frame(width: 5, height: 5).padding(.bottom, 8)
                }
                VStack(spacing: 2) {
                    ForEach(Array(segments.reversed().enumerated()), id: \.offset) { _, part in
                        Rectangle()
                            .fill(part.sport.color)
                            .frame(height: max(4, (height - 2 * Double(segments.count - 1)) * Double(part.minutes) / peak))
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .scaleEffect(y: grown ? 1 : 0.02, anchor: .bottom)
                .animation(.spring(duration: 0.7, bounce: 0.25).delay(0.4 + Double(index) * 0.07), value: grown)
            }
            Text(RecapFormat.dayLetter(day.date))
                .font(AppFont.body(11, weight: .semibold))
                .foregroundStyle(day.future ? Color.dim : Color.muted)
        }
        .frame(maxWidth: .infinity)
        .animation(.easeOut.delay(0.6 + Double(index) * 0.07), value: grown)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(day.date): \(total > 0 ? TodayFormat.duration(total) : "rest")")
    }
}

private struct WinsCard: View {
    let wins: [WeekWins.Win]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Kicker(wins.count == 1 ? "The win" : "\(wins.count) wins", color: .volt)
            ForEach(Array(wins.enumerated()), id: \.offset) { index, win in
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: RecapFormat.winSymbol(win.kind))
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(Color.bg)
                        .frame(width: 36, height: 36)
                        .background(Color.volt, in: Circle())
                    VStack(alignment: .leading, spacing: 3) {
                        Text(win.headline).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                        if let detail = win.detail {
                            Text(detail).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                        }
                    }
                    .fixedSize(horizontal: false, vertical: true)
                }
                .reveal(index, base: 0.5)
            }
        }
        .card(border: Color.volt.opacity(0.35))
    }
}

/// The plan as a ring, then each weekly goal as a bar; the anchor goal is marked.
private struct GoalsCard: View {
    let plan: WeekReport.PlanDone?
    let goals: [WeekReport.Goal]
    @State private var grown = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Kicker("Plan and goals")
            if let plan, plan.planned > 0 {
                HStack(spacing: 14) {
                    ring(Double(plan.done) / Double(plan.planned), color: plan.done >= plan.planned ? .volt : .ride)
                        .frame(width: 58, height: 58)
                        .overlay {
                            Text("\(plan.done)/\(plan.planned)").font(AppFont.number(18)).foregroundStyle(Color.ink)
                        }
                    VStack(alignment: .leading, spacing: 3) {
                        Text(plan.done >= plan.planned ? "Every planned session done" : "\(plan.done) of \(plan.planned) planned sessions")
                            .font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                        if let title = plan.title {
                            Text(title).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(2)
                        }
                    }
                }
            }
            ForEach(goals) { goal in
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        if goal.met {
                            Image(systemName: "checkmark.circle.fill").font(.system(size: 13)).foregroundStyle(Color.volt)
                        }
                        Text(goal.title).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink)
                        if goal.anchor == true {
                            Text("ANCHOR").font(AppFont.body(9, weight: .bold)).tracking(0.9).foregroundStyle(Color.strength)
                        }
                        Spacer()
                        Text("\(RecapFormat.number(goal.done)) / \(RecapFormat.number(goal.target))")
                            .font(AppFont.number(16)).foregroundStyle(goal.met ? Color.volt : Color.inkSoft)
                    }
                    GeometryReader { proxy in
                        Capsule().fill(Color.track)
                            .overlay(alignment: .leading) {
                                Capsule()
                                    .fill(goal.met ? Color.volt : goal.anchor == true ? Color.strength : Color.ride)
                                    .frame(width: grown ? proxy.size.width * min(goal.done / max(goal.target, 0.001), 1) : 0)
                            }
                    }
                    .frame(height: 6)
                }
            }
        }
        .card()
        .onAppear { withAnimation(.easeOut(duration: 0.9).delay(0.4)) { grown = true } }
    }

    private func ring(_ share: Double, color: Color) -> some View {
        ZStack {
            Circle().stroke(Color.track, lineWidth: 6)
            Circle()
                .trim(from: 0, to: grown ? min(share, 1) : 0)
                .stroke(color, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

private struct RecoveryCard: View {
    let vitals: [RecapFormat.VitalChange]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker("How the body took it")
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                ForEach(vitals) { vital in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(vital.title).font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.muted)
                        HStack(alignment: .firstTextBaseline, spacing: 3) {
                            Text(vital.value).font(AppFont.number(26)).foregroundStyle(Color.ink)
                            Text(vital.unit).font(AppFont.body(11)).foregroundStyle(Color.muted)
                        }
                        Text(vital.change).font(AppFont.body(11, weight: .semibold)).foregroundStyle(color(vital.mood))
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
        }
        .card()
    }

    private func color(_ mood: RecapFormat.VitalChange.Mood) -> Color {
        switch mood {
        case .better: .mobility
        case .worse: .warning
        case .steady: .muted
        }
    }
}

/// Training time for the last eight weeks, this one in volt.
private struct HistoryCard: View {
    let history: [WeekReport.HistoryWeek]
    let fitness: WeekReport.Fitness?
    @State private var grown = false

    var body: some View {
        let peak = Double(max(history.map(\.minutes).max() ?? 0, 1))
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("Last \(history.count) weeks")
                Spacer()
                if let start = fitness?.start, let end = fitness?.end {
                    let delta = Int(end.rounded()) - Int(start.rounded())
                    Text("Fitness \(Int(start.rounded())) → \(Int(end.rounded()))")
                        .font(AppFont.body(12, weight: .semibold))
                        .foregroundStyle(delta > 0 ? Color.mobility : Color.muted)
                }
            }
            HStack(alignment: .bottom, spacing: 6) {
                ForEach(Array(history.enumerated()), id: \.element.id) { index, week in
                    VStack(spacing: 5) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(week.current ? Color.volt : Color.raised)
                            .frame(height: max(4, 70 * Double(week.minutes) / peak))
                            .scaleEffect(y: grown ? 1 : 0.02, anchor: .bottom)
                            .animation(.spring(duration: 0.6, bounce: 0.2).delay(0.3 + Double(index) * 0.05), value: grown)
                        Text(TodayFormat.duration(week.minutes))
                            .font(AppFont.number(10, weight: .semibold))
                            .foregroundStyle(week.current ? Color.volt : Color.faint)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .frame(height: 92, alignment: .bottom)
            Text("Training time; walks and hikes not counted.").font(AppFont.body(11)).foregroundStyle(Color.faint)
        }
        .card()
        .onAppear { grown = true }
    }
}

private struct FocusCard: View {
    let focus: WeekWins.Focus
    let finished: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(finished ? "Next week" : "Before Sunday", color: .ride)
            Text(focus.headline).font(AppFont.title(26)).foregroundStyle(Color.ink).textCase(.uppercase)
            if let detail = focus.detail {
                Text(detail).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).fixedSize(horizontal: false, vertical: true)
            }
        }
        .card()
    }
}

#Preview {
    WeekRecapView().preferredColorScheme(.dark)
}
