import SwiftUI

// Pieces shared by the scan result (MealEstimateSheet) and a logged meal (MealEditSheet).

/// Split donut with the meal's kcal in the middle, macros listed beside it.
struct MealSummaryCard: View {
    let totals: Macros
    let target: Double?

    var body: some View {
        let shares = FoodFormat.kcalShares(totals)
        VStack(alignment: .leading, spacing: 12) {
            Kicker(target.map { "This meal · \(Int((totals.kcal / max($0, 1) * 100).rounded()))% of today" } ?? "This meal")
            HStack(spacing: 18) {
                MacroDonut(shares: [shares.protein, shares.carbs, shares.fat], colors: [.mobility, .ride, .run]) {
                    VStack(spacing: 3) {
                        Text(FoodFormat.kcal(totals.kcal)).font(AppFont.number(30)).foregroundStyle(Color.ink)
                        Text("KCAL").font(AppFont.body(10, weight: .semibold)).tracking(0.8).foregroundStyle(Color.muted)
                    }
                }
                VStack(spacing: 0) {
                    row("Protein", .mobility, totals.proteinG, shares.protein)
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    row("Carbs", .ride, totals.carbsG, shares.carbs)
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    row("Fat", .run, totals.fatG, shares.fat)
                }
            }
        }
        .card()
    }

    private func row(_ label: String, _ color: Color, _ grams: Double, _ share: Double) -> some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
            Text(label).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
            Spacer(minLength: 4)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text("\(Int(grams.rounded()))").font(AppFont.number(20)).foregroundStyle(Color.ink)
                Text("g").font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            Text("\(Int((share * 100).rounded()))%")
                .font(AppFont.body(12)).foregroundStyle(Color.muted)
                .frame(width: 34, alignment: .trailing)
        }
        .padding(.vertical, 7)
    }
}

/// Segments with small gaps between them; butt ends so each share reads cleanly.
struct MacroDonut<Center: View>: View {
    let shares: [Double]
    let colors: [Color]
    @ViewBuilder let center: Center

    private let size: CGFloat = 100
    private let width: CGFloat = 12
    private let gap = 0.012

    var body: some View {
        ZStack {
            Circle().stroke(Color.cardBorder, lineWidth: width)
            ForEach(Array(segments.enumerated()), id: \.offset) { index, segment in
                Circle()
                    .trim(from: segment.from, to: segment.to)
                    .stroke(colors[index], style: StrokeStyle(lineWidth: width, lineCap: .butt))
                    .rotationEffect(.degrees(-90))
            }
            center
        }
        .frame(width: size, height: size)
        .padding(width / 2)
    }

    private var segments: [(from: Double, to: Double)] {
        var start = 0.0
        return shares.map { share in
            defer { start += share }
            guard share > gap * 2 else { return (start, start) }
            return (start + gap / 2, start + share - gap / 2)
        }
    }
}

/// Scales the whole meal: for when you ate less or more than the photo shows.
struct PortionPicker: View {
    @Binding var factor: Double
    let grams: Double?

    static let steps: [(value: Double, label: String)] = [(0.5, "½"), (0.75, "¾"), (1, "1×"), (1.25, "1¼"), (1.5, "1½"), (2, "2×")]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Kicker("Portion")
                Spacer()
                if let grams, grams > 0 {
                    Text("≈ \(Int(grams.rounded())) g").font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
            }
            HStack(spacing: 0) {
                ForEach(Self.steps, id: \.value) { step in
                    let selected = factor == step.value
                    Button {
                        factor = step.value
                        UISelectionFeedbackGenerator().selectionChanged()
                    } label: {
                        Text(step.label)
                            .font(AppFont.body(13, weight: .semibold))
                            .foregroundStyle(selected ? Color.ink : Color.muted)
                            .frame(maxWidth: .infinity, minHeight: 36)
                            .background(selected ? Color.raised : .clear, in: RoundedRectangle(cornerRadius: 9))
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Portion \(step.label)")
                }
            }
            .padding(3)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.cardBorder))
            Text("Scales every item. Tap an item below to fine-tune it.")
                .font(AppFont.body(12)).foregroundStyle(Color.muted)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
    }
}

/// The item list: tap a row for its grams stepper.
struct Breakdown: View {
    @Binding var items: [FoodItem]
    let originals: [UUID: FoodItem]
    @State private var expanded: UUID?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Kicker("Breakdown")
                Spacer()
                Text("tap an item for grams").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 4)
            .padding(.top, 6)
            VStack(spacing: 0) {
                ForEach($items) { $item in
                    let open = expanded == item.id
                    if item.id != items.first?.id && !open && expanded != previousID(of: item.id) {
                        Rectangle().fill(Color.cardBorder).frame(height: 1)
                    }
                    ItemRow(item: $item, original: originals[item.id], expanded: open) {
                        withAnimation(.snappy(duration: 0.2)) { expanded = open ? nil : item.id }
                    } onRemove: {
                        withAnimation(.snappy(duration: 0.2)) { items.removeAll { $0.id == item.id } }
                    }
                }
                if !items.isEmpty { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                Button {
                    let item = FoodItem(name: "", kcal: 0, proteinG: 0)
                    items.append(item)
                    withAnimation(.snappy(duration: 0.2)) { expanded = item.id }
                } label: {
                    Label("Add item", systemImage: "plus")
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 4)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
        }
    }

    private func previousID(of id: UUID) -> UUID? {
        guard let index = items.firstIndex(where: { $0.id == id }), index > 0 else { return nil }
        return items[index - 1].id
    }
}

/// One item: name, grams and macros; expanded, a stepper (10 g or ½ portion a tap, hold to repeat)
/// and a chip back to Claude's own amount. Items without grams get plain kcal / protein fields.
struct ItemRow: View {
    @Binding var item: FoodItem
    let original: FoodItem?
    let expanded: Bool
    let onTap: () -> Void
    let onRemove: () -> Void

    private var usesPortions: Bool { item.portions != nil }
    private var hasAmount: Bool { usesPortions || (item.grams ?? 0) > 0 }

    var body: some View {
        VStack(spacing: 0) {
            Button(action: onTap) { summary }.buttonStyle(.plain)
            if expanded {
                editor
                    .padding(.horizontal, 6)
                    .padding(.bottom, 12)
                    .transition(.opacity)
            }
        }
        .background(expanded ? Color.inset : .clear, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            if expanded { RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color.outline) }
        }
        .padding(.horizontal, expanded ? -6 : 0)
        .padding(.vertical, expanded ? 8 : 0)
    }

    private var summary: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(item.name.isEmpty ? "New item" : item.name)
                        .font(AppFont.body(14, weight: .semibold))
                        .foregroundStyle(item.name.isEmpty ? Color.muted : Color.ink)
                        .lineLimit(1)
                    if item.confidence == "low" {
                        Text("GUESS").font(AppFont.body(10, weight: .bold)).foregroundStyle(Color(hex: 0xFFB547))
                    }
                }
                Text(amountLabel).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            Spacer(minLength: 6)
            HStack(spacing: 8) {
                Text("P \(Int(item.proteinG.rounded()))")
                Text("C \(Int(item.carbsG.rounded()))")
                Text("F \(Int(item.fatG.rounded()))")
            }
            .font(AppFont.body(11))
            .foregroundStyle(Color.muted)
            Text(FoodFormat.kcal(item.kcal))
                .font(AppFont.number(18)).foregroundStyle(Color.ink)
                .frame(minWidth: 40, alignment: .trailing)
        }
        .padding(.vertical, 11)
        .padding(.horizontal, expanded ? 6 : 0)
        .contentShape(Rectangle())
    }

    private var amountLabel: String {
        if let portions = item.portions { return "\(portions.formatted(.number.precision(.fractionLength(0...2)))) portion" }
        if let grams = item.grams, grams > 0 { return "\(Int(grams.rounded())) g" }
        return "no amount"
    }

    @ViewBuilder
    private var editor: some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                TextField("Food name", text: $item.name)
                    .font(AppFont.body(14, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .padding(.horizontal, 10)
                    .frame(minHeight: 40)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 10))
                Button(action: onRemove) {
                    Image(systemName: "trash").font(.system(size: 15)).foregroundStyle(Color.faint)
                        .frame(width: 44, height: 40)
                }
                .accessibilityLabel("Remove \(item.name)")
            }
            if hasAmount {
                stepper
                chips
            } else {
                HStack(spacing: 8) {
                    field("g", value: gramsBinding)
                    field("kcal", value: $item.kcal)
                    field("g P", value: $item.proteinG)
                }
            }
        }
    }

    private var stepper: some View {
        HStack {
            stepButton("minus", delta: usesPortions ? -0.5 : -10)
            Spacer()
            VStack(spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    Text(usesPortions ? (item.portions ?? 1).formatted(.number.precision(.fractionLength(0...2))) : "\(Int((item.grams ?? 0).rounded()))")
                        .font(AppFont.number(34)).foregroundStyle(Color.ink)
                        .contentTransition(.numericText())
                    Text(usesPortions ? "portion" : "g").font(AppFont.body(14)).foregroundStyle(Color.muted)
                }
                Text(usesPortions ? "± ½ per tap · hold to repeat" : "± 10 g per tap · hold to repeat")
                    .font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            Spacer()
            stepButton("plus", delta: usesPortions ? 0.5 : 10)
        }
        .padding(.horizontal, 6)
    }

    private func stepButton(_ symbol: String, delta: Double) -> some View {
        Button {
            withAnimation(.snappy(duration: 0.15)) {
                if usesPortions {
                    item = FoodFormat.rescale(item, portions: max(0.5, (item.portions ?? 1) + delta))
                } else {
                    item = FoodFormat.rescale(item, grams: max(5, (item.grams ?? 0) + delta))
                }
            }
            UISelectionFeedbackGenerator().selectionChanged()
        } label: {
            Image(systemName: symbol)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(Color.ink)
                .frame(width: 44, height: 44)
                .background(Color.card, in: Circle())
                .overlay(Circle().strokeBorder(Color.cardBorder))
        }
        .buttonRepeatBehavior(.enabled)
        .accessibilityLabel(delta < 0 ? "Less" : "More")
    }

    @ViewBuilder
    private var chips: some View {
        HStack(spacing: 6) {
            if !usesPortions {
                chip("−50 g") { item = FoodFormat.rescale(item, grams: max(5, (item.grams ?? 0) - 50)) }
            }
            if let original, original != item {
                chip("AI · " + (original.portions.map { "\($0.formatted()) portion" } ?? "\(Int((original.grams ?? 0).rounded())) g"), selected: true) {
                    var reset = original
                    reset.name = item.name
                    item = reset
                }
            }
            if !usesPortions {
                chip("+50 g") { item = FoodFormat.rescale(item, grams: (item.grams ?? 0) + 50) }
            }
        }
    }

    private func chip(_ label: String, selected: Bool = false, action: @escaping () -> Void) -> some View {
        Button {
            withAnimation(.snappy(duration: 0.15)) { action() }
        } label: {
            Text(label)
                .font(AppFont.body(12, weight: .semibold))
                .foregroundStyle(selected ? Color.ink : Color(hex: 0xC9CFDA))
                .padding(.horizontal, 10)
                .frame(height: 30)
                .background(selected ? Color.raised : Color(hex: 0x1B1F29), in: RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .frame(minHeight: 44)
    }

    private var gramsBinding: Binding<Double> {
        Binding(get: { item.grams ?? 0 }, set: { item = FoodFormat.rescale(item, grams: $0) })
    }

    private func field(_ unit: String, value: Binding<Double>) -> some View {
        HStack(spacing: 4) {
            TextField("0", value: value, format: .number.precision(.fractionLength(0...1)))
                .keyboardType(.decimalPad)
                .font(AppFont.number(18, weight: .semibold))
                .foregroundStyle(Color.ink)
                .multilineTextAlignment(.trailing)
            Text(unit).font(AppFont.body(11)).foregroundStyle(Color.muted)
        }
        .padding(.horizontal, 10)
        .frame(maxWidth: .infinity, minHeight: 40)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 10))
    }
}

/// "Lunch ▾": picks Breakfast · Dinner · Supper · Snack.
struct MealChip: View {
    @Binding var meal: String

    var body: some View {
        Menu {
            Picker("Meal", selection: $meal) {
                ForEach(FoodFormat.meals, id: \.value) { Text($0.label).tag($0.value) }
            }
        } label: {
            HStack(spacing: 4) {
                Text(FoodFormat.mealLabel(meal))
                Image(systemName: "chevron.down").font(.system(size: 9, weight: .bold))
            }
            .modifier(ChipStyle())
        }
        .frame(minHeight: 44)
    }
}

struct ChipStyle: ViewModifier {
    var color: Color = Color(hex: 0xC9CFDA)

    func body(content: Content) -> some View {
        content
            .font(AppFont.body(12, weight: .semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .frame(height: 26)
            .background(Color(hex: 0x1B1F29), in: RoundedRectangle(cornerRadius: 7))
    }
}

/// What's left of today after this meal, through the under-eating lens.
struct ImpactLine: View {
    let meal: Double
    let context: MealDayContext

    var body: some View {
        if let impact = FoodFormat.impact(meal: meal, eaten: context.eaten, target: context.target, dinner: context.dinner) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: impact.closes ? "checkmark.circle.fill" : "exclamationmark.circle")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(impact.closes ? Color.volt : Color(hex: 0xFFB547))
                (Text(impact.headline).foregroundStyle(Color.ink).fontWeight(.semibold)
                    + Text(impact.detail.isEmpty ? "" : " " + impact.detail).foregroundStyle(Color.muted))
                    .font(AppFont.body(13))
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(12)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
        }
    }
}
