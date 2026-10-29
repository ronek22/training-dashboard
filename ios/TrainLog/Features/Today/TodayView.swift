import SwiftUI

struct TodayView: View {
    @State private var model = TodayModel()
    @Environment(\.scenePhase) private var scenePhase
    @State private var showFallback = false
    @State private var showSettings = false
    @State private var showBody = false
    @State private var showCheckin = false
    /// The plan week behind today's card: steps, rehab ticks and Move day come from it.
    @State private var plan = PlanModel()
    @State private var route: Route?
    @State private var moving: PlanDay?
    @State private var showRehab = false
    var onStartStrength: (Int?) -> Void = { _ in }
    /// Bumped when the strength screen closes, so the banner and plan reload.
    var refresh = 0

    var body: some View {
        NavigationStack {
            content
                .toolbar(.hidden, for: .navigationBar)
                .navigationTitle("Today")
                .navigationDestination(isPresented: $showSettings) { SettingsView().hidesTabBar() }
                .navigationDestination(isPresented: $showBody) { BodyView().hidesTabBar() }
                // One destination for both: two stacked ones on the same view push the wrong screen.
                .navigationDestination(item: $route) { route in
                    if let date = model.data?.date {
                        switch route {
                        case .day:
                            PlanDayView(model: plan, date: date, onMove: { moving = $0 }, onStartStrength: onStartStrength)
                                .hidesTabBar()
                        }
                    }
                }
        }
        .tint(.volt)
        .fullScreenCover(isPresented: $showRehab, onDismiss: { Task { await load() } }) {
            RehabSessionView()
        }
        .sheet(item: $moving) { day in
            if let week = plan.weeks.first(where: { $0.days.contains { $0.date == day.date } }) {
                MoveDaySheet(source: day, slots: PlanFormat.slots(week), today: plan.today) { target in
                    let error = await plan.move(from: day.date, to: target)
                    if error == nil {
                        route = nil
                        await model.load()
                    }
                    return error
                }
                .presentationDetents([.height(470)])
                .presentationBackground(Color(hex: 0x161A22))
            }
        }
        .onChange(of: showSettings) {
            // Back from Settings may have pointed the app at another server.
            if !showSettings { Task { await load() } }
        }
    }

    private enum Route: Hashable {
        case day
    }

    private func load() async {
        async let today: Void = model.load()
        async let week: Void = plan.load()
        _ = await (today, week)
    }

    private var content: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if let workout = model.activeWorkout {
                    ResumeWorkoutCard(workout: workout) { onStartStrength(nil) }
                }
                if let data = model.data {
                    if model.offline, let syncedAt = model.syncedAt {
                        offlineNote(syncedAt)
                    }
                    SessionCard(
                        data: data,
                        planDay: plan.day(data.date),
                        today: plan.today,
                        showFallback: $showFallback,
                        rehabPending: model.rehabPending,
                        workoutOpen: model.activeWorkout != nil,
                        onStartStrength: onStartStrength,
                        onOpen: { route = .day },
                        onRehab: { showRehab = true },
                        onMove: { moving = $0 }
                    )
                    ReadinessCard(readiness: data.readiness, vitals: data.vitals, checkinDone: data.checkinDone,
                                  onOpen: { showBody = true }, onCheckin: { showCheckin = true })
                    WeekCard(week: data.week, minutes: data.weekMinutes, today: data.date)
                } else if let error = model.error {
                    errorCard(error)
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .overlay(alignment: .top) {
            // Keeps scrolled cards from running under the status bar. An overlay, not a
            // safeAreaInset: an inset fights the refresh control and makes the pull snap back.
            Color.bg.frame(height: 0).background(Color.bg).allowsHitTesting(false)
        }
        .background(Color.bg)
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await load()
        }
        .task(id: refresh) { await load() }
        .sheet(isPresented: $showCheckin, onDismiss: { Task { await model.load() } }) {
            QuickLogSheet()
                .presentationDetents([.large])
                .presentationBackground(Color.card)
        }
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await model.refreshWorkout()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(model.data.map { TodayFormat.dateKicker($0.date) } ?? " ")
                Text("TODAY").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            HStack(spacing: 8) {
                if let streak = model.data?.streakDays, streak > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "flame.fill").font(.system(size: 12))
                        Text("\(streak)").font(AppFont.body(13, weight: .bold))
                    }
                    .foregroundStyle(Color.volt)
                    .padding(.horizontal, 10)
                    .frame(height: 26)
                    .background(Color.volt.opacity(0.12), in: Capsule())
                    .accessibilityLabel("\(streak) day streak")
                }
                Button {
                    showSettings = true
                } label: {
                    Text("J")
                        .font(AppFont.body(14, weight: .bold))
                        .foregroundStyle(Color.ink)
                        .frame(width: 34, height: 34)
                        .background(Color.raised, in: Circle())
                        .frame(width: 44, height: 44)
                        .contentShape(Circle())
                }
                .buttonStyle(.plain)
                .padding(-5)
                .accessibilityLabel("Settings")
            }
            .padding(.bottom, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func offlineNote(_ syncedAt: Date) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "wifi.slash").font(.system(size: 11, weight: .semibold))
            Text("Offline · last synced \(syncedAt.formatted(date: .omitted, time: .shortened))")
                .font(AppFont.body(12, weight: .medium))
        }
        .foregroundStyle(Color.muted)
        .padding(.horizontal, 4)
    }

    private func errorCard(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Not synced yet")
            Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text("Start the backend on the Mac (docker compose up) and pull to refresh.")
                .font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

// MARK: - Session

private struct SessionCard: View {
    let data: PhoneToday
    /// The same day from the plan week; nil until it loads (or offline with no cache).
    let planDay: PlanDay?
    let today: String
    @Binding var showFallback: Bool
    let rehabPending: Int?
    /// The Resume banner owns the volt action while a workout is open.
    let workoutOpen: Bool
    let onStartStrength: (Int?) -> Void
    let onOpen: () -> Void
    let onRehab: () -> Void
    let onMove: (PlanDay) -> Void

    var body: some View {
        if let session = data.today, session.sport != .rest {
            planned(session)
        } else {
            restDay
        }
    }

    /// Today's rehab from the plan day: exercises ticked, and still due (from the guided session,
    /// which leaves out off-day ones; the plan's own count when that's unknown).
    private var rehab: (done: Int, left: Int, title: String)? {
        guard let routines = planDay?.rehab, !routines.isEmpty else { return nil }
        let done = routines.reduce(0) { $0 + $1.ticked.count }
        let total = routines.reduce(0) { $0 + $1.exercises.count }
        return (done, rehabPending ?? max(0, total - done), routines.map(\.title).joined(separator: " · "))
    }

    private func planned(_ session: PhoneToday.Session) -> some View {
        let sport = session.sport ?? .other
        let fallback = PlanFormat.fallback(session.fallback)
        let canMove = PlanFormat.canMove(planDay, today: today)
        let rehab = self.rehab
        // A rehab-only day is the routine itself; any other day with rehab has two parts.
        let rehabOnly = sport == .mobility && rehab != nil
        let next = TodayFormat.next(isStrength: session.strength != nil, rehabOnly: rehabOnly,
                                    mainDone: session.isDone, rehabLeft: rehab?.left)
        return VStack(alignment: .leading, spacing: 0) {
            // Tapping the top half opens the full day: steps, cues, go-check.
            Button(action: onOpen) { header(session, sport: sport).contentShape(Rectangle()) }
                .buttonStyle(.plain)
                .accessibilityHint("Opens the full session")

            // Once the main part is in, the card is about what's left. Two-part days list the parts
            // instead; the steps are one tap away under Open session.
            if !session.isDone, rehab == nil {
                if let exercises = session.strength?.exercises, !exercises.isEmpty {
                    numberedList(exercises.map { ($0.name, TodayFormat.exerciseTarget($0)) }, color: sport.color)
                        .padding(.top, 14)
                } else if let steps = planDay?.steps, !steps.isEmpty, !rehabOnly {
                    numberedList(steps.map { ($0, nil) }, color: sport.color, limit: 2).padding(.top, 14)
                } else if let details = session.details {
                    Text(details)
                        .font(AppFont.body(14))
                        .foregroundStyle(Color.inkSoft)
                        .lineSpacing(3)
                        .lineLimit(4)
                        .padding(.top, 12)
                }
            }

            if showFallback, let fallback, !session.isDone {
                Text("\(Text("Short on time: ").foregroundStyle(Color.ink).bold())\(fallback)")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.warning.opacity(0.35)))
                    .padding(.top, 12)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }

            if let rehab {
                VStack(spacing: 8) {
                    if !rehabOnly {
                        mainPart(session, sport: sport)
                    }
                    rehabPart(rehab, number: rehabOnly ? nil : 2, after: rehabOnly || session.isDone ? nil : sport)
                }
                .padding(.top, 14)
            }

            if next == .allDone {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                    Text("Done today").font(AppFont.body(15, weight: .bold))
                }
                .foregroundStyle(Color.volt)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Color.volt.opacity(0.12), in: Capsule())
                .padding(.top, 16)
            } else if !workoutOpen {
                primary(next, session: session)
                if !session.isDone, fallback != nil || canMove {
                    HStack(spacing: 8) {
                        if fallback != nil {
                            Button {
                                withAnimation(.snappy) { showFallback.toggle() }
                            } label: {
                                Label(showFallback ? "Full session" : "Short on time",
                                      systemImage: showFallback ? "arrow.uturn.backward" : "timer")
                            }
                            .buttonStyle(OutlineButtonStyle(height: 44))
                        }
                        if canMove, let planDay {
                            Button {
                                onMove(planDay)
                            } label: {
                                Label("Move day", systemImage: "arrow.left.arrow.right")
                            }
                            .buttonStyle(OutlineButtonStyle(height: 44))
                        }
                    }
                    .padding(.top, 10)
                }
            }
        }
        .card(border: sport.color.opacity(0.35))
    }

    private func header(_ session: PhoneToday.Session, sport: Sport) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: sport.symbol)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(sport.color)
                    .frame(width: 34, height: 34)
                    .background(sport.color.opacity(0.14), in: Circle())
                Kicker(kicker(session, sport: sport), color: sport.color)
                    .lineLimit(1)
                Spacer(minLength: 8)
                target(session)
            }
            Text((session.title ?? "Session").uppercased())
                .font(AppFont.title(28))
                .foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 12)
            if let meta = meta(session) {
                Text(meta).font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 4)
            }
        }
    }

    /// The day's size, big on the right: minutes, then km when there's a distance.
    @ViewBuilder
    private func target(_ session: PhoneToday.Session) -> some View {
        if let km = session.distanceKm, km > 0 {
            bigNumber(TodayFormat.number(km), unit: "km")
        } else if let minutes = session.durationMin {
            bigNumber("\(minutes)", unit: "min")
        }
    }

    private func bigNumber(_ value: String, unit: String) -> some View {
        Text("\(Text(value).font(AppFont.number(26)).foregroundStyle(Color.ink))\(Text(" \(unit)").font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.muted))")
            .lineLimit(1)
            .fixedSize()
    }

    /// The volt follows the part that's next: the lift or the ride's steps, then the rehab.
    private func primary(_ next: TodayFormat.Next, session: PhoneToday.Session) -> some View {
        Group {
            switch next {
            case .startStrength:
                Button {
                    onStartStrength(session.strength?.templateId)
                } label: {
                    Label("Start session", systemImage: "play.fill")
                }
            case .startRehab:
                Button(action: onRehab) {
                    Label("Start rehab", systemImage: "play.fill")
                }
            case .openSession, .allDone:
                Button(action: onOpen) {
                    Label("Open session", systemImage: "list.bullet")
                }
            }
        }
        .buttonStyle(VoltButtonStyle())
        .padding(.top, 16)
    }

    /// Part 1 of a two-part day: recorded on the Watch, ticked here once it syncs.
    private func mainPart(_ session: PhoneToday.Session, sport: Sport) -> some View {
        let done = session.isDone
        let size = session.durationMin.map { "\($0) min" }
        return Button(action: onOpen) {
            partRow(
                badge: AnyView(partBadge(number: 1, done: done, color: sport.color)),
                title: [sport.label, size].compactMap { $0 }.joined(separator: " · "),
                subtitle: done ? "Done · synced" : "Record it on your Watch",
                dimmed: done
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(sport.label), \(done ? "done" : "to do")")
    }

    /// The rehab part; opens the guided session (its first screen lists the exercises).
    private func rehabPart(_ rehab: (done: Int, left: Int, title: String), number: Int?, after sport: Sport?) -> some View {
        let total = rehab.done + rehab.left
        let complete = rehab.left == 0
        let ring = ZStack {
            Circle().stroke(Color.track, lineWidth: 3)
            Circle()
                .trim(from: 0, to: total == 0 ? 0 : Double(rehab.done) / Double(total))
                .stroke(Color.mobility, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(-90))
            if complete {
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.mobility)
            } else if let number {
                Text("\(number)").font(AppFont.number(15)).foregroundStyle(Color.mobility)
            }
        }
        .frame(width: 28, height: 28)
        let title = complete ? "Rehab done" : "Rehab · \(rehab.left) to do"
        let subtitle = sport.map { "After the \($0.label.lowercased()) · \(rehab.title)" } ?? rehab.title
        return Button(action: onRehab) {
            partRow(badge: AnyView(ring), title: title, subtitle: subtitle, dimmed: complete)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(complete ? "Rehab done" : "Rehab, \(rehab.left) exercises to do")
        .accessibilityHint("Opens the guided rehab session")
    }

    private func partBadge(number: Int, done: Bool, color: Color) -> some View {
        ZStack {
            if done {
                Circle().fill(color)
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.bg)
            } else {
                Circle().strokeBorder(color, lineWidth: 2)
                Text("\(number)").font(AppFont.number(15)).foregroundStyle(color)
            }
        }
        .frame(width: 28, height: 28)
    }

    private func partRow(badge: AnyView, title: String, subtitle: String, dimmed: Bool) -> some View {
        HStack(spacing: 12) {
            badge
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(AppFont.body(14, weight: .semibold))
                    .foregroundStyle(dimmed ? Color.inkSoft : Color.ink)
                Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
            }
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.faint)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(minHeight: 44)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
        .contentShape(Rectangle())
    }

    private var restDay: some View {
        VStack(alignment: .leading, spacing: 0) {
            Pill(text: "Rest day", color: .muted)
            Text("RECOVER").font(AppFont.title(30)).foregroundStyle(Color.ink).padding(.top, 12)
            if let tomorrow = data.tomorrow, let title = tomorrow.title {
                Text("Tomorrow: \(title)").font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 4)
            }
        }
        .card()
    }

    private func numberedList(_ rows: [(String, String?)], color: Color, limit: Int = 3) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(rows.prefix(limit).enumerated()), id: \.offset) { index, row in
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(String(format: "%02d", index + 1))
                        .font(AppFont.number(16))
                        .foregroundStyle(color)
                        .frame(width: 22, alignment: .leading)
                    Text(row.0).font(AppFont.body(14)).foregroundStyle(Color.ink)
                        .lineLimit(row.1 == nil ? 2 : 1)
                    Spacer(minLength: 8)
                    if let trailing = row.1 {
                        Text(trailing).font(AppFont.body(14)).foregroundStyle(Color.muted)
                    }
                }
            }
            if rows.count > limit {
                Button(action: onOpen) {
                    Text("+ \(rows.count - limit) more")
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .padding(.leading, 34)
                        .frame(minHeight: 28)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func kicker(_ session: PhoneToday.Session, sport: Sport) -> String {
        [sport.label, session.intentLabel].compactMap { $0 }.joined(separator: " · ")
    }

    private func meta(_ session: PhoneToday.Session) -> String? {
        var parts: [String] = []
        if let strength = session.strength {
            parts.append("\(strength.exercises.count) exercises")
            if let last = strength.lastDone { parts.append("last done \(TodayFormat.shortDay(last, relativeTo: data.date))") }
        } else {
            if (session.distanceKm ?? 0) > 0, let minutes = session.durationMin { parts.append("~\(minutes) min") }
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }
}

// MARK: - Resume

private struct ResumeWorkoutCard: View {
    let workout: StrengthSession
    let onResume: () -> Void

    var body: some View {
        let working = workout.exercises.flatMap(\.workingSets)
        let done = working.filter(\.isCompleted).count
        let index = workout.exercises.firstIndex { $0.exerciseOrder == workout.currentExerciseOrder }
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("Workout in progress", color: Color(hex: 0xFF7AB5))
                Spacer()
                if let startedAt = StrengthFormat.parseMoment(workout.startedAt) {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        Text(StrengthFormat.clock(Int(context.date.timeIntervalSince(startedAt))))
                            .font(AppFont.number(20))
                            .foregroundStyle(Color.ink)
                            .monospacedDigit()
                    }
                }
            }
            Text(workout.templateName.uppercased())
                .font(AppFont.title(26))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .padding(.top, 8)
            Text(meta(done: done, total: working.count, index: index))
                .font(AppFont.body(13))
                .foregroundStyle(Color.muted)
                .padding(.top, 4)
            GeometryReader { proxy in
                Capsule().fill(Color.track).overlay(alignment: .leading) {
                    Capsule().fill(Color.strength)
                        .frame(width: proxy.size.width * (working.isEmpty ? 0 : Double(done) / Double(working.count)))
                }
            }
            .frame(height: 4)
            .padding(.top, 12)
            Button(action: onResume) {
                Label("Resume workout", systemImage: "play.fill")
            }
            .buttonStyle(VoltButtonStyle())
            .padding(.top, 16)
        }
        .card(border: Color.strength.opacity(0.35))
    }

    private func meta(done: Int, total: Int, index: Int?) -> String {
        var parts = ["\(done) of \(total) sets"]
        if let index { parts.insert("Exercise \(index + 1) of \(workout.exercises.count)", at: 0) }
        return parts.joined(separator: " · ")
    }
}

// MARK: - Readiness

private struct ReadinessCard: View {
    let readiness: PhoneToday.Readiness
    let vitals: PhoneToday.Vitals
    let checkinDone: Bool
    let onOpen: () -> Void
    let onCheckin: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // The card opens Body; the check-in below is its own button, so it can't sit inside that one.
            Button(action: onOpen) { summary.contentShape(Rectangle()) }
                .buttonStyle(.plain)
                .accessibilityHint("Opens sleep, steps, heart rate and training load")
            if checkinDone {
                Button(action: onCheckin) {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.mobility)
                        Text("Checked in today").foregroundStyle(Color.muted)
                        Spacer()
                        Text("Edit").foregroundStyle(Color.inkSoft)
                    }
                    .font(AppFont.body(12, weight: .semibold))
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.top, 4)
                .padding(.bottom, -10)
                .accessibilityLabel("Edit today's check-in")
            } else {
                Button("Check in", action: onCheckin)
                    .buttonStyle(OutlineButtonStyle(height: 44))
                    .padding(.top, 14)
            }
        }
        .card()
    }

    private var style: ReadinessStyle { ReadinessStyle(level: readiness.level, points: readiness.points) }
    private var factors: [PhoneToday.Factor] { readiness.factors ?? [] }

    private var summary: some View {
        let style = style
        return VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Readiness")
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.faint)
            }
            HStack(spacing: 16) {
                ReadinessGauge(style: style, size: 92)
                VStack(alignment: .leading, spacing: 4) {
                    Text(style.headline.uppercased())
                        .font(AppFont.title(38))
                        .foregroundStyle(style.color)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    Text(signalSummary(style))
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                    if !factors.isEmpty {
                        HStack(spacing: 5) {
                            ForEach(factors) { SignalChip(key: $0.key, tone: $0.tone, size: 24) }
                        }
                        .padding(.top, 4)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.top, 10)
            HStack(spacing: 8) {
                vital(vitals.restingHr.map { String(Int($0.rounded())) }, unit: "bpm", label: "Resting HR",
                      trend: vitals.restingHrTrend, color: .danger)
                vital(vitals.sleepH.map { String(format: "%.1f", $0) }, unit: "h", label: "Sleep",
                      trend: vitals.sleepTrend, color: SleepStage.deep.color)
                pain
            }
            .padding(.top, 14)
            if let advice = readiness.advice {
                Text(advice)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.top, 12)
            }
        }
    }

    private func signalSummary(_ style: ReadinessStyle) -> String {
        guard !factors.isEmpty else { return style.label }
        let steady = factors.filter { $0.points == 0 && !["caution", "risk"].contains($0.tone) }.count
        return "\(style.label) · \(steady) of \(factors.count) signals steady"
    }

    private func vital(_ value: String?, unit: String, label: String, trend: [PhoneToday.Reading]?, color: Color) -> some View {
        let values = (trend ?? []).map(\.value)
        return VStack(alignment: .leading, spacing: 2) {
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value ?? "–").font(AppFont.number(26)).foregroundStyle(value == nil ? Color.muted : Color.ink)
                if value != nil {
                    Text(unit).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
                }
            }
            Group {
                if values.count >= 2 {
                    TrendLine(values: values, color: color)
                } else {
                    Color.clear
                }
            }
            .frame(height: 18)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    /// Ten ticks, filled up to today's pain in its colour.
    private var pain: some View {
        let color = vitals.pain.map(TodayFormat.painColor) ?? .muted
        return VStack(alignment: .leading, spacing: 2) {
            Text("Pain").font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(vitals.pain.map(String.init) ?? "–").font(AppFont.number(26)).foregroundStyle(vitals.pain == nil ? Color.muted : color)
                if vitals.pain != nil {
                    Text("/10").font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
                }
            }
            HStack(spacing: 2) {
                ForEach(1...10, id: \.self) { tick in
                    Capsule().fill(tick <= (vitals.pain ?? 0) ? color : Color.track)
                }
            }
            .frame(height: 5)
            .frame(height: 18)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

// MARK: - Week

private struct WeekCard: View {
    let week: [PhoneToday.WeekDay]
    let minutes: PhoneToday.WeekMinutes
    let today: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("This week")
                Spacer()
                Text(TodayFormat.duration(minutes.done)).font(AppFont.number(22)).foregroundStyle(Color.ink)
                    + Text(minutes.planned > 0 ? " of \(TodayFormat.duration(minutes.planned))" : "")
                    .font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
            progressBar.padding(.top, 10)
            HStack(spacing: 0) {
                ForEach(week) { day in
                    DayRing(day: day, isToday: day.date == today).frame(maxWidth: .infinity)
                }
            }
            .padding(.top, 14)
        }
        .card()
    }

    private var progressBar: some View {
        GeometryReader { proxy in
            let total = Double(max(minutes.planned, minutes.done, 1))
            HStack(spacing: 2) {
                ForEach(Array(minutes.bySport.enumerated()), id: \.offset) { _, part in
                    Rectangle()
                        .fill(part.sport.color)
                        .frame(width: max(2, proxy.size.width * Double(part.minutes) / total))
                }
                Spacer(minLength: 0)
            }
        }
        .frame(height: 6)
        .background(Color.track)
        .clipShape(Capsule())
    }
}

private struct DayRing: View {
    let day: PhoneToday.WeekDay
    let isToday: Bool

    private var isDone: Bool { !day.doneSports.isEmpty }

    var body: some View {
        VStack(spacing: 7) {
            Text(String(day.label.prefix(1)))
                .font(AppFont.body(11, weight: isToday ? .bold : .semibold))
                .foregroundStyle(isToday ? Color.volt : Color.muted)
            ring.frame(width: 32, height: 32)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(day.label): \(day.title ?? "Rest"), \(isDone ? "done" : day.status)")
    }

    @ViewBuilder
    private var ring: some View {
        if isDone {
            ZStack {
                Circle().fill(fill)
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.bg)
            }
            .overlay { if isToday { Circle().strokeBorder(Color.volt, lineWidth: 2).padding(-4) } }
        } else if isToday {
            ZStack {
                Circle().strokeBorder(Color.volt, lineWidth: 2)
                if day.sport != .rest { Circle().fill(day.sport.color).frame(width: 10, height: 10) }
            }
        } else if day.sport == .rest {
            Circle().fill(Color.dim).frame(width: 5, height: 5)
        } else {
            Circle()
                .strokeBorder(
                    day.sport.color.opacity(0.45),
                    style: StrokeStyle(lineWidth: 2, dash: day.status == "missed" || day.status == "skipped" ? [3, 3] : [])
                )
        }
    }

    /// One sport fills the ring; two or more split it like the artboard's Tuesday.
    private var fill: AnyShapeStyle {
        let colors = day.doneSports.map(\.color)
        guard colors.count > 1 else { return AnyShapeStyle(colors.first ?? .muted) }
        let step = 1.0 / Double(colors.count)
        let stops = colors.enumerated().flatMap { index, color in
            [Gradient.Stop(color: color, location: Double(index) * step), .init(color: color, location: Double(index + 1) * step)]
        }
        return AnyShapeStyle(AngularGradient(stops: stops, center: .center, startAngle: .degrees(-90), endAngle: .degrees(270)))
    }
}

#Preview {
    TodayView().preferredColorScheme(.dark)
}
