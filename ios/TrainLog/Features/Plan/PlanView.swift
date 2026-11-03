import SwiftUI

struct PlanView: View {
    let onStartStrength: (StrengthLaunch) -> Void
    @State private var model: PlanModel
    @State private var coach: PlanCoachModel
    @State private var path: [String] = []
    @State private var moving: PlanDay?
    @State private var asking: CoachContext?
    @State private var coachOpen = false

    init(onStartStrength: @escaping (StrengthLaunch) -> Void) {
        self.onStartStrength = onStartStrength
        let model = PlanModel()
        _model = State(initialValue: model)
        _coach = State(initialValue: PlanCoachModel(plans: model))
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                header.plainRow(top: 0)
                if model.offline, let syncedAt = model.syncedAt {
                    OfflineNote(syncedAt: syncedAt)
                        .plainRow()
                }
                if let week = model.week {
                    WeekSummaryCard(week: week, today: model.today).plainRow()
                    if coach.isRunning(for: week.weekStart) {
                        CoachRunningLine(coach: coach) { coachOpen = true }.plainRow()
                    }
                    Section {
                        ForEach(PlanFormat.slots(week)) { slot in
                            row(slot)
                        }
                    }
                    if week.weekStart == model.weeks.last?.weekStart, let next = model.unplannedStart {
                        Button {
                            model.page(1)
                        } label: {
                            HStack(spacing: 4) {
                                Text("Week \(PlanCoachFormat.weekNumber(next)) isn't planned ·")
                                Text("Plan it").foregroundStyle(Color.ink).fontWeight(.semibold)
                                Image(systemName: "chevron.right").font(.system(size: 10, weight: .bold))
                            }
                            .font(AppFont.body(13))
                            .foregroundStyle(Color.muted)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .plainRow()
                    }
                } else if model.showingUnplanned, let start = model.selected {
                    UnplannedWeekCard(weekStart: start, coach: coach, onPlan: { openCoach(.plan(week: start)) },
                                      onOpen: { coachOpen = true })
                        .plainRow()
                    if let last = model.weeks.last {
                        HStack {
                            Text("Last week").font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                            Spacer()
                            Text(PlanCoachFormat.weekLine(last)).font(AppFont.body(12)).foregroundStyle(Color.muted)
                        }
                        .padding(.horizontal, 6)
                        .plainRow()
                    }
                } else if model.loaded {
                    emptyCard.plainRow()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300).plainRow()
                }
            }
            .listStyle(.insetGrouped)
            .listSectionSpacing(12)
            .scrollContentBackground(.hidden)
            .scrollIndicators(.hidden)
            .contentMargins(.horizontal, 16, for: .scrollContent)
            .contentMargins(.top, 0, for: .scrollContent)
            .background(Color.bg)
            .toolbar(.hidden, for: .navigationBar)
            .navigationTitle("Plan")
            .smoothRefreshable {
                await APIClient.current.reconnect()
                await model.load()
            }
            .task {
                await model.load()
                coach.resume()
                #if DEBUG
                if let stage = PlanCoachModel.demoStage {
                    // Planning stages show the unsaved week behind the sheet; refine stages the current one.
                    if !["refine", "changed", "day"].contains(stage), let next = model.unplannedStart { model.select(next) }
                    coach.startDemo(week: model.week, unplanned: model.unplannedStart)
                    coachOpen = stage != "card"
                }
                #endif
            }
            .navigationDestination(for: String.self) { date in
                PlanDayView(model: model, date: date, onMove: { moving = $0 },
                            onChange: { day in openCoach(.day(week: PlanFormat.weekStart(of: day.date), date: day.date)) },
                            onStartStrength: onStartStrength)
                    .hidesTabBar()
            }
        }
        .tint(.volt)
        .sheet(isPresented: $coachOpen) {
            PlanCoachSheet(coach: coach, week: coach.task.flatMap { task in model.weeks.first { $0.weekStart == task.week } },
                           today: model.today,
                           onRefine: { if let week = coach.task?.week { coach.open(.refine(week: week)) } })
                .presentationDetents([.large])
                .presentationBackground(Color.sheet)
        }
        .sheet(item: $asking) { context in
            CoachChatView(context: context)
                .presentationDetents([.large])
                .presentationBackground(Color.bg)
        }
        .sheet(item: $moving) { day in
            if let week = model.week {
                MoveDaySheet(source: day, slots: PlanFormat.slots(week), today: model.today) { target in
                    let error = await model.move(from: day.date, to: target)
                    if error == nil, path.last == day.date { path.removeLast() }
                    return error
                }
                .presentationDetents([.height(470)])
                .presentationBackground(Color.sheet)
            }
        }
    }

    @ViewBuilder
    private func row(_ slot: PlanSlot) -> some View {
        // A button rather than a NavigationLink: the artboard's rows have the ring, not a chevron.
        Button {
            path.append(slot.date)
        } label: {
            PlanRow(slot: slot, today: model.today).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(slot.day == nil)
        .listRowBackground(Color.card)
        .listRowSeparatorTint(Color.cardBorder)
        .listRowInsets(EdgeInsets(top: 0, leading: 14, bottom: 0, trailing: 14))
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            if PlanFormat.canMove(slot.day, today: model.today), let day = slot.day {
                Button {
                    moving = day
                } label: {
                    Label("Move", systemImage: "arrow.left.arrow.right")
                }
                .tint(Color.other)
            }
        }
    }

    private var header: some View {
        ScreenHeader(kicker: model.selected.map(PlanFormat.weekKicker) ?? " ", title: "Plan") {
            HStack(spacing: 8) {
                if let week = model.week, coach.isRunning(for: week.weekStart) || !PlanCoachFormat.editableDates(week, today: model.today).isEmpty {
                    Button {
                        if coach.isRunning(for: week.weekStart) { coachOpen = true } else { openCoach(.refine(week: week.weekStart)) }
                    } label: {
                        ZStack {
                            if coach.isRunning(for: week.weekStart) {
                                ProgressView().controlSize(.small).tint(.volt)
                            } else {
                                Image(systemName: "sparkles").font(.system(size: 14, weight: .semibold)).foregroundStyle(Color.volt)
                            }
                        }
                        .frame(width: 36, height: 36)
                        .overlay(Circle().strokeBorder(Color.outline))
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Refine this week with the coach")
                }
                if let week = model.week {
                    HeaderIconButton(label: "Ask coach about this week") {
                        asking = CoachFormat.weekContext(week.weekStart)
                    } icon: {
                        Image(systemName: "bubble.left.and.bubble.right").font(.system(size: 13, weight: .semibold))
                    }
                }
                HeaderIconButton(enabled: model.hasPrevious, label: "Previous week") { model.page(-1) } icon: {
                    Image(systemName: "chevron.left")
                }
                HeaderIconButton(enabled: model.hasNext, label: "Next week") { model.page(1) } icon: {
                    Image(systemName: "chevron.right")
                }
            }
            .padding(.bottom, 4)
        }
    }

    private func openCoach(_ task: PlanCoachTask) {
        coach.open(task)
        coachOpen = true
    }

    private var emptyCard: some View {
        SyncStateCard(kicker: model.error == nil ? "No plan yet" : "Not synced yet",
                      message: model.error ?? "There's no weekly plan on the server.")
    }
}

/// The week's headline, focus and how much of it is done.
private struct WeekSummaryCard: View {
    let week: WeeklyPlan
    let today: String

    var body: some View {
        let summary = PlanFormat.summary(week, today: today)
        VStack(alignment: .leading, spacing: 0) {
            if let title = PlanFormat.shortTitle(week.title) {
                Text(title.uppercased()).font(AppFont.title(22)).foregroundStyle(Color.ink)
            }
            if let focus = week.focus, !focus.isEmpty {
                Text(focus)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.muted)
                    .lineSpacing(2)
                    .lineLimit(3)
                    .padding(.top, 5)
            }
            HStack(alignment: .firstTextBaseline) {
                Text("\(Text("\(summary.done)").foregroundStyle(Color.ink).bold()) of \(summary.sessions) done")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                Spacer()
                let done = Text(TodayFormat.duration(summary.doneMinutes)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                let planned = Text(" of \(TodayFormat.duration(summary.plannedMinutes))").font(AppFont.body(12)).foregroundStyle(Color.muted)
                Text("\(done)\(planned)")
            }
            .padding(.top, 12)
            progressBar(summary).padding(.top, 8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func progressBar(_ summary: PlanFormat.Summary) -> some View {
        GeometryReader { geo in
            let total = Double(max(summary.plannedMinutes, summary.doneMinutes, 1))
            HStack(spacing: 2) {
                ForEach(summary.bySport, id: \.sport) { part in
                    Rectangle().fill(part.sport.color).frame(width: geo.size.width * Double(part.minutes) / total)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(height: 6)
        .background(Color.track)
        .clipShape(Capsule())
    }
}

/// The week after the newest saved one: seven dashed slots and the one volt action, Plan with coach.
private struct UnplannedWeekCard: View {
    let weekStart: String
    let coach: PlanCoachModel
    let onPlan: () -> Void
    let onOpen: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker("Not planned yet")
            Text("PLAN WEEK \(PlanCoachFormat.weekNumber(weekStart))").font(AppFont.title(30)).foregroundStyle(Color.ink)
                .padding(.top, 8)
                .padding(.bottom, 14)
            PlanWeekStrip(days: PlanCoachFormat.ghost(weekStart), showMinutes: false, pending: coach.isRunning(for: weekStart))
            if coach.isRunning(for: weekStart) {
                CoachRunningLine(coach: coach, action: onOpen).padding(.top, 14)
            } else {
                Text("The coach reads this week, your readiness and recovery, then writes all seven days. Tell it anything that's different next week.")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.top, 14)
                Button(action: onPlan) {
                    Label("Plan with coach", systemImage: "sparkles")
                }
                .buttonStyle(VoltButtonStyle())
                .padding(.top, 16)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
    }
}

/// "Coach is planning · 2:10 · Open": the job keeps running after the sheet closes.
struct CoachRunningLine: View {
    let coach: PlanCoachModel
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                ProgressView().controlSize(.small).tint(.volt)
                TimelineView(.periodic(from: .now, by: 1)) { context in
                    Text("\(verb) · \(PlanCoachFormat.clock(Int(context.date.timeIntervalSince(coach.startedAt ?? context.date))))")
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.inkBody)
                        .monospacedDigit()
                }
                Spacer()
                Text("Open").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.inkSoft)
            }
            .padding(.horizontal, 4)
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var verb: String {
        switch coach.task {
        case .plan: "Coach is planning"
        case .day: "Coach is changing a day"
        default: "Coach is refining"
        }
    }
}

/// Day column, sport bar, title and meta, then the same ring as Today's week.
struct PlanRow: View {
    let slot: PlanSlot
    let today: String

    var body: some View {
        let status = PlanFormat.status(slot.day, today: today)
        let isToday = slot.date == today
        let sport = slot.day.map(PlanFormat.sport) ?? .rest
        HStack(spacing: 12) {
            VStack(spacing: 2) {
                Text(weekday)
                    .font(AppFont.body(10, weight: isToday ? .bold : .semibold))
                    .tracking(1)
                    .foregroundStyle(isToday ? Color.volt : Color.muted)
                Text(dayNumber).font(AppFont.number(20)).foregroundStyle(isToday ? Color.volt : Color.ink)
            }
            .frame(width: 30)
            RoundedRectangle(cornerRadius: 2).fill(sport.color).frame(width: 4, height: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text(slot.day.map { PlanFormat.rowTitle($0.title) } ?? "Free day")
                    .font(AppFont.body(15, weight: .semibold))
                    .foregroundStyle(slot.day == nil ? Color.muted : Color.ink)
                    .lineLimit(1)
                if let day = slot.day {
                    Text(PlanFormat.meta(day, today: today))
                        .font(AppFont.body(12))
                        .foregroundStyle(status == .missed ? Color.warning : Color.muted)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            PlanRing(status: status, sport: sport, isToday: isToday)
        }
        .padding(.vertical, 10)
        .frame(minHeight: 58)
        // Past finished days step back so the rest of the week reads first.
        .opacity(slot.date < today && status != .missed ? 0.62 : 1)
        .accessibilityElement(children: .combine)
    }

    private var weekday: String {
        FoodFormat.parse(slot.date)?.formatted(.dateTime.weekday(.abbreviated).locale(Locale(identifier: "en_GB"))).uppercased() ?? ""
    }

    private var dayNumber: String {
        FoodFormat.parse(slot.date).map { "\(ActivityFormat.mondayCalendar.component(.day, from: $0))" } ?? ""
    }
}

/// Filled = done, outline = planned, volt ring around it = today.
struct PlanRing: View {
    let status: PlanDayStatus
    let sport: Sport
    let isToday: Bool

    var body: some View {
        ZStack {
            switch status {
            case .done:
                Circle().fill(sport.color)
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.bg)
            case .replaced:
                Circle().fill(Color.raised)
                Image(systemName: "arrow.left.arrow.right").font(.system(size: 10, weight: .bold)).foregroundStyle(Color.muted)
            case .skipped, .missed:
                Circle().strokeBorder(Color.dim, lineWidth: 2)
                Image(systemName: "xmark").font(.system(size: 9, weight: .bold)).foregroundStyle(Color.faint)
            case .planned:
                Circle().strokeBorder(sport.color.opacity(0.45), lineWidth: 2)
            case .rest:
                Circle().fill(Color.dim).frame(width: 5, height: 5)
            }
        }
        .frame(width: 26, height: 26)
        .padding(4)
        .overlay {
            if isToday { Circle().strokeBorder(Color.volt, lineWidth: 2) }
        }
    }
}

