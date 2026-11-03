import SwiftUI

/// Seven slots, one per day: bar height is the planned minutes, colour the sport. Dashed while a
/// week isn't planned, breathing while the coach writes it, outlined in volt where it changed.
struct PlanWeekStrip: View {
    enum Style: Equatable {
        case normal, today, past, changed, selected, ghost, selectedGhost
    }

    struct Day: Identifiable, Equatable {
        let date: String
        let color: Color?
        let minutes: Int
        let style: Style

        var id: String { date }
    }

    let days: [Day]
    var showMinutes = true
    /// Grey bars that pulse: the coach is still writing the week.
    var pending = false
    var onTap: ((String) -> Void)?

    private static let slotHeight: CGFloat = 58

    var body: some View {
        HStack(spacing: 6) {
            ForEach(Array(days.enumerated()), id: \.element.id) { index, day in
                if let onTap, day.style != .past {
                    Button { onTap(day.date) } label: { column(day, index: index) }
                        .buttonStyle(.plain)
                } else {
                    column(day, index: index)
                }
            }
        }
    }

    private func column(_ day: Day, index: Int) -> some View {
        let ghost = day.style == .ghost || day.style == .selectedGhost
        let accent = day.style == .today
        return VStack(spacing: 5) {
            Text(weekdayLetter(day.date))
                .font(AppFont.body(10, weight: .semibold))
                .tracking(1)
                .foregroundStyle(accent ? Color.volt : Color.muted)
            Text(dayNumber(day.date))
                .font(AppFont.number(17))
                .foregroundStyle(accent ? Color.volt : Color.ink)
            slot(day, ghost: ghost, index: index)
            Text(showMinutes && !ghost && !pending ? label(day) : " ")
                .font(AppFont.number(12, weight: .semibold))
                .foregroundStyle(Color.inkSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity)
        .background(background(day.style), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(border(day.style), lineWidth: 1))
        .opacity(day.style == .past ? 0.38 : 1)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(ActivityFormat.shortDay(day.date)), \(ghost ? "not planned" : label(day))")
    }

    @ViewBuilder
    private func slot(_ day: Day, ghost: Bool, index: Int) -> some View {
        if ghost {
            RoundedRectangle(cornerRadius: 5, style: .continuous)
                .strokeBorder(Color.outline, style: StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
                .frame(width: 18, height: Self.slotHeight)
        } else if pending {
            PulsingBar(height: [0.5, 0.75, 0.6, 0.9, 0.55, 0.8, 0.45][index % 7] * Self.slotHeight, delay: Double(index) * 0.12)
                .frame(width: 18, height: Self.slotHeight, alignment: .bottom)
                .background(Color(hex: 0x1A1E27), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
        } else {
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 5, style: .continuous).fill(Color(hex: 0x1A1E27))
                if let color = day.color {
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(color)
                        .frame(height: max(10, Self.slotHeight * CGFloat(min(day.minutes, 90)) / 90))
                }
            }
            .frame(width: 18, height: Self.slotHeight)
        }
    }

    private func label(_ day: Day) -> String {
        guard day.color != nil, day.minutes > 0 else { return day.color == nil ? "rest" : "" }
        return day.minutes >= 60 ? "\(day.minutes / 60)h\(String(format: "%02d", day.minutes % 60))" : "\(day.minutes)m"
    }

    private func background(_ style: Style) -> Color {
        switch style {
        case .changed: Color.volt.opacity(0.06)
        case .selected, .selectedGhost: Color.cardBorder
        default: .clear
        }
    }

    private func border(_ style: Style) -> Color {
        switch style {
        case .changed: .volt
        case .selected, .selectedGhost: Color.dim
        default: .clear
        }
    }

    private func weekdayLetter(_ iso: String) -> String {
        String(ActivityFormat.shortDay(iso).prefix(1))
    }

    private func dayNumber(_ iso: String) -> String {
        FoodFormat.parse(iso).map { "\(ActivityFormat.mondayCalendar.component(.day, from: $0))" } ?? ""
    }
}

/// A grey bar that breathes while the coach works (still under Reduce Motion).
private struct PulsingBar: View {
    let height: CGFloat
    let delay: Double
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var up = false

    var body: some View {
        RoundedRectangle(cornerRadius: 5, style: .continuous)
            .fill(Color.raised)
            .frame(height: up && !reduceMotion ? height : height * 0.55)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true).delay(delay)) { up = true }
            }
    }
}
