import SwiftUI

struct FoodView: View {
    @State private var model = FoodModel()
    @State private var showCamera = false
    @State private var draft: MealDraft?
    @State private var editing: FoodEntry?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if model.offline, let syncedAt = model.syncedAt {
                    offlineNote(syncedAt)
                }
                if let day = model.day {
                    EatenCard(day: day, eaten: model.eaten, dinner: model.plannedDinner, isToday: model.isToday)
                    MealsCard(
                        entries: day.entries,
                        pending: model.pending.filter { $0.date == model.selectedDate },
                        dinner: model.plannedDinner,
                        onLogDinner: { Task { await model.logPlannedDinner() } },
                        onEdit: { editing = $0 },
                        onDelete: { entry in Task { await model.delete(entry) } }
                    )
                } else if let error = model.error {
                    errorCard(error)
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 88)
        }
        .scrollIndicators(.hidden)
        .safeAreaInset(edge: .top, spacing: 0) {
            Color.clear.frame(height: 0).background(Color.bg)
        }
        .background(Color.bg)
        .overlay(alignment: .bottomTrailing) { snapButton }
        .refreshable {
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
            MealEstimateSheet(draft: draft, date: model.selectedDate) { entry in
                Task { await model.save(entry) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.card)
        }
        .sheet(item: $editing) { entry in
            MealEditSheet(entry: entry) { input in
                Task { await model.update(entry, with: input) }
            } onDelete: {
                Task { await model.delete(entry) }
            }
            .presentationDetents([.large])
            .presentationBackground(Color.card)
        }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(FoodFormat.dayKicker(model.selectedDate, kind: model.day?.target?.dayKind))
                Text("FOOD").font(AppFont.title(44)).foregroundStyle(Color.ink)
            }
            Spacer()
            HStack(spacing: 8) {
                dayButton(-1, "‹ " + FoodFormat.shortWeekday(neighbour(-1)))
                if !model.isToday {
                    dayButton(1, FoodFormat.shortWeekday(neighbour(1)) + " ›")
                }
            }
            .padding(.bottom, 4)
        }
        .padding(.horizontal, 4)
        .padding(.top, 6)
    }

    private func neighbour(_ days: Int) -> String {
        FoodFormat.parse(model.selectedDate)
            .flatMap { Calendar(identifier: .gregorian).date(byAdding: .day, value: days, to: $0) }
            .map(FoodFormat.iso) ?? model.selectedDate
    }

    private func dayButton(_ days: Int, _ title: String) -> some View {
        Button { Task { await model.shiftDay(days) } } label: {
            Text(title).padding(.horizontal, 12)
        }
            .buttonStyle(OutlineButtonStyle(height: 34))
            .fixedSize()
            .frame(minHeight: 44)
    }

    /// The one volt action: camera straight away. The outline button describes a meal in words
    /// (or picks a library photo) instead.
    private var snapButton: some View {
        HStack(spacing: 10) {
            Button {
                draft = MealDraft(photo: nil)
            } label: {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 52, height: 52)
                    .background(Color.card, in: Circle())
                    .overlay(Circle().strokeBorder(Color.outline))
            }
            .accessibilityLabel("Describe a meal")
            Button {
                showCamera = true
            } label: {
                Label("Snap meal", systemImage: "camera")
                    .font(AppFont.body(16, weight: .bold))
                    .foregroundStyle(Color.bg)
                    .padding(.leading, 16)
                    .padding(.trailing, 20)
                    .frame(height: 52)
                    .background(Color.volt, in: Capsule())
            }
        }
        .shadow(color: .black.opacity(0.45), radius: 12, y: 6)
        .padding(.trailing, 16)
        .padding(.bottom, 16)
    }

    private func offlineNote(_ syncedAt: Date) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "wifi.slash").font(.system(size: 11, weight: .semibold))
            Text("Offline · last synced \(syncedAt.formatted(date: .omitted, time: .shortened))")
                .font(AppFont.body(12, weight: .medium))
        }
        .foregroundStyle(Color.muted)
        .padding(.horizontal, 4)
    }

    private func errorCard(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Not synced yet")
            Text(message).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
            Text("Start the backend on the Mac (docker compose up) and pull to refresh.")
                .font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .card()
    }
}

/// A meal being estimated: a camera photo, or nil to describe it in words.
struct MealDraft: Identifiable {
    let id = UUID()
    let photo: UIImage?
}

// MARK: - Eaten

private struct EatenCard: View {
    let day: FoodDay
    let eaten: Macros
    let dinner: DinnerWeek.Day?
    let isToday: Bool

    private var target: Double? { day.target?.kcal }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker(isToday ? "Eaten today" : "Eaten")
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(FoodFormat.kcal(eaten.kcal)).font(AppFont.number(52)).foregroundStyle(Color.ink)
                if let target {
                    Text("of \(FoodFormat.kcal(target)) kcal").font(AppFont.body(14)).foregroundStyle(Color.muted)
                } else {
                    Text("kcal").font(AppFont.body(14)).foregroundStyle(Color.muted)
                }
            }
            .padding(.top, 8)
            Bar(share: FoodFormat.share(eaten.kcal, of: target), color: .volt.opacity(0.85), height: 10)
                .padding(.top, 10)
            if let target {
                gapLine(target).padding(.top, 10)
            }
            HStack(spacing: 8) {
                MacroTile(label: "Protein", value: eaten.proteinG, target: day.proteinTargetG, color: .mobility)
                MacroTile(label: "Carbs", value: eaten.carbsG, target: day.target?.carbsG, color: .ride)
                MacroTile(label: "Fat", value: eaten.fatG, target: nil, color: .run)
            }
            .padding(.top, 16)
        }
        .card()
    }

    @ViewBuilder
    private func gapLine(_ target: Double) -> some View {
        let toGo = target - eaten.kcal
        HStack(spacing: 6) {
            if toGo > 0 {
                Image(systemName: "exclamationmark.circle").font(.system(size: 13, weight: .semibold)).foregroundStyle(Color(hex: 0xFFB547))
                Text("\(FoodFormat.kcal(toGo)) kcal to go").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color(hex: 0xFFC873))
                if let kcal = dinner?.kcal {
                    Text("· dinner covers ~\(FoodFormat.kcal(kcal))").font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            } else {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 13)).foregroundStyle(Color.volt)
                Text("Target reached").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.volt)
            }
        }
    }
}

private struct MacroTile: View {
    let label: String
    let value: Double
    let target: Double?
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(label.uppercased())
                .font(AppFont.body(9, weight: .semibold))
                .tracking(9 * 0.14)
                .foregroundStyle(Color.muted)
            HStack(alignment: .firstTextBaseline, spacing: 0) {
                Text("\(Int(value.rounded()))").font(AppFont.number(24)).foregroundStyle(Color.ink)
                Text(target.map { " /\(Int($0.rounded())) g" } ?? " g")
                    .font(AppFont.body(12, weight: .medium))
                    .foregroundStyle(Color.muted)
            }
            .padding(.top, 6)
            Bar(share: target == nil ? 0 : FoodFormat.share(value, of: target), color: color, height: 4)
                .padding(.top, 8)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
    }
}

private struct Bar: View {
    let share: Double
    let color: Color
    var height: CGFloat = 6

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.track)
                Capsule().fill(color).frame(width: geo.size.width * share)
            }
        }
        .frame(height: height)
    }
}

// MARK: - Meals

private struct MealsCard: View {
    let entries: [FoodEntry]
    let pending: [FoodEntryInput]
    let dinner: DinnerWeek.Day?
    let onLogDinner: () -> Void
    let onEdit: (FoodEntry) -> Void
    let onDelete: (FoodEntry) -> Void

    var body: some View {
        VStack(spacing: 0) {
            if entries.isEmpty && pending.isEmpty && dinner == nil {
                Text("Nothing logged yet. Snap your next meal.")
                    .font(AppFont.body(14))
                    .foregroundStyle(Color.muted)
                    .frame(maxWidth: .infinity, minHeight: 64, alignment: .leading)
            }
            ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                row
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private var rows: [AnyView] {
        var rows = entries.map { entry in
            AnyView(
                Button { onEdit(entry) } label: {
                    MealRow(
                        icon: FoodFormat.emoji(entry.meal),
                        title: FoodFormat.entryTitle(entry),
                        meta: FoodFormat.entryMeta(entry),
                        kcal: FoodFormat.kcal(entry.totals.kcal),
                        protein: entry.totals.proteinG
                    )
                }
                .buttonStyle(.plain)
                .contextMenu {
                    Button("Edit", systemImage: "pencil") { onEdit(entry) }
                    Button("Delete", systemImage: "trash", role: .destructive) { onDelete(entry) }
                }
            )
        }
        rows += pending.map { entry in
            let totals = entry.items.reduce(Macros.zero, FoodFormat.add)
            return AnyView(MealRow(
                icon: FoodFormat.emoji(entry.meal),
                title: entry.items.first?.name ?? "Meal",
                meta: FoodFormat.mealLabel(entry.meal) + " · waiting to sync",
                kcal: FoodFormat.kcal(totals.kcal),
                protein: totals.proteinG
            ))
        }
        if let dinner, let dish = dinner.dish {
            rows.append(AnyView(
                Button(action: onLogDinner) {
                    MealRow(
                        icon: "🍽️",
                        title: dish,
                        meta: "Dinner · planned · tap to log",
                        kcal: dinner.kcal.map { "~" + FoodFormat.kcal($0) } ?? "–",
                        protein: dinner.proteinG,
                        planned: true
                    )
                }
                .buttonStyle(.plain)
            ))
        }
        return rows
    }
}

private struct MealRow: View {
    let icon: String
    let title: String
    let meta: String
    let kcal: String
    let protein: Double?
    var planned = false

    var body: some View {
        HStack(spacing: 12) {
            Text(icon)
                .font(.system(size: 20))
                .frame(width: 44, height: 44)
                .background(planned ? Color.clear : Color(hex: 0x1B1F29), in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    if planned {
                        RoundedRectangle(cornerRadius: 12).strokeBorder(Color.dim, style: StrokeStyle(lineWidth: 1.5, dash: [4, 3]))
                    }
                }
                .opacity(planned ? 0.7 : 1)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(AppFont.body(14, weight: .semibold)).foregroundStyle(planned ? Color.inkSoft : Color.ink).lineLimit(1)
                Text(meta).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 0) {
                Text(kcal).font(AppFont.number(18)).foregroundStyle(planned ? Color.muted : Color.ink)
                if let protein {
                    Text("\(Int(protein.rounded())) g P").font(AppFont.body(11)).foregroundStyle(Color.muted)
                }
            }
        }
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }
}
