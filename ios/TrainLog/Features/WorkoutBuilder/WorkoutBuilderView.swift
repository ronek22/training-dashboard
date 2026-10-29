import SwiftUI

/// Build or edit a strength workout (a template the Mac shares). Full screen, over Workout Studio.
struct WorkoutBuilderView: View {
    @State var model: WorkoutBuilderModel
    /// Called after a save with the result and the workout's name.
    let onSaved: (WorkoutBuilderModel.SaveResult, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var editing: EditTarget?
    @State private var adding = false
    @State private var swapping: DraftExercise?
    @State private var reordering = false
    @State private var removed: Removed?
    @State private var confirmLeave = false
    @State private var editingName = false
    @State private var editingNotes = false
    @FocusState private var nameFocused: Bool
    @FocusState private var notesFocused: Bool

    private struct EditTarget: Identifiable { let id: UUID }
    private struct Removed: Equatable {
        let exercise: DraftExercise
        let index: Int
    }

    var body: some View {
        List {
            Group {
                header
                if reordering {
                    Text("Drag to change the order. Big compound lifts usually go first.")
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.muted)
                        .padding(.horizontal, 4)
                } else {
                    if !model.draft.exercises.isEmpty { summaryCard }
                    if let nudge = model.coreNudge { nudgeCard(nudge) }
                    if model.draft.exercises.isEmpty { emptyCard }
                }
            }
            .listRowInsets(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
            .moveDisabled(true)

            ForEach(model.draft.exercises) { exercise in
                exerciseRow(exercise)
                    .listRowInsets(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
            .onMove { model.move(from: $0, to: $1) }

            Color.clear.frame(height: 90)
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
                .moveDisabled(true)
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .environment(\.editMode, .constant(reordering ? .active : .inactive))
        .animation(.snappy, value: reordering)
        .animation(.snappy, value: model.draft.exercises.map(\.id))
        .background(Color.bg)
        .safeAreaInset(edge: .top, spacing: 0) { nav }
        .overlay(alignment: .bottom) {
            if !reordering { dock }
        }
        .overlay(alignment: .bottom) {
            if let removed { undoToast(removed) }
        }
        .sheet(item: $editing) { target in
            if let index = model.draft.exercises.firstIndex(where: { $0.id == target.id }) {
                ExerciseEditorSheet(
                    exercise: $model.draft.exercises[index],
                    history: model.suggestion(named: model.draft.exercises[index].name),
                    position: "Exercise \(index + 1) of \(model.draft.exercises.count)",
                    onSwap: {
                        let exercise = model.draft.exercises[index]
                        editing = nil
                        Task {
                            try? await Task.sleep(for: .milliseconds(350))
                            swapping = exercise
                        }
                    },
                    onRemove: { remove(target.id) }
                )
                .presentationDetents([.large])
                .presentationBackground(Color.card)
                .presentationCornerRadius(34)
            }
        }
        .sheet(isPresented: $adding) {
            AddExercisesSheet(model: model) { picks, newName in
                model.add(picks)
                if let newName { model.addNew(named: newName) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.card)
            .presentationCornerRadius(34)
        }
        .sheet(item: $swapping) { exercise in
            AddExercisesSheet(model: model, swapping: exercise) { picks, _ in
                if let pick = picks.first { model.swap(exercise.id, to: pick) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.card)
            .presentationCornerRadius(34)
        }
        .confirmationDialog("Save changes to \(displayName)?", isPresented: $confirmLeave, titleVisibility: .visible) {
            Button("Save") { Task { await save() } }
            Button("Discard changes", role: .destructive) {
                model.discard()
                dismiss()
            }
            Button("Keep editing", role: .cancel) {}
        }
        .task { await model.loadSuggestions() }
        .task(id: removed) {
            guard removed != nil else { return }
            try? await Task.sleep(for: .seconds(4))
            withAnimation(.snappy) { removed = nil }
        }
        .sensoryFeedback(.impact(weight: .light), trigger: reordering)
    }

    private var displayName: String {
        model.draft.name.isEmpty ? "this workout" : model.draft.name
    }

    // MARK: Header

    private var nav: some View {
        HStack {
            if reordering {
                Color.clear.frame(width: 60, height: 1)
                Spacer()
                Text("Reorder").font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color.ink)
                Spacer()
                Button("Done") { reordering = false }
                    .font(AppFont.body(16, weight: .semibold))
                    .foregroundStyle(Color.volt)
                    .frame(width: 60, height: 44, alignment: .trailing)
            } else {
                Button("Cancel") {
                    if model.isDirty { confirmLeave = true } else { dismiss() }
                }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minHeight: 44)
                Spacer()
                Button {
                    reordering = true
                } label: {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .frame(width: 36, height: 36)
                        .background(Color(hex: 0x191D27), in: Circle())
                        .frame(width: 44, height: 44)
                }
                .disabled(model.draft.exercises.count < 2)
                .accessibilityLabel("Reorder exercises")
            }
        }
        .padding(.horizontal, 16)
        .background(Color.bg)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Kicker(model.isNew ? "New workout" : "Editing workout")
            if editingName {
                TextField("", text: $model.draft.name, prompt: Text("Name this workout").foregroundStyle(Color.faint))
                    .font(AppFont.title(36))
                    .foregroundStyle(Color.ink)
                    .textInputAutocapitalization(.words)
                    .focused($nameFocused)
                    .submitLabel(.done)
                    .onSubmit { editingName = false }
                    .onChange(of: nameFocused) { _, focused in if !focused { editingName = false } }
            } else {
                Button {
                    editingName = true
                    nameFocused = true
                } label: {
                    // The pencil rides on the last line of the name.
                    (Text((model.draft.name.isEmpty ? "Name this workout" : model.draft.name).uppercased())
                        .font(AppFont.title(38))
                        .foregroundStyle(model.draft.name.isEmpty ? Color.faint : .ink)
                     + Text("  ")
                     + Text(Image(systemName: "pencil")).font(.system(size: 15, weight: .semibold)).foregroundStyle(Color.dim))
                        .multilineTextAlignment(.leading)
                }
                .buttonStyle(.plain)
                .accessibilityHint("Rename the workout")
            }
            if !model.draft.exercises.isEmpty {
                meta
            }
            if !reordering { notes }
        }
        .padding(.horizontal, 4)
        .padding(.top, 4)
    }

    private var meta: some View {
        HStack(spacing: 0) {
            metaPart(model.draft.exercises.count, model.draft.exercises.count == 1 ? " lift" : " lifts")
            Text(" · ").foregroundStyle(Color.muted)
            metaPart(model.setCount, " work sets")
            Text(" · ").foregroundStyle(Color.muted)
            metaPart(model.durationMinutes, " min", prefix: "~")
        }
        .font(AppFont.body(13))
    }

    private func metaPart(_ value: Int, _ unit: String, prefix: String = "") -> some View {
        HStack(spacing: 0) {
            Text(prefix + "\(value)").font(AppFont.number(17)).foregroundStyle(Color.ink).contentTransition(.numericText())
            Text(unit).foregroundStyle(Color.muted)
        }
    }

    @ViewBuilder private var notes: some View {
        if editingNotes || !(model.draft.notes ?? "").isEmpty {
            TextField("", text: Binding(get: { model.draft.notes ?? "" }, set: { model.draft.notes = $0.isEmpty ? nil : $0 }),
                      prompt: Text("A note for this workout").foregroundStyle(Color.faint), axis: .vertical)
                .font(AppFont.body(13))
                .foregroundStyle(Color.inkSoft)
                .focused($notesFocused)
                .onChange(of: notesFocused) { _, focused in if !focused { editingNotes = false } }
        } else {
            Button("+ Add a note for this workout") {
                editingNotes = true
                notesFocused = true
            }
            .font(AppFont.body(13))
            .foregroundStyle(Color.muted)
            .buttonStyle(.plain)
        }
    }

    // MARK: Summary

    private var summaryCard: some View {
        let summary = model.summary
        let rows = Array(summary.counts.filter { $0.primary > 0 }.prefix(model.coreNudge == nil ? 5 : 4))
        let top = max(rows.first?.primary ?? 1, 1)
        let gap: Set<Muscle> = summary.hasCore || model.draft.exercises.count < 2 ? [] : [.abs]
        return HStack(alignment: .center, spacing: 14) {
            VStack(spacing: 4) {
                MusclePair(summary: summary, gap: gap)
                    .frame(width: 128, height: 140)
                HStack {
                    Text("FRONT").frame(maxWidth: .infinity)
                    Text("BACK").frame(maxWidth: .infinity)
                }
                .font(AppFont.body(9, weight: .semibold))
                .tracking(1)
                .foregroundStyle(Color.muted)
                .frame(width: 128)
            }
            VStack(alignment: .leading, spacing: 7) {
                Kicker("Work sets per muscle").font(AppFont.body(9, weight: .semibold))
                ForEach(rows, id: \.muscle) { count in
                    muscleBar(count.muscle.label, count.primary, fraction: Double(count.primary) / Double(top), color: .strength)
                }
                if !gap.isEmpty {
                    muscleBar("Core", 0, fraction: 0, color: .warning)
                }
                if rows.isEmpty {
                    Text("Add a lift to see what it works.").font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
        .animation(.snappy, value: summary)
    }

    private func muscleBar(_ label: String, _ sets: Int, fraction: Double, color: Color) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(AppFont.body(12))
                .foregroundStyle(color == .warning ? Color.warning : Color(hex: 0xC9CFDA))
                .lineLimit(1)
                .frame(width: 74, alignment: .leading)
            GeometryReader { proxy in
                Capsule().fill(Color(hex: 0x1A1E27))
                    .overlay(alignment: .leading) {
                        Capsule().fill(color).frame(width: proxy.size.width * fraction)
                    }
            }
            .frame(height: 6)
            Text("\(sets)")
                .font(AppFont.number(15))
                .foregroundStyle(color == .warning ? Color.warning : .ink)
                .frame(width: 18, alignment: .trailing)
        }
        .accessibilityElement(children: .combine)
    }

    private func nudgeCard(_ suggestion: ExerciseSuggestion) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Nothing for core yet").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink)
                Text(suggestion.exerciseName + (suggestion.suggestedSetCount.flatMap { sets in
                    suggestion.suggestedReps.map { " · \(sets) × \($0) last time" }
                } ?? ""))
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .lineLimit(1)
            }
            Spacer(minLength: 4)
            Button("+ Add") {
                withAnimation(.snappy) { model.add([suggestion]) }
            }
            .font(AppFont.body(13, weight: .semibold))
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 14)
            .frame(height: 34)
            .overlay(Capsule().strokeBorder(Color.outline))
            .frame(minHeight: 44)
            .buttonStyle(.plain)
            Button {
                withAnimation(.snappy) { model.nudgeDismissed = true }
            } label: {
                Image(systemName: "xmark").font(.system(size: 11, weight: .bold)).foregroundStyle(Color.faint)
                    .frame(width: 28, height: 44)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Dismiss")
        }
        .padding(.leading, 14)
        .padding(.trailing, 6)
        .padding(.vertical, 4)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Color.warning.opacity(0.28)))
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("No exercises yet")
            Text("Add lifts from your history. Each one comes with last session's sets, reps and weight.")
                .font(AppFont.body(14))
                .foregroundStyle(Color.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
        }
        .card()
    }

    // MARK: Rows

    @ViewBuilder private func exerciseRow(_ exercise: DraftExercise) -> some View {
        if reordering {
            HStack(spacing: 12) {
                Text(exercise.name).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                Spacer()
                Text("\(exercise.sets) × \(exercise.reps)").font(AppFont.number(16)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 16)
            .frame(height: 56)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.cardBorder))
        } else {
            Button {
                editing = EditTarget(id: exercise.id)
            } label: {
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(exercise.name)
                            .font(AppFont.body(15, weight: .semibold))
                            .foregroundStyle(Color.ink)
                            .multilineTextAlignment(.leading)
                        values(exercise)
                        Text(lastLine(exercise))
                            .font(AppFont.body(12))
                            .foregroundStyle(Color.faint)
                            .lineLimit(1)
                    }
                    Spacer(minLength: 4)
                    Image(systemName: "line.3.horizontal")
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(Color.dim)
                }
                .padding(.vertical, 12)
                .padding(.leading, 16)
                .padding(.trailing, 14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.cardBorder))
                .contentShape(RoundedRectangle(cornerRadius: 18))
            }
            .buttonStyle(.plain)
            .simultaneousGesture(LongPressGesture(minimumDuration: 0.45).onEnded { _ in
                if model.draft.exercises.count > 1 { reordering = true }
            })
            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                Button {
                    remove(exercise.id)
                } label: {
                    Label("Remove", systemImage: "trash")
                }
                .tint(Color(hex: 0xFF5A6E))
                Button {
                    model.duplicate(exercise.id)
                } label: {
                    Label("Copy", systemImage: "plus.square.on.square")
                }
                .tint(Color.dim)
                Button {
                    swapping = exercise
                } label: {
                    Label("Swap", systemImage: "arrow.left.arrow.right")
                }
                .tint(Color.ride)
            }
            .accessibilityHint("Opens the exercise targets")
        }
    }

    /// "3 sets  10 reps  34 kg +0.4": numbers big, units small.
    private func values(_ exercise: DraftExercise) -> some View {
        let last = model.suggestion(named: exercise.name)?.suggestedWeightKg
        let change = exercise.weightKg.flatMap { now in last.map { now - $0 } }
        return HStack(alignment: .firstTextBaseline, spacing: 14) {
            value("\(exercise.sets)", "sets")
            value("\(exercise.reps)", "reps")
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(BuilderFormat.weight(exercise.weightKg)).font(AppFont.number(22)).foregroundStyle(Color.ink)
                if exercise.weightKg != nil {
                    Text("kg").font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                if let change, abs(change) >= 0.25 {
                    Text((change > 0 ? "+" : "−") + BuilderFormat.weight(abs(change)))
                        .font(AppFont.body(12, weight: .semibold))
                        .foregroundStyle(change > 0 ? Color.mobility : .muted)
                }
            }
        }
    }

    private func value(_ number: String, _ unit: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text(number).font(AppFont.number(22)).foregroundStyle(Color.ink)
            Text(unit).font(AppFont.body(12)).foregroundStyle(Color.muted)
        }
    }

    /// "Rest 1:30 · last 33.6 kg · Good".
    private func lastLine(_ exercise: DraftExercise) -> String {
        var parts = ["Rest \(BuilderFormat.rest(exercise.restSeconds))"]
        if let history = model.suggestion(named: exercise.name) {
            if let kg = history.suggestedWeightKg, kg > 0 {
                parts.append("last \(BuilderFormat.weight(kg)) kg")
            } else if let reps = history.suggestedReps {
                parts.append("last \(reps) reps")
            }
            if let effort = SetEffort(backend: history.lastSets?.last(where: { $0.isWarmup != true })?.effort) {
                parts.append(effort.label)
            }
        } else {
            parts.append("new exercise")
        }
        return parts.joined(separator: " · ")
    }

    // MARK: Dock

    private var dock: some View {
        VStack(spacing: 6) {
            if let error = model.error {
                Text(error).font(AppFont.body(12)).foregroundStyle(Color.danger)
            }
            HStack(spacing: 10) {
                Button {
                    adding = true
                } label: {
                    Label("Exercise", systemImage: "plus")
                        .font(AppFont.body(15, weight: .semibold))
                        .foregroundStyle(Color.ink)
                        .padding(.horizontal, 18)
                        .frame(height: 52)
                        .background(Color.bg, in: Capsule())
                        .overlay(Capsule().strokeBorder(Color.outline))
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                Button {
                    Task { await save() }
                } label: {
                    if model.saving { ProgressView().tint(Color.bg) } else { Text("Save workout") }
                }
                .buttonStyle(VoltButtonStyle())
                .disabled(!model.canSave)
                .opacity(model.canSave ? 1 : 0.4)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 22)
        .padding(.bottom, 8)
        .background(
            LinearGradient(stops: [.init(color: Color.bg.opacity(0), location: 0), .init(color: Color.bg, location: 0.35)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
        )
    }

    private func undoToast(_ item: Removed) -> some View {
        HStack(spacing: 12) {
            Text("Removed \(item.exercise.name)")
                .font(AppFont.body(14, weight: .semibold))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
            Spacer()
            Button("Undo") {
                withAnimation(.snappy) {
                    model.restore((item.exercise, item.index))
                    removed = nil
                }
            }
            .font(AppFont.body(14, weight: .semibold))
            .foregroundStyle(Color.volt)
            .frame(minHeight: 44)
        }
        .padding(.horizontal, 16)
        .background(Color.raised, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Color.outline))
        .shadow(color: .black.opacity(0.45), radius: 14, y: 6)
        .padding(.horizontal, 16)
        .padding(.bottom, 92)
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    // MARK: Actions

    private func remove(_ id: DraftExercise.ID) {
        withAnimation(.snappy) {
            if let (exercise, index) = model.remove(id) {
                removed = Removed(exercise: exercise, index: index)
            }
        }
    }

    private func save() async {
        let name = model.draft.input.name
        guard let result = await model.save() else { return }
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        onSaved(result, name)
        dismiss()
    }
}
