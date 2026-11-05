import SwiftUI

/// The week card as the week's contract: the brief's first rules on coloured rails, with the lift
/// slots and the block's rides as pills and ticks that fill as the week is trained. Tap → the brief.
struct WeekContractCard: View {
    let week: WeeklyPlan
    let brief: WeekBrief
    let today: String
    let onOpen: () -> Void

    var body: some View {
        let summary = PlanFormat.summary(week, today: today)
        Button(action: onOpen) {
            VStack(alignment: .leading, spacing: 0) {
                if let title = PlanFormat.shortTitle(week.title) {
                    Text(title.uppercased()).font(AppFont.title(22)).foregroundStyle(Color.ink).lineLimit(1)
                }
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(WeekBriefFormat.rules(brief, week: week, today: today).enumerated()), id: \.offset) { _, rule in
                        RuleRail(rule: rule)
                    }
                }
                .padding(.top, 12)
                HStack(alignment: .firstTextBaseline) {
                    let more = WeekBriefFormat.moreCount(brief)
                    HStack(spacing: 4) {
                        Text(more > 0 ? "\(more) more rule\(more == 1 ? "" : "s")" : "Week brief")
                        Image(systemName: "chevron.right").font(.system(size: 9, weight: .bold)).foregroundStyle(Color.faint)
                    }
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.muted)
                    Spacer()
                    let done = Text(TodayFormat.duration(summary.doneMinutes)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                    let planned = Text(" of \(TodayFormat.duration(summary.plannedMinutes))").font(AppFont.body(12)).foregroundStyle(Color.muted)
                    Text("\(done)\(planned)")
                }
                .padding(.top, 12)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
            .contentShape(RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityHint("Opens the week brief")
    }
}

extension WeekBriefFormat.Kind {
    var color: Color {
        switch self {
        case .safety: .danger
        case .anchor: .strengthText
        case .block: .rideText
        case .outcome, .habit: .inkSoft
        }
    }
}

/// One rule: a 3 pt rail in its colour, the kicker, then text, slot pills or ride ticks.
private struct RuleRail: View {
    let rule: WeekBriefFormat.Rule

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            RoundedRectangle(cornerRadius: 2).fill(rule.kind.color).frame(width: 3)
            VStack(alignment: .leading, spacing: 4) {
                Text(rule.kicker.uppercased())
                    .font(AppFont.body(10, weight: .bold))
                    .tracking(10 * 0.14)
                    .foregroundStyle(rule.kind.color)
                    .lineLimit(1)
                if !rule.slots.isEmpty {
                    HStack(spacing: 6) {
                        ForEach(Array(rule.slots.enumerated()), id: \.offset) { _, slot in SlotPillView(slot: slot) }
                    }
                    .padding(.top, 2)
                } else if !rule.rides.isEmpty {
                    HStack(spacing: 8) {
                        RideTicks(rides: rule.rides).frame(height: 8)
                        Text(rule.text).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1).fixedSize()
                    }
                    .padding(.top, 2)
                } else {
                    Group {
                        if let lead = rule.lead {
                            Text("\(Text(lead).foregroundStyle(Color.ink).fontWeight(.semibold)) · \(rule.text)")
                        } else {
                            Text(rule.text)
                        }
                    }
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.inkBody)
                    .lineSpacing(1)
                    .lineLimit(2)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .fixedSize(horizontal: false, vertical: true)
        .accessibilityElement(children: .combine)
    }
}

/// "A Upper Press": filled pink once that workout is done; dashed while it stands in for a leg day.
private struct SlotPillView: View {
    let slot: WeekBriefFormat.SlotPill

    var body: some View {
        HStack(spacing: 6) {
            Text(slot.code).font(AppFont.number(15)).foregroundStyle(slot.done ? Color.bg : Color.strengthText)
            Text(slot.name)
                .font(AppFont.body(12, weight: .medium))
                .foregroundStyle(slot.done ? Color.bg : Color.inkSoft)
                .lineLimit(1)
        }
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity, minHeight: 30, alignment: .leading)
        .background(slot.done ? Color.strength : .clear, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .strokeBorder(Color.strength.opacity(slot.done ? 1 : 0.55),
                              style: StrokeStyle(lineWidth: 1.5, dash: slot.swapped && !slot.done ? [4, 3] : []))
        }
        .accessibilityLabel("\(slot.code), \(slot.name)\(slot.done ? ", done" : "")")
    }
}

/// One tick per planned ride, as wide as its share of the week's riding, filled when ridden.
private struct RideTicks: View {
    let rides: [WeekBriefFormat.RideTick]

    var body: some View {
        GeometryReader { geo in
            let gap: CGFloat = 4
            let total = CGFloat(max(rides.reduce(0) { $0 + $1.minutes }, 1))
            let width = max(geo.size.width - gap * CGFloat(rides.count - 1), 0)
            HStack(spacing: gap) {
                ForEach(Array(rides.enumerated()), id: \.offset) { _, ride in
                    let color = Self.color(ride.kind)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(ride.done ? color : Color.track)
                        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(color.opacity(ride.done ? 1 : 0.6), lineWidth: 1.5))
                        .frame(width: width * CGFloat(ride.minutes) / total)
                }
            }
        }
    }

    static func color(_ kind: String) -> Color {
        switch kind {
        case "sweet_spot": .amber
        case "vo2": .alert
        default: .ride
        }
    }
}

/// The whole brief: every rule in order with its source, then the coach's note.
struct WeekBriefSheet: View {
    let brief: WeekBrief
    let week: WeeklyPlan?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Kicker("Week brief · \(PlanFormat.weekKicker(brief.weekStart).components(separatedBy: " · ").last ?? "")")
                        Text(WeekBriefFormat.sheetTitle(brief).uppercased()).font(AppFont.title(28)).foregroundStyle(Color.ink)
                    }
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.system(size: 12, weight: .bold)).foregroundStyle(Color.inkSoft)
                            .frame(width: 32, height: 32)
                            .background(Color.raised, in: Circle())
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Close")
                }
                Text("Higher rules win. The coach plans to this list, and saving a week holds rides to the block and lifts to the slots.")
                    .font(AppFont.body(13))
                    .foregroundStyle(Color.muted)
                    .lineSpacing(2)
                    .padding(.top, 6)
                VStack(spacing: 0) {
                    ForEach(Array(brief.lines.enumerated()), id: \.offset) { index, line in
                        ruleRow(line, first: index == 0)
                    }
                }
                .padding(.top, 10)
                if let note = week?.focus, !note.isEmpty {
                    Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 8)
                    Kicker("Coach's note").padding(.top, 12)
                    Text(note).font(AppFont.body(13)).foregroundStyle(Color.inkBody).lineSpacing(2).padding(.top, 6)
                }
            }
            .padding(.horizontal, Space.gutter + 4)
            .padding(.top, 20)
            .padding(.bottom, Space.l)
        }
        .scrollIndicators(.hidden)
    }

    private func ruleRow(_ line: WeekBrief.Line, first: Bool) -> some View {
        let kind = WeekBriefFormat.Kind(rawValue: line.priority) ?? .habit
        let quiet = kind == .outcome || kind == .habit
        return HStack(alignment: .top, spacing: 12) {
            Text(line.priorityLabel.uppercased())
                .font(AppFont.body(10, weight: .bold))
                .tracking(10 * 0.12)
                .foregroundStyle(kind.color)
                .frame(width: 62, alignment: .leading)
                .padding(.top, 3)
            VStack(alignment: .leading, spacing: 3) {
                Text(line.text).font(AppFont.body(14)).foregroundStyle(quiet ? Color.inkBody : Color.ink).lineSpacing(2)
                Text(line.source).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 12)
        .overlay(alignment: .top) {
            if !first { Rectangle().fill(Color.cardBorder).frame(height: 1) }
        }
        .accessibilityElement(children: .combine)
    }
}
