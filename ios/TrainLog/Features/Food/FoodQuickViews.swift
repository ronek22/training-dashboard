import SwiftUI

// The top of Food: meals to log again (morning), evening picks that close the gap, ride fuel.
// Frames in docs/design/artboards/iOSFoodGap.dc.html.

// MARK: - Again

struct AgainRow: View {
    let cards: [FoodQuick.Again]
    let relogged: FoodModel.Relogged?
    let onLog: (FoodQuick.Again, String) -> Void

    private var slot: String { FoodFormat.defaultMeal() }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker("Again")
                Spacer()
                Text("Adds to \(FoodFormat.mealLabel(slot).lowercased())").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 4)
            ScrollView(.horizontal) {
                HStack(spacing: 8) {
                    ForEach(cards) { card in
                        AgainCard(card: card, done: relogged?.key == card.key ? relogged?.meal : nil) { meal in
                            onLog(card, meal)
                        }
                    }
                }
                .padding(.horizontal, 16)
            }
            .scrollIndicators(.hidden)
            .padding(.horizontal, -16)
        }
    }
}

private struct AgainCard: View {
    let card: FoodQuick.Again
    /// The meal it was just logged to.
    let done: String?
    let onLog: (String) -> Void

    var body: some View {
        Button { if done == nil { onLog(FoodFormat.defaultMeal()) } } label: {
            VStack(alignment: .leading, spacing: 6) {
                Text(done.map { "Added to \(FoodFormat.mealLabel($0).lowercased())" } ?? FoodFormat.againSource(card))
                    .font(AppFont.body(11, weight: .semibold))
                    .foregroundStyle(done == nil ? Color.muted : Color.volt)
                    .lineLimit(1)
                Text(card.title)
                    .font(AppFont.body(14, weight: .bold))
                    .foregroundStyle(Color.ink)
                    .lineLimit(2, reservesSpace: true)
                    .multilineTextAlignment(.leading)
                SplitBar(totals: card.totals)
                HStack(alignment: .firstTextBaseline, spacing: 0) {
                    Text(FoodFormat.kcal(card.totals.kcal)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                    Text(" kcal · ").font(AppFont.body(11)).foregroundStyle(Color.muted)
                    Text("\(Int(card.totals.proteinG.rounded())) g").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.mobility)
                    Spacer(minLength: 32)
                }
                .padding(.top, 2)
            }
            .padding(.horizontal, 12)
            .padding(.top, 11)
            .padding(.bottom, 12)
            .frame(width: 148, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.panel, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Radius.panel, style: .continuous).strokeBorder(done == nil ? Color.cardBorder : Color.volt))
            .overlay(alignment: .bottomTrailing) { badge.padding(10) }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .contextMenu {
            ForEach(FoodFormat.meals, id: \.value) { meal in
                Button("Add as \(meal.label.lowercased())") { onLog(meal.value) }
            }
        }
        .accessibilityLabel("\(card.title), \(FoodFormat.kcal(card.totals.kcal)) kcal")
        .accessibilityHint(done == nil ? "Logs it again" : "Logged")
    }

    @ViewBuilder
    private var badge: some View {
        if done != nil {
            Image(systemName: "checkmark")
                .font(.system(size: 12, weight: .heavy))
                .foregroundStyle(Color.bg)
                .frame(width: 28, height: 28)
                .background(Color.volt, in: Circle())
        } else {
            Image(systemName: "plus")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Color.ink)
                .frame(width: 28, height: 28)
                .overlay(Circle().strokeBorder(Color.outline))
        }
    }
}

/// A meal's kcal split as a thin stacked bar (the MacroSplit bar without the grams).
private struct SplitBar: View {
    let totals: Macros

    var body: some View {
        let shares = FoodFormat.kcalShares(totals)
        GeometryReader { geo in
            let width = geo.size.width - 4
            HStack(spacing: 2) {
                Rectangle().fill(Color.mobility).frame(width: width * shares.protein)
                Rectangle().fill(Color.ride).frame(width: width * shares.carbs)
                Rectangle().fill(Color.run)
            }
            .clipShape(Capsule())
        }
        .frame(height: 4)
    }
}

// MARK: - Close the gap

struct GapPicksCard: View {
    let gap: FoodQuick.Gap
    let selected: String?
    let onSelect: (FoodQuick.Pick) -> Void
    let onLog: (FoodQuick.Pick) -> Void

    private var current: String? { selected ?? gap.picks.first?.key }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker(FoodFormat.gapKicker(gap.focus))
                Spacer()
                Text("Logs to \(FoodFormat.mealLabel(FoodFormat.defaultMeal()).lowercased())")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.bottom, 4)
            if gap.picks.isEmpty {
                Text("Nothing you've logged fits \(FoodFormat.kcal(max(0, gap.left.kcal))) kcal and \(Int(gap.left.proteinG.rounded())) g protein. Scan this meal and it'll be here next time.")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkSoft)
                    .padding(.vertical, 8)
            }
            ForEach(gap.picks) { pick in
                Rectangle().fill(Color.cardBorder).frame(height: 1)
                row(pick, on: pick.key == current)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 16)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func row(_ pick: FoodQuick.Pick, on: Bool) -> some View {
        HStack(spacing: 12) {
            Button { onSelect(pick) } label: {
                HStack(spacing: 12) {
                    Circle()
                        .strokeBorder(on ? Color.mobility : Color.dim, lineWidth: on ? 6 : 2)
                        .frame(width: 20, height: 20)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(FoodFormat.pickTitle(pick))
                            .font(AppFont.body(14, weight: on ? .bold : .semibold))
                            .foregroundStyle(Color.ink)
                            .lineLimit(1)
                            // Keeps the portion at the end visible.
                            .truncationMode(pick.portions == 1 ? .tail : .middle)
                        (Text("+\(Int(pick.totals.proteinG.rounded())) g").font(AppFont.number(14)).foregroundStyle(Color.mobility)
                            + Text(" protein · \(FoodFormat.kcal(pick.totals.kcal)) kcal" + FoodFormat.pickNote(pick, focus: gap.focus).map { " · \($0)" }.orEmpty)
                                .font(AppFont.body(12)).foregroundStyle(Color.muted))
                            .lineLimit(1)
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(on ? .isSelected : [])
            Button { onLog(pick) } label: {
                Text("Log").padding(.horizontal, 16)
            }
                .buttonStyle(OutlineButtonStyle(height: 36))
                .fixedSize()
                .frame(minHeight: 44)
        }
        .padding(.vertical, 5)
    }
}

/// Diagonal stripes: the ghost of a pick on the ring and bars.
struct Hatch: View {
    let color: Color

    var body: some View {
        Canvas { context, size in
            context.fill(Path(CGRect(origin: .zero, size: size)), with: .color(color.opacity(0.22)))
            var path = Path()
            var x = -size.height
            while x < size.width {
                path.move(to: CGPoint(x: x, y: size.height))
                path.addLine(to: CGPoint(x: x + size.height, y: 0))
                x += 5
            }
            context.stroke(path, with: .color(color.opacity(0.75)), lineWidth: 2)
        }
    }
}

// MARK: - Ride fuel

struct FuelCard: View {
    let fuel: FoodQuick.Fuel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("On the bike · " + FoodFormat.fuelTitle(fuel.title), color: .ride).lineLimit(1)
                Spacer(minLength: 8)
                Text("\(fuel.durationMin) min").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            HStack(alignment: .firstTextBaseline, spacing: 0) {
                Text("\(Int(fuel.totalCarbsG))").font(AppFont.number(40)).foregroundStyle(Color.ink)
                Text(" g carbs").font(AppFont.number(20)).foregroundStyle(Color.ink)
                Text("~\(Int(fuel.carbsGPerH.target)) g/h · \(fuel.bottles) bottle\(fuel.bottles == 1 ? "" : "s")")
                    .font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                    .padding(.leading, 8)
            }
            .lineLimit(1)
            .padding(.top, 8)
            FuelTimeline(fuel: fuel).padding(.top, 12)
            HStack {
                Text("0")
                Spacer()
                Text("\(fuel.durationMin / 2) min")
                Spacer()
                Text("\(fuel.durationMin) min")
            }
            .font(AppFont.body(11))
            .foregroundStyle(Color.faint)
            .padding(.top, 2)
            Text("Eat in the first 20 min, then every 20; drink mix counts.")
                .font(AppFont.body(12))
                .foregroundStyle(Color.muted)
                .padding(.top, 10)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.ride.opacity(0.35)))
        .accessibilityElement(children: .combine)
    }
}

/// The ride to scale: work blocks solid, a dot with grams where to eat.
private struct FuelTimeline: View {
    let fuel: FoodQuick.Fuel

    var body: some View {
        GeometryReader { geo in
            let total = Double(max(fuel.durationMin, 1))
            let x = { (minute: Int) in geo.size.width * Double(minute) / total }
            ZStack(alignment: .leading) {
                Capsule().fill(Color.ride.opacity(0.22)).frame(height: 8)
                ForEach(Array(fuel.blocks.enumerated()), id: \.offset) { _, block in
                    if block.count == 2 {
                        RoundedRectangle(cornerRadius: 2).fill(Color.ride)
                            .frame(width: max(2, x(block[1]) - x(block[0])), height: 8)
                            .offset(x: x(block[0]))
                    }
                }
                ForEach(Array(fuel.stops.enumerated()), id: \.offset) { _, stop in
                    Text("\(Int(stop.carbsG))")
                        .font(AppFont.number(10))
                        .foregroundStyle(Color.ink)
                        .frame(width: 22, height: 22)
                        .background(Color.bg, in: Circle())
                        .overlay(Circle().strokeBorder(Color.ink, lineWidth: 2))
                        .offset(x: x(stop.min) - 11)
                }
            }
            .frame(height: geo.size.height)
        }
        .frame(height: 24)
    }
}

// MARK: - Toast

struct QuickLogToast: View {
    let relogged: FoodModel.Relogged
    let onUndo: () -> Void

    var body: some View {
        HStack {
            Text("\(FoodFormat.mealLabel(relogged.meal)) logged · \(FoodFormat.kcal(relogged.kcal)) kcal")
                .font(AppFont.body(14))
                .foregroundStyle(Color.ink)
            Spacer()
            if relogged.entryId != nil {
                Button("Undo", action: onUndo)
                    .font(AppFont.body(14, weight: .semibold))
                    .foregroundStyle(Color.volt)
                    .padding(.horizontal, 14)
                    .frame(minHeight: 44)
            }
        }
        .padding(.leading, 18)
        .padding(.trailing, 4)
        .frame(height: 52)
        .background(Color.raised, in: Capsule())
        .shadow(color: .black.opacity(0.45), radius: 12, y: 6)
    }
}

// MARK: - Formatting

extension FoodFormat {
    /// "Yesterday · breakfast", "4× in 30 days", "Saved".
    static func againSource(_ card: FoodQuick.Again) -> String {
        switch card.kind {
        case "yesterday": "Yesterday · " + mealLabel(card.meal).lowercased()
        case "favourite": "\(card.count)× in 30 days"
        default: "Saved"
        }
    }

    static func gapKicker(_ focus: String) -> String {
        switch focus {
        case "protein": "Close the gap · protein"
        case "refuel": "Refuel · after the ride"
        default: "Close the gap"
        }
    }

    /// The pick's name with its portion: grams for a single weighed food, otherwise a count.
    static func pickTitle(_ pick: FoodQuick.Pick) -> String {
        guard pick.portions != 1 else { return pick.title }
        if pick.items.count == 1, let grams = pick.items[0].grams, grams > 0 {
            return "\(pick.title) · \(Int(grams.rounded())) g"
        }
        let count = switch pick.portions {
        case 0.5: "½ portion"
        case 1.5: "1½ portions"
        default: "\(Int(pick.portions)) portions"
        }
        return "\(pick.title) · \(count)"
    }

    /// When it was last logged ("Sat", "27 Oct"), or its carbs after a ride.
    static func pickNote(_ pick: FoodQuick.Pick, focus: String, today: Date = .now) -> String? {
        if focus == "refuel" { return "\(Int(pick.totals.carbsG.rounded())) g carbs" }
        guard let last = pick.lastDate, let date = parse(last) else { return pick.source == "saved" ? "saved" : nil }
        let days = Calendar(identifier: .gregorian).dateComponents([.day], from: date, to: today).day ?? 99
        if days < 7 { return shortWeekday(last) }
        return date.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB")))
    }

    /// "Sweet spot 3 × 10 min" without the plan's "(knee-gated)" aside.
    static func fuelTitle(_ title: String) -> String {
        guard let open = title.firstIndex(of: "(") else { return title }
        return title[..<open].trimmingCharacters(in: .whitespaces)
    }

    /// Where the pick's ghost sits on a 0–1 ring: after what's eaten and the planned dinner, capped at full.
    static func ghostRange(eaten: Double, planned: Double?, ghost: Double, target: Double) -> ClosedRange<Double>? {
        guard target > 0, ghost > 0 else { return nil }
        let start = share(eaten, of: target) + (planned ?? 0) / target + (planned == nil ? 0 : 0.03)
        let end = min(1, start + ghost / target)
        return end > start ? start...end : nil
    }
}

extension Optional where Wrapped == String {
    var orEmpty: String { self ?? "" }
}
