import SwiftUI

/// Tune one lift's targets: sets, reps and kg in one strip, driven by a single ruler.
struct ExerciseEditorSheet: View {
    @Binding var exercise: DraftExercise
    let history: ExerciseSuggestion?
    let position: String
    let onSwap: () -> Void
    let onRemove: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var field: Field = .weight
    @State private var typing = false
    @State private var typed = ""
    @FocusState private var typingFocused: Bool

    enum Field: CaseIterable {
        case sets, reps, weight

        var label: String {
            switch self {
            case .sets: "Sets"
            case .reps: "Reps"
            case .weight: "Kg"
            }
        }

        var range: ClosedRange<Double> {
            switch self {
            case .sets: 1...20
            case .reps: 1...100
            case .weight: 0...400
            }
        }

        var step: Double { self == .weight ? 0.5 : 1 }
        /// Value between labels under the ruler.
        var labelEvery: Double { self == .sets ? 1 : 2 }
        /// Quick jumps under the ruler.
        var jumps: [Double] { self == .weight ? [-2.5, -1, 1, 2.5] : self == .reps ? [-2, -1, 1, 2] : [] }
    }

    private static let rests = [60, 90, 120, 180]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                nav
                header.padding(.top, 4)
                strip.padding(.top, 18)
                ValueRuler(value: binding(field), range: field.range, step: field.step,
                           labelEvery: field.labelEvery, format: format(field))
                    .padding(.top, 12)
                    .id(field)
                if !field.jumps.isEmpty {
                    jumps.padding(.top, 8)
                }
                rest.padding(.top, 18)
                if let trend = history?.recentSessions, !trend.isEmpty {
                    trendCard(trend).padding(.top, 14)
                }
                note.padding(.top, 12)
                footer.padding(.top, 14)
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 28)
        }
        .scrollIndicators(.hidden)
        .background(Color.card)
        .sensoryFeedback(.selection, trigger: field)
        // Bodyweight lifts are tuned by reps.
        .onAppear { if exercise.weightKg == nil { field = .reps } }
    }

    private var nav: some View {
        HStack {
            Button {
                onSwap()
            } label: {
                Label("Swap", systemImage: "arrow.left.arrow.right")
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .frame(minHeight: 44)
            }
            Spacer()
            Button("Done") { dismiss() }
                .font(AppFont.body(16, weight: .semibold))
                .foregroundStyle(Color.volt)
                .frame(minHeight: 44)
        }
        .padding(.top, 8)
    }

    private var header: some View {
        let mapping = MuscleRules.classify(exercise.name)
        let summary = MuscleSummary([(exercise.name, 1)])
        return HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                Kicker(position, color: .strength)
                Text(exercise.name.uppercased())
                    .font(AppFont.title(34))
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                if let mapping {
                    MuscleTags(muscles: mapping.primary + mapping.secondary.prefix(max(0, 3 - mapping.primary.count)))
                }
            }
            Spacer(minLength: 0)
            if mapping != nil {
                MuscleSilhouette(side: summary.bestSide, primary: summary.primary, secondary: summary.secondary)
                    .frame(width: 40, height: 84)
            }
        }
    }

    private var strip: some View {
        HStack(spacing: 0) {
            ForEach(Field.allCases, id: \.self) { item in
                let selected = item == field
                Button {
                    if selected {
                        typed = item == .weight && exercise.weightKg == nil ? "" : format(item)(value(item))
                        typing = true
                        typingFocused = true
                    } else {
                        commitTyping()
                        withAnimation(.snappy(duration: 0.2)) { field = item }
                    }
                } label: {
                    VStack(spacing: 6) {
                        Kicker(item == .weight && exercise.weightKg != nil && isPerArm ? "Kg · per arm" : item.label,
                               color: selected ? Color(hex: 0xFF7AB5) : .muted)
                            .font(AppFont.body(9, weight: .semibold))
                        if selected && typing {
                            TextField("", text: $typed)
                                .keyboardType(item == .weight ? .decimalPad : .numberPad)
                                .multilineTextAlignment(.center)
                                .font(AppFont.number(40))
                                .foregroundStyle(Color.ink)
                                .focused($typingFocused)
                                .onSubmit(commitTyping)
                                .frame(height: 40)
                        } else {
                            Text(format(item)(value(item)))
                                .font(AppFont.number(40))
                                .foregroundStyle(Color.ink)
                                .monospacedDigit()
                                .contentTransition(.numericText())
                                .frame(height: 40)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(selected ? Color.strength.opacity(0.08) : .clear)
                    .overlay(alignment: .bottom) {
                        if selected {
                            Capsule().fill(Color.strength).frame(height: 3).padding(.horizontal, 26)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(item.label) \(format(item)(value(item)))")
                .accessibilityHint(selected ? "Tap to type a value" : "Tap to adjust")
                if item != .weight {
                    Rectangle().fill(Color.cardBorder).frame(width: 1)
                }
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .background(Color.inset)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.cardBorder))
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done", action: commitTyping).foregroundStyle(Color.volt)
            }
        }
        .onChange(of: typingFocused) { _, focused in
            if !focused { commitTyping() }
        }
    }

    private var jumps: some View {
        HStack(spacing: 6) {
            ForEach(field.jumps, id: \.self) { jump in
                Button {
                    withAnimation(.snappy) {
                        let next = value(field) + jump
                        binding(field).wrappedValue = min(max(next, field.range.lowerBound), field.range.upperBound)
                    }
                } label: {
                    Text((jump > 0 ? "+" : "−") + BuilderFormat.weight(abs(jump)))
                        .font(AppFont.body(12, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .padding(.horizontal, 12)
                        .frame(minWidth: 50, minHeight: 32)
                        .overlay(Capsule().strokeBorder(Color.outline))
                        .frame(minHeight: 44)
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity)
    }

    private var rest: some View {
        let options = Self.rests.contains(exercise.restSeconds) ? Self.rests : (Self.rests + [exercise.restSeconds]).sorted()
        return HStack(spacing: 6) {
            Kicker("Rest").font(AppFont.body(10, weight: .semibold)).frame(width: 42, alignment: .leading)
            ForEach(options, id: \.self) { seconds in
                let selected = seconds == exercise.restSeconds
                Button {
                    exercise.restSeconds = seconds
                } label: {
                    Text(BuilderFormat.rest(seconds))
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(selected ? Color(hex: 0xFF9AC6) : .inkSoft)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(selected ? Color.strength.opacity(0.14) : .clear, in: Capsule())
                        .overlay(Capsule().strokeBorder(selected ? Color.strength : .outline))
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .sensoryFeedback(.selection, trigger: exercise.restSeconds)
            }
        }
    }

    private func trendCard(_ trend: [ExerciseSuggestion.RecentSession]) -> some View {
        let target = exercise.weightKg ?? 0
        let weights = trend.map(\.weightKg) + (target > 0 ? [target] : [])
        let top = max(weights.max() ?? 1, 1)
        // Bars start a little under the lightest session so small changes show.
        let floor = (weights.min() ?? 0) * 0.75
        let scale = { (kg: Double) in (kg - floor) / max(top - floor, 0.1) }
        let lastSets = (history?.lastSets ?? []).filter { $0.isWarmup != true }
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Kicker("Working weight · last \(trend.count)").font(AppFont.body(10, weight: .semibold))
                Spacer()
                if let history {
                    Button("Use last session") {
                        withAnimation(.snappy) {
                            exercise.sets = min(max(history.suggestedSetCount ?? exercise.sets, 1), 20)
                            exercise.reps = history.suggestedReps ?? exercise.reps
                            exercise.weightKg = history.suggestedWeightKg.flatMap { $0 > 0 ? $0 : nil }
                        }
                    }
                    .font(AppFont.body(13, weight: .semibold))
                    .foregroundStyle(Color.volt)
                    .frame(minHeight: 32)
                }
            }
            HStack(alignment: .bottom, spacing: 6) {
                ForEach(Array(trend.enumerated()), id: \.offset) { index, session in
                    let last = index == trend.count - 1
                    bar(height: scale(session.weightKg), fill: last ? Color.strength : Color.outline,
                        label: last ? BuilderFormat.weight(session.weightKg) : month(session.date, previous: index > 0 ? trend[index - 1].date : nil),
                        labelColor: last ? Color(hex: 0xFF7AB5) : .faint)
                }
                if target > 0 {
                    VStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 5)
                            .strokeBorder(Color.strength, style: StrokeStyle(lineWidth: 1.5, dash: [4, 3]))
                            .frame(height: max(8, 52 * scale(target)))
                        Text(BuilderFormat.weight(target)).font(AppFont.body(10, weight: .semibold)).foregroundStyle(Color.ink)
                            .frame(height: 12)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .frame(height: 70, alignment: .bottom)
            if !lastSets.isEmpty {
                Text("Last: " + lastSets.compactMap { $0.reps.map(String.init) }.joined(separator: " · ") + " reps"
                     + efforts(lastSets))
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
            }
        }
        .padding(14)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
    }

    private func bar(height: Double, fill: Color, label: String, labelColor: Color) -> some View {
        VStack(spacing: 4) {
            UnevenRoundedRectangle(topLeadingRadius: 5, bottomLeadingRadius: 2, bottomTrailingRadius: 2, topTrailingRadius: 5)
                .fill(fill)
                .frame(height: max(8, 52 * height))
            Text(label).font(AppFont.body(10, weight: .medium)).foregroundStyle(labelColor).frame(height: 12)
        }
        .frame(maxWidth: .infinity)
    }

    private var note: some View {
        TextField("", text: Binding(get: { exercise.notes ?? "" }, set: { exercise.notes = $0.isEmpty ? nil : $0 }),
                  prompt: Text("Note · e.g. “elbow tucked, pause at top”").foregroundStyle(Color.faint), axis: .vertical)
            .font(AppFont.body(14))
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 12)
            .frame(minHeight: 44)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.cardBorder))
    }

    private var footer: some View {
        HStack(alignment: .center) {
            Text("Starting target. Your effort taps move it after each session.")
                .font(AppFont.body(12))
                .foregroundStyle(Color.muted)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 12)
            Button("Remove", role: .destructive) {
                onRemove()
                dismiss()
            }
            .font(AppFont.body(14, weight: .semibold))
            .foregroundStyle(Color(hex: 0xFF5A6E))
            .frame(minHeight: 44)
        }
    }

    // MARK: Values

    private var isPerArm: Bool {
        exercise.name.lowercased().contains("dumbbell") || exercise.name.lowercased().hasPrefix("db ")
    }

    private func value(_ field: Field) -> Double {
        switch field {
        case .sets: Double(exercise.sets)
        case .reps: Double(exercise.reps)
        case .weight: exercise.weightKg ?? 0
        }
    }

    private func binding(_ field: Field) -> Binding<Double> {
        Binding {
            value(field)
        } set: { new in
            switch field {
            case .sets: exercise.sets = Int(new)
            case .reps: exercise.reps = Int(new)
            case .weight: exercise.weightKg = new > 0 ? new : nil
            }
        }
    }

    private func format(_ field: Field) -> (Double) -> String {
        field == .weight ? { BuilderFormat.weight($0) } : { String(Int($0)) }
    }

    private func commitTyping() {
        guard typing else { return }
        typing = false
        typingFocused = false
        let text = typed.replacingOccurrences(of: ",", with: ".").trimmingCharacters(in: .whitespaces)
        if field == .weight, text.isEmpty || text.uppercased() == "BW" {
            exercise.weightKg = nil
            return
        }
        guard let number = Double(text) else { return }
        let snapped = (number / field.step).rounded() * field.step
        binding(field).wrappedValue = min(max(snapped, field.range.lowerBound), field.range.upperBound)
    }

    private func month(_ date: String, previous: String?) -> String {
        guard let day = FoodFormat.parse(date) else { return "" }
        if let previous, previous.prefix(7) == date.prefix(7) { return "" }
        return day.formatted(.dateTime.month(.abbreviated))
    }

    private func efforts(_ sets: [ExerciseSuggestion.LastSet]) -> String {
        let labels = sets.compactMap { SetEffort(backend: $0.effort)?.label }
        return labels.isEmpty ? "" : " · " + labels.joined(separator: ", ")
    }
}

/// Drag left or right to step a value; the centre line marks it. 44 pt − / + on either side.
struct ValueRuler: View {
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let labelEvery: Double
    let format: (Double) -> String
    @State private var dragStart: Double?

    private let spacing: CGFloat = 13

    var body: some View {
        HStack(spacing: 8) {
            stepButton("minus", -step)
            Canvas { context, size in
                let mid = size.width / 2
                let count = Int(mid / spacing) + 1
                for index in -count...count {
                    let tick = value + Double(index) * step
                    guard range.contains(tick) else { continue }
                    let x = mid + CGFloat(index) * spacing
                    let major = isMultiple(tick, of: 1)
                    let height: CGFloat = major ? 18 : 10
                    let rect = CGRect(x: x - 0.75, y: size.height - 18 - height, width: 1.5, height: height)
                    context.fill(Path(roundedRect: rect, cornerRadius: 0.75), with: .color(major ? Color(hex: 0x5A6275) : .dim))
                    if isMultiple(tick, of: labelEvery) {
                        let text = Text(format(tick))
                            .font(AppFont.number(13))
                            .foregroundStyle(index == 0 ? Color.ink : .faint)
                        context.draw(text, at: CGPoint(x: x, y: size.height - 7))
                    }
                }
                let needle = CGRect(x: mid - 1.5, y: size.height - 52, width: 3, height: 34)
                context.fill(Path(roundedRect: needle, cornerRadius: 1.5), with: .color(.strength))
            }
            .frame(height: 54)
            .mask(LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.22),
                                         .init(color: .black, location: 0.78), .init(color: .clear, location: 1)],
                                 startPoint: .leading, endPoint: .trailing))
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { drag in
                        let start = dragStart ?? value
                        if dragStart == nil { dragStart = start }
                        let steps = (-drag.translation.width / spacing).rounded()
                        set(start + steps * step)
                    }
                    .onEnded { _ in dragStart = nil }
            )
            .accessibilityElement()
            .accessibilityValue(format(value))
            .accessibilityAdjustableAction { direction in
                set(value + (direction == .increment ? step : -step))
            }
            stepButton("plus", step)
        }
        .sensoryFeedback(.selection, trigger: value)
    }

    private func stepButton(_ icon: String, _ delta: Double) -> some View {
        Button {
            withAnimation(.snappy) { set(value + delta) }
        } label: {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .frame(width: 44, height: 44)
                .overlay(Circle().strokeBorder(Color.outline))
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .buttonRepeatBehavior(.enabled)
        .accessibilityLabel(delta > 0 ? "More" : "Less")
    }

    private func set(_ new: Double) {
        let snapped = (new / step).rounded() * step
        let clamped = min(max(snapped, range.lowerBound), range.upperBound)
        if clamped != value { value = clamped }
    }

    private func isMultiple(_ value: Double, of unit: Double) -> Bool {
        abs(value / unit - (value / unit).rounded()) < 0.001
    }
}

/// Pink muscle tags under a lift's name.
struct MuscleTags: View {
    let muscles: [Muscle]
    var color: Color = Color(hex: 0xFF7AB5)

    var body: some View {
        HStack(spacing: 4) {
            ForEach(muscles, id: \.self) { muscle in
                Text(muscle.label.uppercased())
                    .font(AppFont.body(10, weight: .bold))
                    .tracking(0.8)
                    .foregroundStyle(color)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(color.opacity(0.12), in: RoundedRectangle(cornerRadius: 6))
                    .lineLimit(1)
                    .fixedSize()
            }
        }
    }
}
