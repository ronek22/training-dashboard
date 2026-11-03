import SwiftUI

struct FoodView: View {
    @State private var model = FoodModel.launch()
    @State private var showCamera = false
    @State private var draft: MealDraft?
    @State private var editing: FoodEntry?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                WeekStrip(dates: model.weekDates, selected: model.selectedDate, marks: model.marks) { date in
                    Task { await model.select(date) }
                } onSwipe: { weeks in
                    Task { await model.shiftDay(weeks * 7) }
                }
                if model.offline, let syncedAt = model.syncedAt {
                    OfflineNote(syncedAt: syncedAt)
                }
                if model.isToday, let fuel = model.quick?.fuel {
                    FuelCard(fuel: fuel)
                }
                if model.isToday, model.quick?.gap == nil, let cards = model.quick?.again, !cards.isEmpty {
                    AgainRow(cards: cards, relogged: model.relogged) { card, meal in
                        Task { await model.quickLog(key: card.key, items: card.items, meal: meal) }
                    }
                }
                if let day = model.day {
                    EatenCard(day: day, eaten: model.eaten, dinner: model.isToday ? model.plannedDinner : nil, isToday: model.isToday,
                              ghost: model.isToday ? model.pick?.totals : nil)
                    if model.isToday, let gap = model.quick?.gap {
                        GapPicksCard(gap: gap, selected: model.selectedPick) { pick in
                            model.selectedPick = pick.key
                        } onLog: { pick in
                            Task { await model.quickLog(key: pick.key, items: pick.items) }
                        }
                    }
                    MealTimeline(
                        entries: day.entries,
                        pending: model.pending.filter { $0.date == model.selectedDate },
                        dinner: model.plannedDinner,
                        onLogDinner: { Task { await model.logPlannedDinner() } },
                        onAteElse: { draft = MealDraft(photo: nil, meal: FoodFormat.plannedMeal) },
                        onEdit: { editing = $0 },
                        onDelete: { entry in Task { await model.delete(entry) } }
                    )
                } else if let error = model.error {
                    SyncStateCard(kicker: "Not synced yet", message: error)
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 88)
        }
        .scrollIndicators(.hidden)
        .overlay(alignment: .top) {
            Color.bg.frame(height: 0).background(Color.bg).allowsHitTesting(false)
        }
        .background(Color.bg)
        .overlay(alignment: .bottomTrailing) {
            if let relogged = model.relogged {
                QuickLogToast(relogged: relogged) { Task { await model.undoQuickLog() } }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task(id: relogged) {
                        try? await Task.sleep(for: .seconds(5))
                        if !Task.isCancelled { await model.finishQuickLog() }
                    }
            } else {
                scanButton
            }
        }
        .animation(Motion.state, value: model.relogged)
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
        .task { await model.load() }
        .fullScreenCover(isPresented: $showCamera) {
            CameraPicker { image in
                showCamera = false
                if let image { draft = MealDraft(photo: image) }
            }
            .ignoresSafeArea()
        }
        .sheet(item: $draft) { draft in
            MealEstimateSheet(draft: draft, date: model.selectedDate, context: dayContext) { entry in
                Task { await model.save(entry) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.bg)
        }
        .sheet(item: $editing) { entry in
            MealEditSheet(entry: entry, context: dayContext) { input in
                Task { await model.update(entry, with: input) }
            } onDelete: {
                Task { await model.delete(entry) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.bg)
        }
    }

    private var dayContext: MealDayContext {
        MealDayContext(
            eaten: model.eaten.kcal,
            target: model.day?.target?.kcal,
            dinner: model.isToday ? model.plannedDinner?.kcal : nil
        )
    }

    private var header: some View {
        ScreenHeader(kicker: FoodFormat.dayKicker(model.selectedDate, kind: model.day?.target?.dayKind), title: "Food") {
            if !model.isToday {
                Button { Task { await model.select(FoodFormat.iso(.now)) } } label: {
                    Text("Today").padding(.horizontal, 14)
                }
                .buttonStyle(OutlineButtonStyle(height: 34))
                .fixedSize()
                .frame(minHeight: 44)
                .padding(.bottom, 2)
            }
        }
    }

    /// The one volt action: camera straight away. The round button describes a meal in words
    /// (or picks a library photo) instead.
    private var scanButton: some View {
        HStack(spacing: 10) {
            Button {
                draft = MealDraft(photo: nil)
            } label: {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 52, height: 52)
                    .background(Color.chip, in: Circle())
                    .overlay(Circle().strokeBorder(Color.outline))
            }
            .accessibilityLabel("Describe a meal")
            Button {
                showCamera = true
            } label: {
                Label("Scan", systemImage: "viewfinder")
                    .font(AppFont.body(16, weight: .bold))
                    .foregroundStyle(Color.bg)
                    .padding(.leading, 16)
                    .padding(.trailing, 20)
                    .frame(height: 52)
                    .background(Color.volt, in: Capsule())
            }
            .accessibilityLabel("Scan a meal")
        }
        .shadow(color: .black.opacity(0.45), radius: 12, y: 6)
        .padding(.trailing, 16)
        .padding(.bottom, 16)
    }

}

/// A meal being estimated: a camera photo, or nil to describe it in words.
struct MealDraft: Identifiable {
    let id = UUID()
    let photo: UIImage?
    var meal: String? = nil
}

/// What the day looks like around a meal, for the "after this" line on the result.
struct MealDayContext {
    let eaten: Double
    let target: Double?
    let dinner: Double?
}

// MARK: - Week strip

private struct WeekStrip: View {
    let dates: [String]
    let selected: String
    let marks: [String: FoodFormat.DayMark]
    let onSelect: (String) -> Void
    let onSwipe: (Int) -> Void

    private let today = FoodFormat.iso(.now)

    var body: some View {
        HStack(spacing: 6) {
            ForEach(dates, id: \.self) { date in
                day(date)
            }
        }
        .gesture(
            DragGesture(minimumDistance: 24).onEnded { value in
                if value.translation.width > 50 { onSwipe(-1) }
                if value.translation.width < -50, !dates.contains(today) { onSwipe(1) }
            }
        )
    }

    private func day(_ date: String) -> some View {
        let isSelected = date == selected
        let future = date > today
        let parsed = FoodFormat.parse(date)
        return Button { onSelect(date) } label: {
            VStack(spacing: 3) {
                Text(parsed?.formatted(.dateTime.weekday(.abbreviated).locale(Locale(identifier: "en_GB"))) ?? "")
                    .font(AppFont.body(11, weight: .semibold))
                    .foregroundStyle(isSelected ? Color.bg : Color.muted)
                Text(parsed?.formatted(.dateTime.day()) ?? "")
                    .font(AppFont.number(20))
                    .foregroundStyle(isSelected ? Color.bg : Color.inkBody)
                Circle()
                    .fill(dotColor(date, selected: isSelected))
                    .frame(width: 6, height: 6)
            }
            .frame(maxWidth: .infinity, minHeight: 62)
            .background(isSelected ? Color.ink : .clear, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(future)
        .opacity(future ? 0.45 : 1)
        .accessibilityLabel(parsed?.formatted(date: .complete, time: .omitted) ?? date)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private func dotColor(_ date: String, selected: Bool) -> Color {
        switch marks[date] {
        case .hit: .volt
        case .short: Color.amber
        case nil: selected ? Color.bg.opacity(0.0) : .clear
        }
    }
}

// MARK: - Eaten

private struct EatenCard: View {
    let day: FoodDay
    let eaten: Macros
    let dinner: DinnerWeek.Day?
    let isToday: Bool
    /// The selected evening pick, drawn as a striped ghost on the ring and bars.
    var ghost: Macros? = nil

    private var target: Double? { day.target?.kcal }
    private var dinnerKcal: Double? { dinner?.kcal }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 0) {
                    Kicker(isToday ? "Eaten today" : "Eaten")
                    Text(FoodFormat.kcal(eaten.kcal)).font(AppFont.number(54)).foregroundStyle(Color.ink).padding(.top, 8)
                    Text(target.map { "of \(FoodFormat.kcal($0)) kcal" } ?? "kcal")
                        .font(AppFont.body(13)).foregroundStyle(Color.muted).padding(.top, 2)
                    if let target {
                        legend(target).padding(.top, 12)
                    }
                }
                Spacer(minLength: 0)
                if let target {
                    CalorieRing(eaten: eaten.kcal, target: target, planned: dinnerKcal, ghost: ghost?.kcal)
                }
            }
            if ghost == nil, let target, let dinnerKcal, target > eaten.kcal {
                afterDinner(short: target - eaten.kcal - dinnerKcal).padding(.top, 12)
            }
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.vertical, 14)
            HStack(alignment: .top, spacing: 0) {
                MacroColumn(label: "Protein", value: eaten.proteinG, target: day.proteinTargetG, color: .mobility,
                            share: FoodFormat.kcalShares(eaten).protein, ghost: ghost?.proteinG)
                divider
                MacroColumn(label: "Carbs", value: eaten.carbsG, target: day.target?.carbsG, color: .ride,
                            share: FoodFormat.kcalShares(eaten).carbs, ghost: ghost?.carbsG)
                divider
                MacroColumn(label: "Fat", value: eaten.fatG, target: nil, color: .run,
                            share: FoodFormat.kcalShares(eaten).fat)
            }
        }
        .card()
    }

    private var divider: some View {
        Rectangle().fill(Color.cardBorder).frame(width: 1).padding(.horizontal, 10)
    }

    private func legend(_ target: Double) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            legendRow(swatch: RoundedRectangle(cornerRadius: 3).fill(Color.volt).frame(width: 10, height: 10),
                      label: "Eaten", value: FoodFormat.share(eaten.kcal, of: target))
            if let dinnerKcal {
                legendRow(swatch: Capsule().fill(Color.volt.opacity(0.8)).frame(width: 10, height: 3).frame(height: 10),
                          label: "Dinner ~\(FoodFormat.kcal(dinnerKcal))", value: dinnerKcal / target)
            }
            if let ghost {
                legendRow(swatch: Hatch(color: .volt).frame(width: 10, height: 10).clipShape(RoundedRectangle(cornerRadius: 3)),
                          label: "Pick", value: ghost.kcal / target, signed: true)
            }
        }
        .frame(width: 150, alignment: .leading)
    }

    private func legendRow(swatch: some View, label: String, value: Double, signed: Bool = false) -> some View {
        HStack(spacing: 8) {
            swatch
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.inkSoft)
            Spacer(minLength: 4)
            Text("\(signed ? "+" : "")\(Int((value * 100).rounded()))%").font(AppFont.number(15)).foregroundStyle(Color.ink)
        }
    }

    @ViewBuilder
    private func afterDinner(short: Double) -> some View {
        if short > 0 {
            (Text("After dinner you're still ").foregroundStyle(Color.muted)
                + Text("\(FoodFormat.kcal(short)) kcal short").foregroundStyle(Color.warning).fontWeight(.semibold)
                + Text(".").foregroundStyle(Color.muted))
                .font(AppFont.body(12))
        } else {
            Text("Planned dinner closes the gap.").font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.volt)
        }
    }
}

/// Eaten as a solid volt arc, the planned dinner as a thin arc after it, kcal to go in the middle.
private struct CalorieRing: View {
    let eaten: Double
    let target: Double
    let planned: Double?
    var ghost: Double? = nil

    private let size: CGFloat = 120
    private let width: CGFloat = 12

    private var eatenShare: Double { FoodFormat.share(eaten, of: target) }
    private var toGo: Double { target - eaten }

    var body: some View {
        ZStack {
            Circle().stroke(Color.cardBorder, lineWidth: width)
            if let planned, toGo > 0 {
                let start = eatenShare + 0.03
                let end = min(1, eatenShare + planned / target) - 0.015
                if end > start {
                    Circle()
                        .trim(from: start, to: end)
                        .stroke(Color.volt.opacity(0.8), style: StrokeStyle(lineWidth: 4, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                }
            }
            if let ghost, let range = FoodFormat.ghostRange(eaten: eaten, planned: toGo > 0 ? planned : nil, ghost: ghost, target: target) {
                let arc = Circle().trim(from: range.lowerBound, to: range.upperBound).rotation(.degrees(-90))
                arc.stroke(Color.volt.opacity(0.22), lineWidth: width)
                // Short dashes across a wide stroke read as hatching.
                arc.stroke(Color.volt.opacity(0.7), style: StrokeStyle(lineWidth: width, dash: [2, 3.5]))
            }
            Circle()
                .trim(from: 0, to: eatenShare)
                .stroke(Color.volt, style: StrokeStyle(lineWidth: width, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 3) {
                if toGo > 0 {
                    Text(FoodFormat.kcal(toGo)).font(AppFont.number(32)).foregroundStyle(Color.warning)
                    Text("TO GO").font(AppFont.body(10, weight: .semibold)).tracking(0.8).foregroundStyle(Color.warning)
                } else {
                    Image(systemName: "checkmark").font(.system(size: 24, weight: .bold)).foregroundStyle(Color.volt)
                    Text("ON TARGET").font(AppFont.body(10, weight: .semibold)).tracking(0.8).foregroundStyle(Color.volt)
                }
            }
        }
        .frame(width: size, height: size)
        .padding(width / 2)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(toGo > 0 ? "\(FoodFormat.kcal(toGo)) kcal to go" : "Target reached")
    }
}

/// One macro: value against its target, a thin bar, and what's left (volt tick once met).
/// Without a target it shows the macro's share of the kcal instead.
private struct MacroColumn: View {
    let label: String
    let value: Double
    let target: Double?
    let color: Color
    let share: Double
    var ghost: Double? = nil

    private var met: Bool { target.map { value >= $0 } ?? false }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Kicker(label, color: color)
                if met {
                    Image(systemName: "checkmark").font(.system(size: 10, weight: .heavy)).foregroundStyle(Color.volt)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 0) {
                Text("\(Int(value.rounded()))").font(AppFont.number(26)).foregroundStyle(Color.ink)
                Text(target.map { " / \(Int($0.rounded())) g" } ?? " g")
                    .font(AppFont.body(11)).foregroundStyle(Color.muted)
                    .lineLimit(1)
                    .fixedSize()
            }
            .padding(.top, 6)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.track)
                    let filled = geo.size.width * (target == nil ? share : FoodFormat.share(value, of: target))
                    if let ghost, let target, value < target {
                        Hatch(color: color)
                            .frame(width: geo.size.width * min(ghost, target - value) / target)
                            .clipShape(UnevenRoundedRectangle(bottomTrailingRadius: 3, topTrailingRadius: 3))
                            .offset(x: filled)
                    }
                    Capsule().fill(color).frame(width: filled)
                }
            }
            .frame(height: 5)
            .padding(.top, 8)
            Group {
                if let target {
                    if met {
                        Text("+\(Int((value - target).rounded())) over").foregroundStyle(Color.volt).fontWeight(.semibold)
                    } else {
                        Text("\(Int((target - value).rounded())) g left").foregroundStyle(Color.muted)
                    }
                } else {
                    Text("\(Int((share * 100).rounded()))% of kcal").foregroundStyle(Color.muted)
                }
            }
            .font(AppFont.body(11))
            .padding(.top, 6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Meals

private struct MealTimeline: View {
    let entries: [FoodEntry]
    let pending: [FoodEntryInput]
    let dinner: DinnerWeek.Day?
    let onLogDinner: () -> Void
    let onAteElse: () -> Void
    let onEdit: (FoodEntry) -> Void
    let onDelete: (FoodEntry) -> Void

    private var count: Int { entries.count + pending.count + (dinner?.dish == nil ? 0 : 1) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Meals")
                Spacer()
                Text(summary).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.horizontal, 4)
            .padding(.top, 8)
            .padding(.bottom, 10)
            if count == 0 {
                Text("Nothing logged yet. Scan your next meal.")
                    .font(AppFont.body(14))
                    .foregroundStyle(Color.muted)
                    .frame(maxWidth: .infinity, minHeight: 64, alignment: .leading)
                    .card()
            }
            ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                TimelineRow(time: FoodFormat.clock(entry), last: index == count - 1) {
                    Button { onEdit(entry) } label: {
                        MealCard(
                            title: FoodFormat.mealLabel(entry.meal),
                            subtitle: FoodFormat.itemNames(entry.items) + (entry.source == "photo" ? " · photo" : ""),
                            totals: entry.totals,
                            items: index == entries.count - 1 && pending.isEmpty ? entry.items : []
                        )
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button("Edit", systemImage: "pencil") { onEdit(entry) }
                        Button("Delete", systemImage: "trash", role: .destructive) { onDelete(entry) }
                    }
                }
            }
            ForEach(Array(pending.enumerated()), id: \.offset) { index, entry in
                TimelineRow(time: nil, last: entries.count + index == count - 1) {
                    MealCard(
                        title: FoodFormat.mealLabel(entry.meal),
                        subtitle: FoodFormat.itemNames(entry.items) + " · waiting to sync",
                        totals: entry.items.reduce(.zero, FoodFormat.add),
                        items: []
                    )
                }
            }
            if let dinner, let dish = dinner.dish {
                TimelineRow(time: nil, last: true) {
                    PlannedDinnerCard(dish: dish, kcal: dinner.kcal, onLog: onLogDinner, onAteElse: onAteElse)
                }
            }
        }
    }

    private var summary: String {
        let logged = entries.count + pending.count
        return dinner?.dish == nil ? "\(logged) logged" : "\(logged) logged · 1 planned"
    }
}

/// Time chip on a rail to the left of a meal card.
private struct TimelineRow<Content: View>: View {
    let time: String?
    let last: Bool
    @ViewBuilder let content: Content

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(spacing: 0) {
                Text(time ?? "·")
                    .font(AppFont.body(11, weight: .semibold))
                    .foregroundStyle(time == nil ? Color.faint : Color.inkSoft)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                    .frame(minWidth: 40)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: Radius.chip))
                    .overlay(RoundedRectangle(cornerRadius: Radius.chip).strokeBorder(Color.cardBorder))
                Rectangle().fill(last ? .clear : Color.cardBorder).frame(width: 1).frame(maxHeight: .infinity)
            }
            .frame(width: 44)
            content.padding(.bottom, last ? 0 : 14)
        }
    }
}

private struct MealCard: View {
    let title: String
    let subtitle: String
    let totals: Macros
    /// Shown under the card for the latest meal only.
    let items: [FoodItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(AppFont.body(15, weight: .bold)).foregroundStyle(Color.ink)
                    Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 0) {
                    Text(FoodFormat.kcal(totals.kcal)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                    Text("kcal").font(AppFont.body(10)).foregroundStyle(Color.muted)
                }
            }
            MacroSplit(totals: totals).padding(.top, 10)
            if items.count > 1 {
                VStack(spacing: 0) {
                    ForEach(items) { item in
                        Rectangle().fill(Color.cardBorder).frame(height: 1)
                        HStack {
                            (Text(item.name).foregroundStyle(Color.ink)
                                + Text(item.grams.map { " · \(Int($0)) g" } ?? "").foregroundStyle(Color.muted))
                                .font(AppFont.body(13))
                                .lineLimit(1)
                            Spacer()
                            Text(FoodFormat.kcal(item.kcal)).font(AppFont.number(15)).foregroundStyle(Color.ink)
                        }
                        .padding(.vertical, 9)
                    }
                }
                .padding(.top, 10)
                .padding(.bottom, -6)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
        .contentShape(Rectangle())
    }
}

/// The meal's kcal split as a thin stacked bar, grams under it.
struct MacroSplit: View {
    let totals: Macros

    var body: some View {
        let shares = FoodFormat.kcalShares(totals)
        VStack(alignment: .leading, spacing: 6) {
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
            HStack(spacing: 12) {
                gram(totals.proteinG, "protein", Color.mobility)
                gram(totals.carbsG, "carbs", Color.rideText)
                gram(totals.fatG, "fat", Color(hex: 0xFFA65C))
            }
        }
    }

    private func gram(_ value: Double, _ label: String, _ color: Color) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            Text("\(Int(value.rounded()))").font(AppFont.number(14)).foregroundStyle(color)
            Text("g \(label)").font(AppFont.body(11)).foregroundStyle(Color.muted)
        }
    }
}

private struct PlannedDinnerCard: View {
    let dish: String
    let kcal: Double?
    let onLog: () -> Void
    let onAteElse: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        Text(FoodFormat.mealLabel(FoodFormat.plannedMeal)).font(AppFont.body(15, weight: .bold)).foregroundStyle(Color.inkSoft)
                        Text("PLANNED")
                            .font(AppFont.body(10, weight: .bold)).tracking(0.8)
                            .foregroundStyle(Color.muted)
                            .padding(.horizontal, 6).frame(height: 18)
                            .background(Color.chip, in: RoundedRectangle(cornerRadius: 6))
                    }
                    Text("\(dish) · from dinner plan").font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 0) {
                    Text(kcal.map { "~" + FoodFormat.kcal($0) } ?? "–").font(AppFont.number(20)).foregroundStyle(Color.muted)
                    Text("kcal").font(AppFont.body(10)).foregroundStyle(Color.muted)
                }
            }
            HStack(spacing: 8) {
                Button("Log as planned", action: onLog).buttonStyle(OutlineButtonStyle(height: 36))
                Button("Ate something else", action: onAteElse).buttonStyle(OutlineButtonStyle(height: 36))
            }
            .frame(minHeight: 44)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
            .strokeBorder(Color(hex: 0x2F3542), style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])))
    }
}
