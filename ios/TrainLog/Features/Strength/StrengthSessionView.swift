import SwiftUI

/// Frame 02: one set at a time, full screen, no tab bar.
struct StrengthSessionView: View {
    @State private var model: StrengthSessionModel
    @State private var showClose = false
    @State private var showExercises = false
    @State private var editingWeight = false
    @State private var weightText = ""
    @State private var toast: LoggedSet?
    @State private var historyFor: String?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase

    init(templateId: Int?, oneTime: TemplateInput? = nil) {
        _model = State(initialValue: StrengthSessionModel.launch(templateId: templateId, oneTime: oneTime))
        #if DEBUG
        if StrengthSessionModel.demoStage == "history" { _historyFor = State(initialValue: "Back Squat") }
        #endif
    }

    var body: some View {
        VStack(spacing: 0) {
            if case .summary = model.phase {} else { topBar }
            switch model.phase {
            case .loading:
                ProgressView().tint(.muted).frame(maxWidth: .infinity, maxHeight: .infinity)
            case .brief(let template):
                WatchReadyRow(watch: .shared)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 4)
                SessionBriefView(template: template, starting: model.starting) {
                    Task { await model.startFromBrief() }
                }
            case .failed(let message):
                failed(message)
            case .summary(let summary):
                SessionSummaryView(summary: summary, onDone: model.dismissSummary)
            case .ready, .closed:
                if let session = model.session { content(session) }
            }
        }
        .background(Color.bg.ignoresSafeArea())
        .task {
            guard !model.isDemo else { return }
            // TrainLog on the Watch shows the same workout: changes go both ways.
            model.onShare = { WatchLive.shared.share(strength: $0) }
            model.onEnd = { WatchLive.shared.send($0) }
            WatchLive.shared.onStrength = { model.adopt($0) }
            WatchLive.shared.onCommand = { model.handleWatch($0) }
            await model.load()
        }
        // The brief is up: TrainLog on the Watch wakes and waits, Start on either starts both.
        .onChange(of: model.phase) {
            guard case .brief(let template) = model.phase, !model.isDemo else { return }
            WatchLive.shared.startOnWatch(WatchWorkoutType.strength(templateId: template.id))
            let minutes = template.estimatedDurationMinutes.map { " · ~\($0) min" } ?? ""
            WatchLive.shared.share(pending: .init(kind: .strength, title: template.name,
                                                  detail: "\(template.exercises.count) exercises\(minutes)"))
        }
        // Resumed, or started without a brief: TrainLog on the Watch joins it straight away.
        .onChange(of: model.session?.id) {
            guard let session = model.session, session.isActive, !model.isDemo else { return }
            WatchLive.shared.startOnWatch(WatchWorkoutType.strength(templateId: session.templateId))
        }
        .onDisappear {
            guard !model.isDemo else { return }
            WatchLive.shared.onStrength = nil
            WatchLive.shared.onCommand = nil
            WatchLive.shared.stopLeading()
        }
        // Keeps in step with the web runner while the app is in front.
        .task(id: scenePhase) {
            guard scenePhase == .active else { return }
            while !Task.isCancelled {
                await model.refresh()
                try? await Task.sleep(for: .seconds(4))
            }
        }
        .onChange(of: model.phase) { _, phase in
            if phase == .closed { dismiss() }
        }
        .confirmationDialog("Leave the workout?", isPresented: $showClose, titleVisibility: .visible) {
            if model.session?.exercises.contains(where: { $0.sets.contains(where: \.isCompleted) }) == true {
                Button("Finish workout") { Task { await model.finish() } }
            }
            Button("Leave it for later") { dismiss() }
            Button("Discard workout", role: .destructive) { Task { await model.abandon() } }
        } message: {
            Text("Leaving for later keeps it open; you can pick it up from Today.")
        }
        .sheet(isPresented: $showExercises) {
            if let session = model.session {
                ExerciseListSheet(session: session) { exercise in
                    showExercises = false
                    Task { await model.jump(to: exercise) }
                }
                .presentationDetents([.medium, .large])
                .presentationBackground(Color.card)
            }
        }
        .sheet(item: Binding(get: { historyFor.flatMap { model.history[$0] } }, set: { historyFor = $0?.exerciseName })) { history in
            LiftHistorySheet(history: history, target: historyTarget(history))
                .presentationDetents([.medium, .large])
                .presentationBackground(Color.card)
        }
        .alert("Weight (kg)", isPresented: $editingWeight) {
            TextField("Bodyweight", text: $weightText).keyboardType(.decimalPad)
            Button("Cancel", role: .cancel) {}
            Button("Set") {
                let value = Double(weightText.replacingOccurrences(of: ",", with: "."))
                model.draftWeight = value.flatMap { $0 > 0 ? min(1000, $0) : nil }
            }
        } message: {
            Text("Leave empty for bodyweight.")
        }
    }

    // MARK: Top bar

    private var topBar: some View {
        HStack {
            circleButton("xmark", label: "Close workout") {
                // Nothing started yet: just leave.
                if model.session == nil { dismiss() } else { showClose = true }
            }
            Spacer()
            VStack(spacing: 3) {
                Text((model.session?.templateName ?? "Strength").uppercased())
                    .font(AppFont.body(10, weight: .semibold))
                    .tracking(1.4)
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
                if let startedAt = model.startedAt {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        HStack(spacing: 10) {
                            Text(StrengthFormat.clock(Int(context.date.timeIntervalSince(startedAt))))
                                .font(AppFont.number(20))
                                .foregroundStyle(Color.ink)
                                .monospacedDigit()
                            // Live from the Watch while it runs the workout.
                            WatchChip(watch: .shared)
                        }
                    }
                }
            }
            Spacer()
            circleButton("line.3.horizontal", label: "All exercises") { showExercises = true }
                .disabled(model.session == nil)
                .opacity(model.session == nil ? 0 : 1)
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .padding(.bottom, 12)
    }

    /// Today's target in the history's own measure, from the current set when it's this lift.
    private func historyTarget(_ history: LiftHistory) -> Double? {
        let set = model.session?.exercises.first { $0.exerciseName == history.exerciseName }
            .flatMap { exercise in model.current?.exercise.id == exercise.id ? model.current?.set : exercise.workingSets.first { !$0.isCompleted } }
        return LiftLogic.target(of: set, LiftLogic.metric(of: history))
    }

    private func circleButton(_ icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color.inkSoft)
                .frame(width: 36, height: 36)
                .background(Color(hex: 0x191D27), in: Circle())
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }

    // MARK: Content

    private func content(_ session: StrengthSession) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                progressBar(session)
                if model.unsynced {
                    HStack(spacing: 6) {
                        Image(systemName: "wifi.slash").font(.system(size: 11, weight: .semibold))
                        Text("Saved on this phone · syncs when the Mac is reachable").font(AppFont.body(12, weight: .medium))
                    }
                    .foregroundStyle(Color.muted)
                    .padding(.horizontal, 4)
                }
                if model.allSetsDone {
                    allDone(session)
                } else if let current = model.current {
                    exerciseHeader(current.exercise, in: session)
                        .id(current.exercise.id)
                        .transition(.opacity)
                    if let ramp = model.ramp {
                        WarmupRampCard(
                            working: ramp.working, reps: ramp.reps, steps: ramp.steps, ticked: model.rampTicks, kit: model.kit,
                            onTick: { index in withAnimation(.snappy) { model.toggleRampStep(index) } },
                            onSkip: { withAnimation(.snappy) { model.finishRamp() } }
                        )
                        .transition(.opacity)
                    } else {
                        setCard(current.exercise, current.set)
                            .id(current.set.id)
                            .transition(.asymmetric(
                                insertion: .move(edge: .trailing).combined(with: .opacity),
                                removal: .move(edge: .leading).combined(with: .opacity)
                            ))
                        setList(current.exercise, currentId: current.set.id)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
            .animation(.spring(duration: 0.5, bounce: 0.18), value: model.current?.set.id)
            .animation(.spring(duration: 0.5, bounce: 0.18), value: model.allSetsDone)
            .animation(.snappy, value: model.ramp == nil)
        }
        .scrollIndicators(.hidden)
        .safeAreaInset(edge: .bottom, spacing: 0) { bottomBar }
    }

    private func progressBar(_ session: StrengthSession) -> some View {
        HStack(spacing: 4) {
            ForEach(session.exercises) { exercise in
                GeometryReader { proxy in
                    Capsule().fill(Color.outline)
                        .overlay(alignment: .leading) {
                            Capsule().fill(Color.strength)
                                .frame(width: proxy.size.width * StrengthLogic.progress(of: exercise))
                        }
                }
                .frame(height: 4)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Workout progress")
    }

    private func exerciseHeader(_ exercise: StrengthSession.Exercise, in session: StrengthSession) -> some View {
        let index = (session.exercises.firstIndex { $0.id == exercise.id } ?? 0) + 1
        return VStack(alignment: .leading, spacing: 6) {
            Kicker("Exercise \(index) of \(session.exercises.count)", color: Color(hex: 0xFF7AB5))
            Text(exercise.exerciseName.uppercased())
                .font(AppFont.title(42))
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
            if let history = model.history[exercise.exerciseName] {
                LiftHistoryLine(history: history, target: historyTarget(history)) { historyFor = exercise.exerciseName }
            }
            if let hint = model.hints[exercise.exerciseName] {
                Text(hint).font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
            if let notes = exercise.notes, !notes.isEmpty {
                Text(notes).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
            }
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func setCard(_ exercise: StrengthSession.Exercise, _ set: StrengthSession.WorkoutSet) -> some View {
        let working = exercise.workingSets
        let title = set.isWarmup
            ? "Warm-up"
            : "Set \((working.firstIndex { $0.id == set.id } ?? 0) + 1) of \(working.count)"
        // Loaded lifts lead with the weight; bodyweight ones with reps, weight only when added.
        let loaded = set.targetWeightKg != nil
        let showsWeight = loaded || model.draftWeight != nil
        return VStack(spacing: 0) {
            HStack {
                Kicker(title)
                Spacer()
                Text("Target \(StrengthFormat.load(weight: set.targetWeightKg, reps: set.targetReps, seconds: set.targetSeconds))")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
            }
            VStack(spacing: 0) {
                if loaded {
                    weightRow
                    if LiftLogic.isBarbell(exercise.exerciseName) {
                        PlateRow(weight: model.draftWeight, kit: model.kit) { model.draftWeight = $0 }
                    }
                    divider
                }
                if set.isTimed {
                    holdRow
                } else {
                    valueRow("Reps", value: "\(model.draftReps)", minus: { model.adjustReps(by: -1) }, plus: { model.adjustReps(by: 1) })
                }
                if showsWeight && !loaded {
                    divider
                    weightRow.transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .padding(.top, 10)
            if !showsWeight && model.holdStartedAt == nil {
                Button {
                    withAnimation(.snappy) { model.addWeight() }
                } label: {
                    Label("Add weight", systemImage: "plus")
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .padding(.horizontal, 14)
                        .frame(height: 32)
                        .overlay(Capsule().strokeBorder(Color.outline))
                        .frame(minHeight: 44)
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .padding(.top, 4)
            }
            Kicker("How did it feel?")
                .font(AppFont.body(10, weight: .semibold))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 14)
            HStack(spacing: 8) {
                ForEach(SetEffort.allCases, id: \.self) { effort in
                    effortButton(effort)
                }
            }
            .padding(.top, 8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
        .animation(.snappy, value: showsWeight)
    }

    private var divider: some View {
        Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.vertical, 4)
    }

    private var weightRow: some View {
        valueRow(
            "Weight",
            value: StrengthFormat.weight(model.draftWeight),
            unit: model.draftWeight == nil ? nil : "kg",
            minus: { model.adjustWeight(by: -1) },
            plus: { model.adjustWeight(by: 1) },
            onTapValue: {
                weightText = model.draftWeight.map(TodayFormat.number) ?? ""
                editingWeight = true
            }
        )
    }

    /// One value, big in the middle, with round − and + either side.
    private func valueRow(
        _ label: String, value: String, unit: String? = nil,
        minus: @escaping () -> Void, plus: @escaping () -> Void, onTapValue: (() -> Void)? = nil
    ) -> some View {
        HStack(spacing: 0) {
            roundButton("minus", label: "Less \(label)", action: minus)
            Spacer(minLength: 8)
            VStack(spacing: 0) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(value)
                        .font(AppFont.number(60))
                        .foregroundStyle(Color.ink)
                        .monospacedDigit()
                        .contentTransition(.numericText())
                    if let unit {
                        Text(unit).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.muted)
                    }
                }
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                Kicker(label).font(AppFont.body(10, weight: .semibold))
            }
            .contentShape(Rectangle())
            .onTapGesture { onTapValue?() }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(label) \(value) \(unit ?? "")")
            .accessibilityAddTraits(onTapValue == nil ? [] : .isButton)
            Spacer(minLength: 8)
            roundButton("plus", label: "More \(label)", action: plus)
        }
        .padding(.vertical, 6)
    }

    /// A timed set: the dial counts down once started; ±5 s until then.
    private var holdRow: some View {
        let running = model.holdStartedAt != nil
        return VStack(spacing: 6) {
            HStack(spacing: 0) {
                roundButton("minus", label: "5 seconds less") { model.adjustSeconds(by: -5) }
                    .opacity(running ? 0 : 1)
                    .disabled(running)
                Spacer(minLength: 8)
                HoldDial(startedAt: model.holdStartedAt, seconds: model.draftSeconds)
                Spacer(minLength: 8)
                roundButton("plus", label: "5 seconds more") { model.adjustSeconds(by: 5) }
                    .opacity(running ? 0 : 1)
                    .disabled(running)
            }
            if !running {
                Button("Log without the timer") { Task { await model.logCurrentSet() } }
                    .font(AppFont.body(13, weight: .medium))
                    .foregroundStyle(Color.muted)
                    .frame(minHeight: 44)
                    .buttonStyle(.plain)
            }
        }
        .padding(.vertical, 6)
    }

    private func roundButton(_ icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button {
            withAnimation(.snappy) { action() }
        } label: {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(Color.ink)
                .frame(width: 52, height: 52)
                .background(Color.inset, in: Circle())
                .overlay(Circle().strokeBorder(Color.cardBorder))
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .buttonRepeatBehavior(.enabled)
        .sensoryFeedback(.selection, trigger: model.draftWeight)
        .sensoryFeedback(.selection, trigger: model.draftReps)
        .sensoryFeedback(.selection, trigger: model.draftSeconds)
        .accessibilityLabel(label)
    }

    private func effortButton(_ effort: SetEffort) -> some View {
        let selected = model.draftEffort == effort
        return Button {
            model.draftEffort = selected ? nil : effort
        } label: {
            Text(effort.label)
                .font(AppFont.body(13, weight: .semibold))
                .foregroundStyle(selected ? Color(hex: 0xFF9AC6) : Color.ink)
                .frame(maxWidth: .infinity, minHeight: 44)
                .background(selected ? Color.strength.opacity(0.14) : .clear, in: Capsule())
                .overlay(Capsule().strokeBorder(selected ? Color.strength : Color.outline, lineWidth: 1))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func setList(_ exercise: StrengthSession.Exercise, currentId: Int) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(exercise.sets.enumerated()), id: \.element.id) { index, set in
                if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                SetRow(
                    label: StrengthLogic.label(for: set, in: exercise),
                    set: set,
                    isCurrent: set.id == currentId,
                    draftWeight: model.draftWeight,
                    draftReps: model.draftReps,
                    draftSeconds: model.draftSeconds
                )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder, lineWidth: 1))
    }

    private func allDone(_ session: StrengthSession) -> some View {
        let sets = session.exercises.flatMap(\.workingSets)
        let volume = sets.reduce(0.0) { $0 + ($1.actualWeightKg ?? 0) * Double($1.actualReps ?? 0) }
        return VStack(alignment: .leading, spacing: 10) {
            Kicker("All sets logged", color: .volt)
            Text("NICE WORK").font(AppFont.title(42)).foregroundStyle(Color.ink)
            HStack(spacing: 24) {
                stat("\(sets.count)", "sets")
                stat("\(session.exercises.count)", "exercises")
                if volume > 0 { stat(TodayFormat.number(volume.rounded()), "kg moved") }
            }
            .padding(.top, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 20)
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(AppFont.number(36)).foregroundStyle(Color.ink)
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
        }
    }

    // MARK: Bottom

    private var bottomBar: some View {
        VStack(spacing: 10) {
            if let restEndsAt = model.restEndsAt, !model.allSetsDone {
                RestStrip(endsAt: restEndsAt, total: model.restSeconds, onSkip: model.skipRest)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            if model.allSetsDone {
                Button {
                    Task { await model.finish() }
                } label: {
                    if model.finishing { ProgressView().tint(Color.bg) } else { Text("Finish workout") }
                }
                .buttonStyle(VoltButtonStyle())
                .disabled(model.finishing)
            } else if model.ramp != nil {
                Button {
                    withAnimation(.snappy) { model.finishRamp() }
                } label: {
                    Text("Warm-up done · go to set 1")
                }
                .buttonStyle(VoltButtonStyle())
            } else if let current = model.current, current.set.isTimed {
                if model.holdStartedAt == nil {
                    Button(action: model.startHold) {
                        Label("Start hold · \(StrengthFormat.hold(model.draftSeconds))", systemImage: "play.fill")
                    }
                    .buttonStyle(VoltButtonStyle())
                } else {
                    Button {
                        Task { await model.stopHold() }
                    } label: {
                        Label("Stop and log", systemImage: "stop.fill")
                    }
                    .buttonStyle(VoltButtonStyle())
                }
            } else if let current = model.current {
                Button {
                    Task { await model.logCurrentSet() }
                } label: {
                    Text(logTitle(current.exercise, current.set))
                }
                .buttonStyle(VoltButtonStyle())
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 8)
        .animation(.spring(duration: 0.45, bounce: 0.2), value: model.restEndsAt)
        .background(Color.bg.opacity(0.94).ignoresSafeArea(edges: .bottom))
        // Floats above the bar so popping in doesn't push the layout around.
        .overlay(alignment: .top) {
            if let toast {
                LoggedToast(logged: toast)
                    .offset(y: -54)
                    .transition(.scale(scale: 0.85, anchor: .bottom).combined(with: .opacity).combined(with: .offset(y: 12)))
            }
        }
        .onChange(of: model.lastLogged) { _, logged in
            withAnimation(.spring(duration: 0.4, bounce: 0.35)) { toast = logged }
        }
        .task(id: toast?.setId) {
            guard toast != nil else { return }
            try? await Task.sleep(for: .seconds(1.6))
            guard !Task.isCancelled else { return }
            withAnimation(.easeOut(duration: 0.3)) { toast = nil }
        }
    }

    private func logTitle(_ exercise: StrengthSession.Exercise, _ set: StrengthSession.WorkoutSet) -> String {
        let label = StrengthLogic.label(for: set, in: exercise).lowercased()
        let rest = set.restSeconds > 0 ? " · rest \(StrengthFormat.clock(set.restSeconds))" : ""
        return "Log \(label)\(rest)"
    }

    private func failed(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Couldn't start the workout")
            Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Button("Try again") { Task { await model.load() } }
                .buttonStyle(OutlineButtonStyle(height: 44))
                .padding(.top, 6)
        }
        .card()
        .padding(.horizontal, 16)
        .frame(maxHeight: .infinity, alignment: .top)
    }
}

private struct SetRow: View {
    let label: String
    let set: StrengthSession.WorkoutSet
    let isCurrent: Bool
    let draftWeight: Double?
    let draftReps: Int
    let draftSeconds: Int

    var body: some View {
        HStack(spacing: 12) {
            marker
            Text(label)
                .font(AppFont.body(14, weight: isCurrent ? .semibold : .regular))
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(load).font(AppFont.number(18))
            Text(trailing)
                .font(AppFont.body(12))
                .foregroundStyle(isCurrent ? Color(hex: 0xFF7AB5) : Color.muted)
                .frame(width: 40, alignment: .trailing)
        }
        .foregroundStyle(set.isCompleted || isCurrent ? Color.ink : Color.faint)
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }

    private var load: String {
        if set.isCompleted {
            return StrengthFormat.load(weight: set.actualWeightKg, reps: set.actualReps ?? set.targetReps,
                                       seconds: set.isTimed ? set.actualSeconds ?? set.targetSeconds : nil)
        }
        if isCurrent { return StrengthFormat.load(weight: draftWeight, reps: draftReps, seconds: set.isTimed ? draftSeconds : nil) }
        return StrengthFormat.load(weight: set.targetWeightKg, reps: set.targetReps, seconds: set.targetSeconds)
    }

    private var trailing: String {
        if isCurrent { return "now" }
        return SetEffort(backend: set.effort)?.label ?? ""
    }

    @ViewBuilder
    private var marker: some View {
        if set.isCompleted {
            Image(systemName: "checkmark")
                .font(.system(size: 10, weight: .heavy))
                .foregroundStyle(Color.mobility)
                .frame(width: 22, height: 22)
                .background(Color.mobility.opacity(0.18), in: Circle())
                .transition(.scale(scale: 0.2).combined(with: .opacity))
        } else if isCurrent {
            Circle().strokeBorder(Color.strength, lineWidth: 2).frame(width: 22, height: 22)
        } else {
            Circle()
                .strokeBorder(Color(hex: 0x4A5263), style: StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
                .frame(width: 22, height: 22)
        }
    }
}

/// Pops up over the log button for a moment after a set is logged.
private struct LoggedToast: View {
    let logged: LoggedSet
    @State private var checked = false

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "checkmark")
                .font(.system(size: 12, weight: .heavy))
                .foregroundStyle(Color.bg)
                .frame(width: 24, height: 24)
                .background(Color.volt, in: Circle())
                .symbolEffect(.bounce, value: checked)
            Text("\(logged.label) logged")
                .font(AppFont.body(14, weight: .semibold))
                .foregroundStyle(Color.ink)
            Text(logged.load)
                .font(AppFont.number(18))
                .foregroundStyle(Color.volt)
                .monospacedDigit()
        }
        .padding(.leading, 8)
        .padding(.trailing, 16)
        .frame(height: 40)
        .background(Color.raised, in: Capsule())
        .overlay(Capsule().strokeBorder(Color.cardBorder))
        .shadow(color: .black.opacity(0.35), radius: 12, y: 4)
        .onAppear { checked = true }
        .accessibilityElement(children: .combine)
    }
}

/// Counts down between sets; turns volt when it's time to lift.
private struct RestStrip: View {
    let endsAt: Date
    let total: Int
    let onSkip: () -> Void

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            let left = Int(endsAt.timeIntervalSince(context.date).rounded(.up))
            let over = left <= 0
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .firstTextBaseline) {
                        Kicker(over ? "Rest over · go" : "Rest", color: over ? .volt : .muted)
                        Spacer()
                        Text(over ? "0:00" : StrengthFormat.clock(left))
                            .font(AppFont.number(22))
                            .foregroundStyle(over ? Color.volt : Color.ink)
                            .monospacedDigit()
                    }
                    GeometryReader { proxy in
                        Capsule().fill(Color.track).overlay(alignment: .leading) {
                            Capsule().fill(over ? Color.volt : Color.strength)
                                .frame(width: proxy.size.width * fraction(left))
                        }
                    }
                    .frame(height: 4)
                }
                Button(over ? "Hide" : "Skip", action: onSkip)
                    .buttonStyle(OutlineButtonStyle(height: 44))
                    .frame(width: 72)
            }
            // Only a fresh crossing chimes: coming back to the app long after the rest ended
            // (the notification already rang) stays quiet.
            .onChange(of: left) { old, new in
                if new > 0 || (old > 0 && new > -2) { RestAlarm.countdown(max(new, 0)) }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func fraction(_ left: Int) -> Double {
        guard total > 0 else { return 0 }
        return min(1, max(0, Double(left) / Double(total)))
    }
}

/// The hold timer: a ring that empties as the seconds run down, ticking for the last three.
private struct HoldDial: View {
    let startedAt: Date?
    let seconds: Int

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.1)) { context in
            let elapsed = startedAt.map { context.date.timeIntervalSince($0) } ?? 0
            let left = max(0, Double(seconds) - elapsed)
            let shown = Int(left.rounded(.up))
            ZStack {
                Circle().stroke(Color.track, lineWidth: 8)
                Circle()
                    .trim(from: 0, to: seconds > 0 ? left / Double(seconds) : 0)
                    .stroke(startedAt == nil ? Color.outline : Color.strength, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                VStack(spacing: 0) {
                    Text(StrengthFormat.clock(shown))
                        .font(AppFont.number(52))
                        .foregroundStyle(Color.ink)
                        .monospacedDigit()
                        .contentTransition(.numericText(countsDown: true))
                    Kicker(startedAt == nil ? "Hold" : "Holding", color: startedAt == nil ? .muted : Color(hex: 0xFF7AB5))
                        .font(AppFont.body(10, weight: .semibold))
                }
            }
            .frame(width: 168, height: 168)
            .onChange(of: shown) { _, new in
                if startedAt != nil, (1...3).contains(new) { RestAlarm.countdown(new) }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(startedAt == nil ? "Hold for \(seconds) seconds" : "Holding")
    }
}

private struct ExerciseListSheet: View {
    let session: StrengthSession
    let onSelect: (StrengthSession.Exercise) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("EXERCISES").font(AppFont.title(30)).foregroundStyle(Color.ink).padding(.bottom, 8)
            ScrollView {
                VStack(spacing: 0) {
                    ForEach(Array(session.exercises.enumerated()), id: \.element.id) { index, exercise in
                        if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                        row(exercise, index: index)
                    }
                }
            }
            .scrollIndicators(.hidden)
        }
        .padding(.horizontal, 20)
        .padding(.top, 24)
    }

    private func row(_ exercise: StrengthSession.Exercise, index: Int) -> some View {
        let isCurrent = exercise.exerciseOrder == session.currentExerciseOrder
        let working = exercise.workingSets
        return Button {
            onSelect(exercise)
        } label: {
            HStack(spacing: 12) {
                Text(String(format: "%02d", index + 1))
                    .font(AppFont.number(16))
                    .foregroundStyle(Color.strength)
                    .frame(width: 24, alignment: .leading)
                Text(exercise.exerciseName)
                    .font(AppFont.body(15, weight: isCurrent ? .semibold : .regular))
                    .foregroundStyle(Color.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if exercise.isDone {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(Color.mobility)
                } else {
                    Text("\(working.filter(\.isCompleted).count)/\(working.count)")
                        .font(AppFont.number(16))
                        .foregroundStyle(isCurrent ? Color(hex: 0xFF7AB5) : Color.muted)
                }
            }
            .frame(minHeight: 52)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    StrengthSessionView(templateId: 3).preferredColorScheme(.dark)
}
