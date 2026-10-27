import SwiftUI

/// Frame 02: one set at a time, full screen, no tab bar.
struct StrengthSessionView: View {
    @State private var model: StrengthSessionModel
    @State private var showClose = false
    @State private var showExercises = false
    @State private var editingWeight = false
    @State private var weightText = ""
    @Environment(\.dismiss) private var dismiss

    init(templateId: Int?) {
        _model = State(initialValue: StrengthSessionModel(templateId: templateId))
    }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            switch model.phase {
            case .loading:
                ProgressView().tint(.muted).frame(maxWidth: .infinity, maxHeight: .infinity)
            case .failed(let message):
                failed(message)
            case .ready, .closed:
                if let session = model.session { content(session) }
            }
        }
        .background(Color.bg.ignoresSafeArea())
        .task { await model.load() }
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
            circleButton("xmark", label: "Close workout") { showClose = true }
            Spacer()
            VStack(spacing: 3) {
                Text((model.session?.templateName ?? "Strength").uppercased())
                    .font(AppFont.body(10, weight: .semibold))
                    .tracking(1.4)
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
                if let startedAt = model.startedAt {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        Text(StrengthFormat.clock(Int(context.date.timeIntervalSince(startedAt))))
                            .font(AppFont.number(20))
                            .foregroundStyle(Color.ink)
                            .monospacedDigit()
                    }
                }
            }
            Spacer()
            circleButton("line.3.horizontal", label: "All exercises") { showExercises = true }
                .disabled(model.session == nil)
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .padding(.bottom, 12)
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
                    setCard(current.exercise, current.set)
                    setList(current.exercise, currentId: current.set.id)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
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
        return VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker(title)
                Spacer()
                Text("Target \(StrengthFormat.load(weight: set.targetWeightKg, reps: set.targetReps))")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
            }
            HStack(spacing: 10) {
                stepper(
                    label: "Weight · kg",
                    value: StrengthFormat.weight(model.draftWeight),
                    minus: { model.adjustWeight(by: -1) },
                    plus: { model.adjustWeight(by: 1) },
                    onTapValue: {
                        weightText = model.draftWeight.map(TodayFormat.number) ?? ""
                        editingWeight = true
                    }
                )
                stepper(
                    label: "Reps",
                    value: "\(model.draftReps)",
                    minus: { model.adjustReps(by: -1) },
                    plus: { model.adjustReps(by: 1) },
                    onTapValue: nil
                )
            }
            .padding(.top, 14)
            Kicker("How did it feel?").font(AppFont.body(10, weight: .semibold)).padding(.top, 16)
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
    }

    private func stepper(
        label: String, value: String, minus: @escaping () -> Void, plus: @escaping () -> Void, onTapValue: (() -> Void)?
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(label).font(AppFont.body(9, weight: .semibold))
            HStack(spacing: 0) {
                stepButton("minus", label: "Less \(label)", action: minus)
                Spacer(minLength: 0)
                Text(value)
                    .font(AppFont.number(48))
                    .foregroundStyle(Color.ink)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                    .contentTransition(.numericText())
                    .onTapGesture { onTapValue?() }
                    .accessibilityLabel("\(label) \(value)")
                    .accessibilityAddTraits(onTapValue == nil ? [] : .isButton)
                Spacer(minLength: 0)
                stepButton("plus", label: "More \(label)", action: plus)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
    }

    private func stepButton(_ icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button {
            withAnimation(.snappy) { action() }
        } label: {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .frame(width: 34, height: 34)
                .overlay(Circle().strokeBorder(Color.outline))
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .buttonRepeatBehavior(.enabled)
        .sensoryFeedback(.selection, trigger: model.draftWeight)
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
                    draftReps: model.draftReps
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
            }
            if model.allSetsDone {
                Button("Finish workout") { Task { await model.finish() } }
                    .buttonStyle(VoltButtonStyle())
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
        .background(Color.bg.opacity(0.94).ignoresSafeArea(edges: .bottom))
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
        if set.isCompleted { return StrengthFormat.load(weight: set.actualWeightKg, reps: set.actualReps ?? set.targetReps) }
        if isCurrent { return StrengthFormat.load(weight: draftWeight, reps: draftReps) }
        return StrengthFormat.load(weight: set.targetWeightKg, reps: set.targetReps)
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
        } else if isCurrent {
            Circle().strokeBorder(Color.strength, lineWidth: 2).frame(width: 22, height: 22)
        } else {
            Circle()
                .strokeBorder(Color(hex: 0x4A5263), style: StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
                .frame(width: 22, height: 22)
        }
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
            .sensoryFeedback(.warning, trigger: over) { _, isOver in isOver }
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
