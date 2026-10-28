import SwiftUI

/// A logged meal, opened from its row: correct portions, grams or macros, move it to another
/// meal, or delete it.
struct MealEditSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var meal: String
    @State private var items: [FoodItem]
    let entry: FoodEntry
    let onSave: (FoodEntryInput) -> Void
    let onDelete: () -> Void

    init(entry: FoodEntry, onSave: @escaping (FoodEntryInput) -> Void, onDelete: @escaping () -> Void) {
        self.entry = entry
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

    var body: some View {
        VStack(spacing: 0) {
            topBar
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    MealPicker(selection: $meal)
                    VStack(alignment: .leading, spacing: 0) {
                        HStack {
                            Kicker("Items")
                            Spacer()
                            Text("\(FoodFormat.kcal(totals.kcal)) kcal · \(Int(totals.proteinG.rounded())) g P")
                                .font(AppFont.body(12, weight: .semibold))
                                .foregroundStyle(Color.inkSoft)
                        }
                        .padding(.bottom, 4)
                        ForEach($items) { $item in
                            Rectangle().fill(Color.cardBorder).frame(height: 1)
                            ItemEditor(item: $item) { items.removeAll { $0.id == item.id } }
                        }
                    }
                    .card()
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
            .scrollDismissesKeyboard(.interactively)
            Button {
                onSave(input)
                dismiss()
            } label: {
                Label("Save \(FoodFormat.kcal(totals.kcal)) kcal", systemImage: "checkmark")
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(input.items.isEmpty)
            .opacity(input.items.isEmpty ? 0.4 : 1)
            .padding(.horizontal, 16)
            .padding(.bottom, 8)
        }
        .padding(.top, 8)
    }

    private var topBar: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minWidth: 52, minHeight: 44, alignment: .leading)
            Spacer()
            Text("Edit meal").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 52, height: 44)
        }
        .padding(.horizontal, 16)
    }
}
