import SwiftUI

/// The centre + sheet from the artboard: one place for everything quick.
struct QuickLogSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var model = QuickLogModel()
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 16) {
            topBar
            tabs
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    switch model.tab {
                    case .checkin: checkin
                    case .weight: weight
                    case .activity: activity
                    case .note: note
                    }
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
                if model.saving { ProgressView().tint(Color.bg) } else { Text(model.actionTitle) }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(!model.canSave)
            .opacity(model.canSave || model.saving ? 1 : 0.4)
            .padding(.bottom, 8)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .task { await model.load() }
        .onChange(of: model.tab) { focused = false }
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
            Text("Log").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 52, height: 44)
        }
    }

    private var tabs: some View {
        Segmented(options: QuickLogModel.Tab.allCases, selection: $model.tab) { $0.rawValue }
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
            Kicker("Body weight · this morning")
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                TextField("0.0", text: $model.weight)
                    .keyboardType(.decimalPad)
                    .focused($focused)
                    .font(AppFont.number(64))
                    .foregroundStyle(Color.ink)
                    .fixedSize()
                Text("kg").font(AppFont.number(24, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity, minHeight: 96, alignment: .leading)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Color.cardBorder))
            .onTapGesture { focused = true }
            if let last = model.lastWeight {
                Text("Last: \(QuickLogFormat.decimal(last.value)) kg on \(last.date)")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
    }

    // MARK: Activity

    @ViewBuilder private var activity: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Type")
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                ForEach(QuickLogFormat.activityTypes, id: \.self) { type in
                    let on = model.activityType == type
                    Button(type.label) { model.activityType = type }
                        .buttonStyle(.plain)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(on ? type.sport.color : Color.ink)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(on ? type.sport.color.opacity(0.12) : .clear, in: Capsule())
                        .overlay(Capsule().strokeBorder(on ? type.sport.color : Color.outline, lineWidth: 1))
                        .contentShape(Capsule())
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
        HStack(spacing: 12) {
            field("Duration", unit: "min", text: $model.duration)
            field("Distance", unit: "km", text: $model.distance)
        }
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Name")
            TextField(model.activityType.label, text: $model.activityName)
                .focused($focused)
                .font(AppFont.body(15))
                .foregroundStyle(Color.ink)
                .padding(12)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
        }
        Text("Logged for today. Use this for sessions that won't come from Strava.")
            .font(AppFont.body(12)).foregroundStyle(Color.muted)
    }

    private func field(_ title: String, unit: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(title)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                TextField("–", text: text)
                    .keyboardType(.decimalPad)
                    .focused($focused)
                    .font(AppFont.number(28))
                    .foregroundStyle(Color.ink)
                Text(unit).font(AppFont.body(13)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 12)
            .frame(minHeight: 56)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
        }
    }

    // MARK: Note

    @ViewBuilder private var note: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("For the coach")
            TextField("What should the coach know? e.g. left knee tight on stairs", text: $model.noteText, axis: .vertical)
                .focused($focused)
                .font(AppFont.body(15))
                .foregroundStyle(Color.ink)
                .lineLimit(4...10)
                .padding(12)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
        }
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Topic")
            FlowLayout(spacing: 8) {
                ForEach(QuickLogFormat.noteCategories, id: \.value) { category in
                    let on = model.noteCategory == category.value
                    Button(category.label) { model.noteCategory = category.value }
                        .buttonStyle(.plain)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(on ? Color.ink : Color.muted)
                        .padding(.horizontal, 16)
                        .frame(height: 44)
                        .background(on ? Color.raised : .clear, in: Capsule())
                        .overlay(Capsule().strokeBorder(Color.outline, lineWidth: 1))
                        .contentShape(Capsule())
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
    }
}

/// The artboard's `.seg`: an inset track with the selected option raised.
struct Segmented<Option: Hashable>: View {
    let options: [Option]
    @Binding var selection: Option
    let label: (Option) -> String

    var body: some View {
        HStack(spacing: 0) {
            ForEach(options, id: \.self) { option in
                let on = selection == option
                Button {
                    selection = option
                } label: {
                    Text(label(option))
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(on ? Color.ink : Color.muted)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(on ? Color.raised : .clear, in: RoundedRectangle(cornerRadius: 9))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
        .padding(3)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.cardBorder))
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
