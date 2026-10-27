import SwiftUI

/// "How it felt" for one activity: the four scales the server needs, plus a note. Opened from the
/// Pain swipe on a row and from the detail page.
struct FeedbackSheet: View {
    let title: String
    let onSave: (ActivityFeedbackInput) -> Void
    @State private var input: ActivityFeedbackInput
    @Environment(\.dismiss) private var dismiss

    init(title: String, existing: ActivityFeedback?, onSave: @escaping (ActivityFeedbackInput) -> Void) {
        self.title = title
        self.onSave = onSave
        _input = State(initialValue: ActivityFeedbackInput(
            rpe: existing?.rpe ?? 5,
            energy: existing?.energy ?? 3,
            muscleSoreness: existing?.muscleSoreness ?? 2,
            painLevel: existing?.painLevel ?? 0,
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
                Text("How it felt").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
                Spacer()
                Color.clear.frame(width: 52, height: 44)
            }
            .padding(.horizontal, 16)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(title).font(AppFont.body(14)).foregroundStyle(Color.muted).lineLimit(1)
                    pain
                    scale("Effort · RPE", value: $input.rpe, range: 1...10, hint: input.rpe <= 3 ? "Easy" : input.rpe >= 8 ? "Hard" : nil)
                    scale("Energy", value: $input.energy, range: 1...5, hint: input.energy >= 4 ? "Fresh" : input.energy <= 2 ? "Flat" : nil)
                    scale("Soreness", value: $input.muscleSoreness, range: 1...5, hint: nil)
                    TextField("Note (optional)", text: note, axis: .vertical)
                        .font(AppFont.body(15))
                        .foregroundStyle(Color.ink)
                        .lineLimit(1...4)
                        .padding(12)
                        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
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

    /// A scale, so a slider (as in the quick log check-in).
    private var pain: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker("Pain")
                Spacer()
                Text("\(input.painLevel) / 10")
                    .font(AppFont.number(18))
                    .foregroundStyle(ActivityDetailFormat.painColor(input.painLevel))
            }
            Slider(value: Binding(get: { Double(input.painLevel) }, set: { input.painLevel = Int($0.rounded()) }),
                   in: 0...10, step: 1)
                .tint(ActivityDetailFormat.painColor(input.painLevel))
        }
    }

    private func scale(_ label: String, value: Binding<Int>, range: ClosedRange<Int>, hint: String?) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker(label)
                Spacer()
                if let hint { Text(hint).font(AppFont.body(12)).foregroundStyle(Color.muted) }
            }
            // Ten options wrap into two rows of five so each stays a 44pt+ target.
            let values = Array(range)
            let rows = values.count > 5 ? [Array(values.prefix(5)), Array(values.dropFirst(5))] : [values]
            VStack(spacing: 8) {
                ForEach(rows, id: \.self) { row in
                    HStack(spacing: 8) {
                        ForEach(row, id: \.self) { option in
                            let selected = value.wrappedValue == option
                            Button {
                                value.wrappedValue = option
                                UISelectionFeedbackGenerator().selectionChanged()
                            } label: {
                                Text("\(option)")
                                    .font(AppFont.number(20))
                                    .foregroundStyle(selected ? Color.volt : Color.ink)
                                    .frame(maxWidth: .infinity, minHeight: 46)
                                    .background(selected ? Color.volt.opacity(0.12) : Color.inset,
                                                in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                                    .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
                                        .strokeBorder(selected ? Color.volt : Color.cardBorder))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }
}
