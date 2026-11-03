import SwiftUI

/// "How it felt" for one activity: effort as the big question on a ruler, energy and soreness as
/// dot rows, pain behind a No/Yes toggle, plus a note. Opened from the Pain swipe on a row and
/// from the detail page.
struct FeedbackSheet: View {
    let title: String
    let onSave: (ActivityFeedbackInput) -> Void
    @State private var input: ActivityFeedbackInput
    @State private var hasPain: Bool
    @Environment(\.dismiss) private var dismiss

    private static let painParts = ["Knee", "Calf", "Achilles", "Shin", "Hip", "Back"]

    init(title: String, existing: ActivityFeedback?, onSave: @escaping (ActivityFeedbackInput) -> Void) {
        self.title = title
        self.onSave = onSave
        let pain = existing?.painLevel ?? 0
        _hasPain = State(initialValue: pain > 0)
        _input = State(initialValue: ActivityFeedbackInput(
            rpe: existing?.rpe ?? 5,
            energy: existing?.energy ?? 3,
            muscleSoreness: existing?.muscleSoreness ?? 2,
            painLevel: pain,
            note: existing?.note
        ))
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("Cancel") { dismiss() }
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .frame(minWidth: 52, minHeight: 44, alignment: .leading)
                Spacer()
                Text(title).font(AppFont.body(13)).foregroundStyle(Color.muted).lineLimit(1)
                Spacer()
                Color.clear.frame(width: 52, height: 44)
            }
            .padding(.horizontal, 16)
            ScrollView {
                VStack(spacing: 0) {
                    effort
                    scales.padding(.top, 22)
                    TextField("Add a note", text: note, axis: .vertical)
                        .font(AppFont.body(15))
                        .foregroundStyle(Color.ink)
                        .lineLimit(1...4)
                        .padding(12)
                        .frame(minHeight: 46)
                        .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.row))
                        .overlay(RoundedRectangle(cornerRadius: Radius.row).strokeBorder(Color.cardBorder))
                        .padding(.top, 20)
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            Button("Save") {
                onSave(input)
                dismiss()
            }
            .buttonStyle(VoltButtonStyle())
            .padding(.horizontal, 16)
            .padding(.bottom, 8)
        }
        .padding(.top, 8)
        .presentationDetents([.large])
        .presentationBackground(Color.card)
    }

    private var note: Binding<String> {
        Binding(get: { input.note ?? "" }, set: { input.note = $0.nilIfEmpty })
    }

    // MARK: Effort

    private var effort: some View {
        let (word, color) = ActivityDetailFormat.effortWord(input.rpe)
        return VStack(spacing: 0) {
            Kicker("How hard was it?")
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("\(input.rpe)").font(AppFont.number(96)).foregroundStyle(Color.ink)
                    .contentTransition(.numericText(value: Double(input.rpe)))
                Text("/10").font(AppFont.number(24)).foregroundStyle(Color.faint)
            }
            .padding(.top, 2)
            Text(word.uppercased()).font(AppFont.title(26)).foregroundStyle(color)
            Text(ActivityDetailFormat.effortHint(input.rpe)).font(AppFont.body(13)).foregroundStyle(Color.muted)
                .padding(.top, 2)
            TickRuler(value: $input.rpe, range: 1...10, color: color)
                .padding(.top, 18)
                .accessibilityElement()
                .accessibilityLabel("Effort")
                .accessibilityValue("\(input.rpe) of 10, \(word)")
                .accessibilityAdjustableAction { step(&input.rpe, in: 1...10, $0) }
        }
        .animation(Motion.quick, value: input.rpe)
    }

    // MARK: Energy, soreness, pain

    private var scales: some View {
        let energy = ActivityDetailFormat.energyWord(input.energy)
        let soreness = ActivityDetailFormat.sorenessWord(input.muscleSoreness)
        return VStack(spacing: 0) {
            DotRow(label: "Energy", word: energy.word, color: energy.color, value: $input.energy)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            DotRow(label: "Soreness", word: soreness.word, color: soreness.color, value: $input.muscleSoreness)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            pain
        }
        .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.tile, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private var pain: some View {
        let color = ActivityDetailFormat.painColor(input.painLevel)
        let word = input.painLevel == 0 ? "Pain-free" : "\(input.painLevel) of 10 · \(input.painLevel >= 4 ? "High" : "Mild")"
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Any pain?").font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                    Text(word).font(AppFont.body(12, weight: .semibold)).foregroundStyle(color)
                }
                Spacer()
                HStack(spacing: 0) {
                    toggle("No", selected: !hasPain, color: .mobility) { setPain(false) }
                    toggle("Yes", selected: hasPain, color: color) { setPain(true) }
                }
                .padding(3)
                .background(Color.chip, in: Capsule())
            }
            if hasPain {
                TickRuler(value: $input.painLevel, range: 1...10, color: color)
                    .accessibilityElement()
                    .accessibilityLabel("Pain")
                    .accessibilityValue("\(input.painLevel) of 10")
                    .accessibilityAdjustableAction { step(&input.painLevel, in: 1...10, $0) }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Self.painParts, id: \.self) { part in
                            partChip(part, color: color)
                        }
                    }
                }
            }
        }
        .padding(.leading, 14)
        .padding(.trailing, 12)
        .padding(.vertical, 10)
        .animation(Motion.quick, value: hasPain)
    }

    private func toggle(_ title: String, selected: Bool, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(AppFont.body(14, weight: selected ? .bold : .semibold))
                .foregroundStyle(selected ? Color.bg : Color.inkSoft)
                .padding(.horizontal, 18)
                .frame(height: 38)
                .background(selected ? color : .clear, in: Capsule())
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func setPain(_ on: Bool) {
        guard on != hasPain else { return }
        hasPain = on
        input.painLevel = on ? Swift.max(input.painLevel, 1) : 0
        Haptics.selection()
    }

    /// A body part chip: it lives in the note (the server has no field for it), so the detail page
    /// picks it up the same way it reads a typed one.
    private func partChip(_ part: String, color: Color) -> some View {
        let selected = (input.note ?? "").localizedCaseInsensitiveContains(part)
        return Button {
            input.note = toggled(part, in: input.note)
            Haptics.selection()
        } label: {
            Text(part)
                .font(AppFont.body(13, weight: selected ? .semibold : .regular))
                .foregroundStyle(selected ? color : Color.inkSoft)
                .padding(.horizontal, 12)
                .frame(height: 32)
                .background(selected ? color.opacity(0.12) : .clear, in: Capsule())
                .overlay(Capsule().strokeBorder(selected ? color : Color.outline))
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func toggled(_ part: String, in note: String?) -> String? {
        let note = note ?? ""
        guard note.localizedCaseInsensitiveContains(part) else {
            return note.isEmpty ? part : "\(part). \(note)"
        }
        return note
            .replacingOccurrences(of: "\(part). ", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: part, with: "", options: .caseInsensitive)
            .trimmingCharacters(in: CharacterSet(charactersIn: " .,"))
            .nilIfEmpty
    }

    private func step(_ value: inout Int, in range: ClosedRange<Int>, _ direction: AccessibilityAdjustmentDirection) {
        switch direction {
        case .increment: value = Swift.min(value + 1, range.upperBound)
        case .decrement: value = Swift.max(value - 1, range.lowerBound)
        @unknown default: break
        }
    }
}

/// A row of tick marks with numbers: tap or drag to pick, a haptic tick on each step.
private struct TickRuler: View {
    @Binding var value: Int
    let range: ClosedRange<Int>
    let color: Color

    var body: some View {
        GeometryReader { geo in
            let count = range.count
            let column = geo.size.width / CGFloat(count)
            ZStack(alignment: .leading) {
                Rectangle()
                    .fill(color.opacity(0.10))
                    .frame(width: column * (CGFloat(value - range.lowerBound) + 0.5))
                HStack(spacing: 0) {
                    ForEach(Array(range), id: \.self) { step in
                        let selected = step == value
                        VStack(spacing: 6) {
                            Spacer(minLength: 0)
                            RoundedRectangle(cornerRadius: 2)
                                .fill(selected ? color : Color.dim)
                                .frame(width: selected ? 4 : 2, height: selected ? 30 : 14)
                            Text("\(step)")
                                .font(AppFont.number(selected ? 15 : 13, weight: selected ? .bold : .semibold))
                                .foregroundStyle(selected ? color : Color.faint)
                        }
                        .frame(width: column)
                        .padding(.bottom, 8)
                    }
                }
            }
            .frame(width: geo.size.width, height: geo.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { drag in
                let picked = range.lowerBound + Int((drag.location.x / column).rounded(.down))
                let clamped = Swift.min(Swift.max(picked, range.lowerBound), range.upperBound)
                if clamped != value {
                    value = clamped
                    Haptics.selection()
                }
            })
        }
        .frame(height: 64)
        .background(Color.inset)
        .clipShape(RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.tile, style: .continuous).strokeBorder(Color.cardBorder))
    }
}

/// "Energy · Good" and five dots, filled up to the pick; each dot is a 44pt target.
private struct DotRow: View {
    let label: String
    let word: String
    let color: Color
    @Binding var value: Int

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                Text(word).font(AppFont.body(12, weight: .semibold)).foregroundStyle(color)
            }
            Spacer(minLength: 8)
            HStack(spacing: 0) {
                ForEach(1...5, id: \.self) { step in
                    Button {
                        value = step
                        Haptics.selection()
                    } label: {
                        Circle()
                            .fill(step <= value ? color : Color.track)
                            .overlay(Circle().strokeBorder(step <= value ? .clear : Color.outline))
                            .frame(width: 18, height: 18)
                            .padding(3)
                            .overlay(Circle().strokeBorder(step == value ? color : .clear, lineWidth: 2))
                            .frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.leading, 14)
        .padding(.trailing, 12)
        .padding(.vertical, 6)
        .animation(Motion.tap, value: value)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label)
        .accessibilityValue("\(value) of 5, \(word)")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: value = Swift.min(value + 1, 5)
            case .decrement: value = Swift.max(value - 1, 1)
            @unknown default: break
            }
        }
    }
}
