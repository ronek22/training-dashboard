import SwiftUI

/// The morning check-in, opened from the Readiness card on Today. Weight rides along at the bottom.
struct QuickLogSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var model = QuickLogModel()
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 16) {
            topBar
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    checkin
                    weight
                    if let error = model.error {
                        Text(error).font(AppFont.body(13)).foregroundStyle(Color.danger)
                    }
                }
                .padding(.bottom, 16)
            }
            .scrollIndicators(.hidden)
            .scrollDismissesKeyboard(.interactively)
            Button {
                Task { if await model.save() { dismiss() } }
            } label: {
                if model.saving { ProgressView().tint(Color.bg) } else { Text(model.isEditing ? "Update check-in" : "Save check-in") }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(!model.canSave)
            .opacity(model.canSave || model.saving ? 1 : 0.4)
            .padding(.bottom, 8)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .task { await model.load() }
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
            Text("Check-in").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 52, height: 44)
        }
    }

    // MARK: Check-in

    @ViewBuilder private var checkin: some View {
        scale("Energy", value: $model.energy, words: QuickLogFormat.energyWords)
        scale("Sleep", value: $model.sleep, words: QuickLogFormat.sleepWords)
        scale("Stress", value: $model.stress, words: QuickLogFormat.stressWords)
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Kicker("Pain")
                Spacer()
                Text("\(model.pain) / 10").font(AppFont.number(18)).foregroundStyle(TodayFormat.painColor(model.pain))
            }
            Slider(value: Binding(get: { Double(model.pain) }, set: { model.pain = Int($0.rounded()) }), in: 0...10, step: 1)
                .tint(TodayFormat.painColor(model.pain))
                .accessibilityValue("\(model.pain) out of 10")
        }
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Sore today")
            FlowLayout(spacing: 8) {
                ForEach(QuickLogFormat.soreAreas, id: \.self) { area in
                    let on = model.soreAreas.contains(area)
                    Button(area) { model.toggleSore(area) }
                        .buttonStyle(.plain)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(on ? Color(hex: 0xFF9AC6) : Color.ink)
                        .padding(.horizontal, 16)
                        .frame(height: 44)
                        .background(on ? Color.strength.opacity(0.1) : .clear, in: Capsule())
                        .overlay(Capsule().strokeBorder(on ? Color.strength : Color.outline, lineWidth: 1))
                        .contentShape(Capsule())
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
        Toggle(isOn: $model.sick) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Feeling sick").font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                Text(model.wasSick ? "Sick mode is on. Turn off when you're back." : "Pauses the plan, keeps the streak")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
        .tint(.mobility)
        .padding(.vertical, 4)
    }

    private func scale(_ title: String, value: Binding<Int?>, words: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker(title)
                Spacer()
                Text(QuickLogFormat.word(value.wrappedValue, in: words)).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            HStack(spacing: 8) {
                ForEach(1...5, id: \.self) { n in
                    let on = value.wrappedValue == n
                    Button {
                        value.wrappedValue = n
                        UISelectionFeedbackGenerator().selectionChanged()
                    } label: {
                        Text("\(n)")
                            .font(AppFont.number(20))
                            .foregroundStyle(on ? Color.volt : Color.inkSoft)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(on ? Color.volt.opacity(0.14) : .clear, in: RoundedRectangle(cornerRadius: 12))
                            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(on ? Color.volt : Color.outline, lineWidth: 1))
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(title) \(n), \(words[n - 1])")
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
    }

    // MARK: Weight

    @ViewBuilder private var weight: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker("Weight")
                Spacer()
                Text("Optional").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                TextField(model.lastWeight.map { QuickLogFormat.decimal($0.value) } ?? "0.0", text: $model.weight)
                    .keyboardType(.decimalPad)
                    .focused($focused)
                    .font(AppFont.number(32))
                    .foregroundStyle(Color.ink)
                Text("kg").font(AppFont.number(18, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity, minHeight: 60, alignment: .leading)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
            .contentShape(Rectangle())
            .onTapGesture { focused = true }
            if let last = model.lastWeight {
                Text("Last: \(QuickLogFormat.decimal(last.value)) kg on \(last.date)")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
    }
}

/// Wraps chips onto as many rows as they need.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        return CGSize(width: proposal.width ?? rows.map(\.width).max() ?? 0,
                      height: rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(rows.count - 1, 0)))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in arrange(width: bounds.width, subviews: subviews) {
            var x = bounds.minX
            for index in row.indices {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row {
        var indices: [Int] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> [Row] {
        var rows = [Row()]
        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            if !rows[rows.count - 1].indices.isEmpty && rows[rows.count - 1].width + spacing + size.width > width {
                rows.append(Row())
            }
            var row = rows[rows.count - 1]
            row.width += (row.indices.isEmpty ? 0 : spacing) + size.width
            row.height = max(row.height, size.height)
            row.indices.append(index)
            rows[rows.count - 1] = row
        }
        return rows
    }
}
