import SwiftUI

/// A logged meal, opened from its card: the same layout as the scan result. Change the portion,
/// fine-tune grams, move it to another meal, or delete it.
struct MealEditSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var meal: String
    @State private var items: [FoodItem]
    @State private var portion = 1.0
    let entry: FoodEntry
    let context: MealDayContext
    let onSave: (FoodEntryInput) -> Void
    let onDelete: () -> Void

    init(entry: FoodEntry, context: MealDayContext, onSave: @escaping (FoodEntryInput) -> Void, onDelete: @escaping () -> Void) {
        self.entry = entry
        self.context = context
        self.onSave = onSave
        self.onDelete = onDelete
        _meal = State(initialValue: entry.meal)
        _items = State(initialValue: entry.items)
    }

    private var totals: Macros { items.reduce(.zero, FoodFormat.add) }

    private var input: FoodEntryInput {
        FoodEntryInput(date: entry.date, meal: meal, source: entry.source, rawText: entry.rawText,
                       items: items.filter { !$0.name.trimmingCharacters(in: .whitespaces).isEmpty })
    }

    /// The entry's own items, so a changed one can go back to what was logged.
    private var originals: [UUID: FoodItem] {
        Dictionary(uniqueKeysWithValues: entry.items.map { ($0.id, $0) })
    }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    VStack(alignment: .leading, spacing: 0) {
                        HStack(spacing: 6) {
                            MealChip(meal: $meal)
                            if let clock = FoodFormat.clock(entry) {
                                Text(clock).modifier(ChipStyle())
                            }
                            if entry.source == "photo" {
                                Label("From photo", systemImage: "camera").modifier(ChipStyle(color: .muted))
                            }
                        }
                        Text(FoodFormat.itemNames(items, limit: 2).uppercased())
                            .font(AppFont.title(34))
                            .foregroundStyle(Color.ink)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 4)
                    }
                    MealSummaryCard(totals: totals, target: context.target)
                    PortionPicker(factor: $portion, grams: items.compactMap(\.grams).reduce(0, +))
                    Breakdown(items: $items, originals: originals)
                    Button(role: .destructive) {
                        onDelete()
                        dismiss()
                    } label: {
                        Label("Delete meal", systemImage: "trash")
                            .font(AppFont.body(14, weight: .semibold))
                            .foregroundStyle(Color.danger)
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
            .scrollIndicators(.hidden)
            .scrollDismissesKeyboard(.interactively)
            Button {
                onSave(input)
                dismiss()
            } label: {
                Text("Save \(FoodFormat.kcal(totals.kcal)) kcal")
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(input.items.isEmpty)
            .opacity(input.items.isEmpty ? 0.4 : 1)
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 8)
            .overlay(alignment: .top) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
        }
        .padding(.top, 8)
        .background(Color.bg)
        .onChange(of: portion) { old, new in
            items = FoodFormat.portioned(items, by: new / old)
        }
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
            Text("Meal").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 52, height: 44)
        }
        .padding(.horizontal, 16)
    }
}
