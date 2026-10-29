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
    @State private var recap: RecapLaunch?
    @State private var showStudio = false
    /// The workout picked in Workout Studio, started once the sheet is gone.
    @State private var studioPick: Int?
    @State private var flameHop = 0
    var onStartStrength: (Int?) -> Void = { _ in }
    /// Bumped when the strength screen closes, so the banner and plan reload.
    var refresh = 0
    /// Bumped by the Sunday nudge (`trainlog://recap`) to open the week's recap.
    var recapRequest = 0

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
        .fullScreenCover(item: $recap) { launch in
            WeekRecapView(weekStart: launch.weekStart)
        }
        .onChange(of: recapRequest) { openRecap() }
        .sheet(isPresented: $showStudio, onDismiss: {
            if let id = studioPick {
                studioPick = nil
                onStartStrength(id)
            }
        }) {
            WorkoutStudioSheet(planned: model.data?.today?.strength?.templateId) { studioPick = $0 }
                .presentationDetents([.large])
                .presentationBackground(Color.bg)
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

    /// The Sunday nudge: this week on Sunday, last week on Monday, the week so far otherwise.
    private func openRecap() {
        let offer = RecapFormat.offer(today: FoodFormat.iso(.now))
        recap = RecapLaunch(weekStart: offer?.weekStart)
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
                        .reveal(0)
                        .transition(.scale(scale: 0.96).combined(with: .opacity))
                }
                if let data = model.data {
                    if model.offline, let syncedAt = model.syncedAt {
                        offlineNote(syncedAt)
                    }
                    if let offer = RecapFormat.offer(today: data.date) {
                        RecapCard(label: offer.label, range: RecapFormat.range(offer.weekStart, RecapFormat.weekEnd(offer.weekStart))) {
                            recap = RecapLaunch(weekStart: offer.weekStart)
                        }
                        .reveal(1)
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
                    .reveal(2)
                    ReadinessCard(readiness: data.readiness, vitals: data.vitals, checkinDone: data.checkinDone,
                                  onOpen: { showBody = true }, onCheckin: { showCheckin = true })
                    .reveal(3)
                    WeekCard(week: data.week, minutes: data.weekMinutes, today: data.date) {
                        recap = RecapLaunch(weekStart: nil)
                    }
                    .reveal(4)
                } else if let error = model.error {
                    errorCard(error)
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
            .animation(.spring(duration: 0.45, bounce: 0.15), value: model.activeWorkout == nil)
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
                guard (try? await Task.sleep(for: .seconds(5))) != nil else { return }
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
                            .symbolEffect(.bounce.up, options: .speed(0.8), value: flameHop)
                            .onAppear { Task { try? await Task.sleep(for: .seconds(0.6)); flameHop += 1 } }
                        Text("\(streak)").font(AppFont.body(13, weight: .bold))
                            .contentTransition(.numericText(value: Double(streak)))
                    }
                    .foregroundStyle(Color.volt)
                    .padding(.horizontal, 10)
                    .frame(height: 26)
                    .background(Color.volt.opacity(0.12), in: Capsule())
                    .accessibilityLabel("\(streak) day streak")
                }
                // Any workout, planned today or not; the Resume banner owns this while one is open.
                if model.activeWorkout == nil {
                    Button {
                        showStudio = true
                    } label: {
                        Image(systemName: "dumbbell.fill")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(Color.strength)
                            .frame(width: 34, height: 34)
                            .background(Color.raised, in: Circle())
                            .frame(width: 44, height: 44)
                            .contentShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .padding(-5)
                    .accessibilityLabel("Workout Studio")
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
                .transition(.scale(scale: 0.9).combined(with: .opacity))
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
        .animation(.spring(duration: 0.45, bounce: 0.2), value: next)
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
            bigNumber(km, unit: "km") { TodayFormat.number(($0 * 10).rounded() / 10) }
        } else if let minutes = session.durationMin {
            bigNumber(Double(minutes), unit: "min") { "\(Int($0.rounded()))" }
        }
    }

    private func bigNumber(_ value: Double, unit: String, format: @escaping (Double) -> String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 0) {
            CountUp(value: value, delay: 0.3, format: format)
                .font(AppFont.number(26)).foregroundStyle(Color.ink)
            Text(" \(unit)").font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.muted)
        }
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
        .buttonStyle(PressableStyle())
        .accessibilityLabel("\(sport.label), \(done ? "done" : "to do")")
    }

    /// The rehab part; opens the guided session (its first screen lists the exercises).
    private func rehabPart(_ rehab: (done: Int, left: Int, title: String), number: Int?, after sport: Sport?) -> some View {
        let total = rehab.done + rehab.left
        let complete = rehab.left == 0
        let share = total == 0 ? 0 : Double(rehab.done) / Double(total)
        let ring = ZStack {
            Circle().stroke(Color.track, lineWidth: 3)
            growing(delay: 0.5) { grown in
                Circle()
                    .trim(from: 0, to: grown ? share : 0)
                    .stroke(Color.mobility, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.spring(duration: 0.6), value: share)
            }
            if complete {
                Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(Color.mobility)
                    .transition(.scale.combined(with: .opacity))
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
        .buttonStyle(PressableStyle())
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
                    growing(delay: 0.3) { grown in
                        Capsule().fill(Color.strength)
                            .frame(width: grown ? proxy.size.width * (working.isEmpty ? 0 : Double(done) / Double(working.count)) : 0)
                            .animation(.spring(duration: 0.5), value: done)
                    }
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
                        if let pain = vitals.pain {
                            Text("· pain \(pain)/10").foregroundStyle(TodayFormat.painColor(pain))
                        }
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

    private var style: ReadinessStyle { ReadinessStyle(level: readiness.level) }
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
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(style.headline.uppercased())
                    .font(AppFont.title(30))
                    .foregroundStyle(style.color)
                Text(factors.isEmpty ? style.label : "\(style.label) · \(steadyCount) of \(factors.count) steady")
                    .font(AppFont.body(12, weight: .medium))
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
            }
            .padding(.top, 6)
            if !factors.isEmpty {
                // One slim slice per signal, steady first: the whole read at a glance.
                growing(delay: 0.35) { grown in
                    HStack(spacing: 3) {
                        ForEach(Array(factors.sorted { rank($0) < rank($1) }.enumerated()), id: \.element.id) { index, factor in
                            Capsule().fill(BodyFormat.toneColor(factor.tone))
                                .scaleEffect(x: grown ? 1 : 0, anchor: .leading)
                                .animation(.spring(duration: 0.5, bounce: 0.2).delay(0.35 + Double(index) * 0.06), value: grown)
                        }
                    }
                }
                .frame(height: 4)
                .padding(.top, 10)
            }
            if let ranges = vitals.ranges, !ranges.isEmpty {
                overnight(ranges).padding(.top, 14)
            }
            if let advice = readiness.advice {
                Text(advice)
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.top, 12)
            }
        }
    }

    private func rank(_ factor: PhoneToday.Factor) -> Int {
        ["caution": 1, "risk": 2][factor.tone] ?? 0
    }

    private var steadyCount: Int {
        factors.filter { $0.points == 0 && !["caution", "risk"].contains($0.tone) }.count
    }

    /// HRV, resting HR and sleep as Watch Vitals columns, each against its typical range.
    private func overnight(_ ranges: [PhoneToday.VitalRange]) -> some View {
        let known = ranges.compactMap { range in VitalKind(rawValue: range.key).map { (kind: $0, range: range) } }
        let outliers = known.filter { VitalStatus(value: $0.range.value, low: $0.range.low, high: $0.range.high).isOutlier }.count
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker("Overnight vitals")
                Spacer()
                Text(outliers == 0 ? "All typical" : "\(outliers) outlier\(outliers == 1 ? "" : "s")")
                    .font(AppFont.body(11, weight: .semibold))
                    .foregroundStyle(outliers == 0 ? Color.muted : Color.warning)
            }
            HStack(spacing: 8) {
                ForEach(known, id: \.kind) { item in
                    vital(item.kind, item.range)
                }
            }
        }
    }

    private func vital(_ kind: VitalKind, _ range: PhoneToday.VitalRange) -> some View {
        let status = VitalStatus(value: range.value, low: range.low, high: range.high)
        return HStack(spacing: 10) {
            VitalBar(kind: kind, value: range.value, low: range.low, high: range.high, width: 10)
                .frame(height: 58)
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 4) {
                    Image(systemName: kind.icon).font(.system(size: 9, weight: .bold))
                    Text(kind.shortLabel).font(AppFont.body(11, weight: .semibold)).lineLimit(1)
                }
                .foregroundStyle(kind.color)
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(kind.format(range.value)).font(AppFont.number(24)).foregroundStyle(Color.ink)
                    Text(kind.unit).font(AppFont.body(10, weight: .medium)).foregroundStyle(Color.muted)
                }
                Text(status == .typical ? "Typical" : status == .low ? "Low" : status == .high ? "High" : "–")
                    .font(AppFont.body(10, weight: .semibold))
                    .foregroundStyle(status.isOutlier ? status.color(kind) : Color.faint)
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(kind.color.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(kind.label) \(kind.format(range.value)) \(kind.unit), \(status.label)")
    }
}

// MARK: - Recap

/// Opens the week recap; a nil week is the current one.
private struct RecapLaunch: Identifiable {
    let id = UUID()
    let weekStart: String?
}

/// Sunday and Monday: the week in review, one tap away.
private struct RecapCard: View {
    let label: String
    let range: String
    let onOpen: () -> Void

    var body: some View {
        Button(action: onOpen) {
            HStack(spacing: 14) {
                Image(systemName: "trophy.fill")
                    .font(.system(size: 18, weight: .bold))
                    .symbolEffect(.wiggle, options: .repeat(.periodic(delay: 6)))
                    .foregroundStyle(Color.bg)
                    .frame(width: 44, height: 44)
                    .background(Color.volt, in: Circle())
                VStack(alignment: .leading, spacing: 3) {
                    Kicker(range, color: .volt)
                    Text(label.uppercased()).font(AppFont.title(24)).foregroundStyle(Color.ink)
                    Text("Time, wins and what's next").font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 14, weight: .bold)).foregroundStyle(Color.muted)
            }
            .card(border: Color.volt.opacity(0.35))
            .contentShape(Rectangle())
        }
        .buttonStyle(PressableStyle())
    }
}

// MARK: - Week

private struct WeekCard: View {
    let week: [PhoneToday.WeekDay]
    let minutes: PhoneToday.WeekMinutes
    let today: String
    var onOpen: () -> Void = {}

    var body: some View {
        Button(action: onOpen) { content }
            .buttonStyle(PressableStyle())
            .accessibilityHint("Opens the week recap")
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Kicker("This week")
                Image(systemName: "chevron.right").font(.system(size: 10, weight: .bold)).foregroundStyle(Color.muted)
                Spacer()
                HStack(alignment: .firstTextBaseline, spacing: 0) {
                    CountUp(value: Double(minutes.done), delay: 0.45) { TodayFormat.duration(Int($0.rounded())) }
                        .font(AppFont.number(22)).foregroundStyle(Color.ink)
                    Text(minutes.planned > 0 ? " of \(TodayFormat.duration(minutes.planned))" : "")
                        .font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            }
            progressBar.padding(.top, 10)
            HStack(spacing: 0) {
                ForEach(Array(week.enumerated()), id: \.element.id) { index, day in
                    DayRing(day: day, isToday: day.date == today, delay: 0.4 + Double(index) * 0.05)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.top, 14)
        }
        .card()
    }

    private var progressBar: some View {
        GeometryReader { proxy in
            let total = Double(max(minutes.planned, minutes.done, 1))
            growing(delay: 0.45) { grown in
                HStack(spacing: 2) {
                    ForEach(Array(minutes.bySport.enumerated()), id: \.offset) { _, part in
                        Rectangle()
                            .fill(part.sport.color)
                            .frame(width: grown ? max(2, proxy.size.width * Double(part.minutes) / total) : 0)
                    }
                    Spacer(minLength: 0)
                }
                .animation(.spring(duration: 0.6), value: minutes.done)
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
    var delay: Double = 0
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var isDone: Bool { !day.doneSports.isEmpty }

    var body: some View {
        VStack(spacing: 7) {
            Text(String(day.label.prefix(1)))
                .font(AppFont.body(11, weight: isToday ? .bold : .semibold))
                .foregroundStyle(isToday ? Color.volt : Color.muted)
            ring.frame(width: 32, height: 32)
                .background { if isToday && !reduceMotion { TodayPulse() } }
                .scaleEffect(shown || reduceMotion ? 1 : 0.4)
                .opacity(shown ? 1 : 0)
                .onFirstVisible(threshold: 0.8) {
                    withAnimation(.spring(duration: 0.5, bounce: 0.4).delay(reduceMotion ? 0 : delay)) { shown = true }
                }
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

/// A volt ripple that leaves today's ring every few seconds: you are here.
private struct TodayPulse: View {
    var body: some View {
        PhaseAnimator([false, true]) { out in
            Circle()
                .strokeBorder(Color.volt, lineWidth: 1.5)
                .scaleEffect(out ? 1.6 : 1)
                .opacity(out ? 0 : 0.6)
        } animation: { out in
            out ? .easeOut(duration: 1.6).delay(1.4) : .linear(duration: 0)
        }
        .allowsHitTesting(false)
    }
}

#Preview {
    TodayView().preferredColorScheme(.dark)
}
