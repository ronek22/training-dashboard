import SwiftUI

/// Pick another day of the same week; the two days swap (or the session moves onto a free day).
/// Past and done days are greyed out; a dot shows what's already on each day.
struct MoveDaySheet: View {
    let source: PlanDay
    let slots: [PlanSlot]
    let today: String
    /// Sends the move; returns an error to show, or nil when it worked.
    let onMove: (String) async -> String?
    @Environment(\.dismiss) private var dismiss
    @State private var target: String?
    @State private var sending = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button("Cancel") { dismiss() }
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .frame(minHeight: 44)
                Spacer()
                Text("Move session").font(AppFont.body(16, weight: .bold)).foregroundStyle(Color.ink)
                Spacer()
                Color.clear.frame(width: 50, height: 1)
            }

            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: 2).fill(PlanFormat.sport(source).color).frame(width: 4, height: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(PlanFormat.rowTitle(source.title)).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                        .lineLimit(1)
                    Text([ActivityFormat.shortDay(source.date), source.targetDurationMin.map { "\($0) min" }].compactMap { $0 }.joined(separator: " · "))
                        .font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
            .padding(.top, 14)

            Kicker("Move to").padding(.top, 20)
            HStack(spacing: 6) {
                ForEach(slots) { slot in
                    dayButton(slot)
                }
            }
            .padding(.top, 10)

            Group {
                if let error {
                    Text(error).foregroundStyle(Color.danger)
                } else if let slot = selectedSlot {
                    Text(PlanFormat.moveDescription(source, to: slot).sentence).foregroundStyle(Color.inkSoft)
                } else {
                    Text("Pick a day this week.").foregroundStyle(Color.muted)
                }
            }
            .font(AppFont.body(14))
            .lineSpacing(2)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.top, 18)

            Spacer(minLength: 16)

            Button {
                guard let target else { return }
                Task {
                    sending = true
                    error = await onMove(target)
                    sending = false
                    if error == nil { dismiss() }
                }
            } label: {
                if sending {
                    ProgressView().tint(Color.bg)
                } else {
                    Text(selectedSlot.map { PlanFormat.moveDescription(source, to: $0).button } ?? "Move")
                }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(target == nil || sending)
            .opacity(target == nil ? 0.4 : 1)
            .padding(.bottom, 8)
        }
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .presentationDragIndicator(.visible)
    }

    private var selectedSlot: PlanSlot? { slots.first { $0.date == target } }

    private func dayButton(_ slot: PlanSlot) -> some View {
        let isSource = slot.date == source.date
        let enabled = !isSource && PlanFormat.canReceive(slot, today: today)
        let selected = slot.date == target
        let date = FoodFormat.parse(slot.date)
        let letter = date?.formatted(.dateTime.weekday(.narrow).locale(Locale(identifier: "en_GB"))) ?? ""
        let number = date.map { "\(ActivityFormat.mondayCalendar.component(.day, from: $0))" } ?? ""
        let dot = slot.day.map(PlanFormat.sport).flatMap { $0 == .rest ? nil : $0.color }
        return Button {
            target = slot.date
            error = nil
            UISelectionFeedbackGenerator().selectionChanged()
        } label: {
            VStack(spacing: 6) {
                Text(letter)
                    .font(AppFont.body(11, weight: selected ? .bold : .semibold))
                    .foregroundStyle(selected ? Color.volt : Color.muted)
                VStack(spacing: 5) {
                    Text(number).font(AppFont.number(20))
                    Circle().fill(dot ?? .clear).frame(width: 6, height: 6)
                }
                .foregroundStyle(selected ? Color.volt : isSource ? Color.muted : Color.ink)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(isSource ? Color.raised : .clear, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(selected ? Color.volt : isSource ? .clear : enabled ? Color.outline : Color.cardBorder,
                                      lineWidth: selected ? 2 : 1)
                )
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled || isSource ? 1 : 0.3)
        .accessibilityLabel(ActivityFormat.shortDay(slot.date))
    }
}
