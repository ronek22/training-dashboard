import Charts
import SwiftUI

/// The last 12 weeks as bars stacked by sport, against a typical week. Tap a week for its split.
struct WeeklyCard: View {
    let volume: WeeklyVolume
    @State private var selection: Int?

    private var selected: WeeklyVolume.Week? {
        selection.flatMap { index in volume.weeks.first { $0.index == index } }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Kicker("Weekly hours · \(volume.weeks.count) weeks")
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        BigHours(value: volume.lastWeek?.total ?? 0)
                        Text("last week").font(AppFont.body(13)).foregroundStyle(Color.muted)
                    }
                }
                Spacer(minLength: 8)
                if let note = typicalNote {
                    Pill(text: note, color: .muted)
                }
            }
            chart.frame(height: 160)
            legend
            Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 2)
            if let selected {
                breakdown(selected)
            } else {
                summary
            }
        }
        .card()
        .sensoryFeedback(.selection, trigger: selection)
    }

    private var typicalNote: String? {
        guard let last = volume.lastWeek, volume.typical > 0 else { return nil }
        let diff = last.total - volume.typical
        if abs(diff) < 0.4 { return "On your usual" }
        return "\(diff < 0 ? "−" : "+")\(TrendsFormat.hours(abs(diff))) vs typical"
    }

    // MARK: Chart

    private struct Segment: Identifiable {
        let group: VolumeGroup
        let hours: Double
        let isTop: Bool
        var id: VolumeGroup { group }
    }

    /// The week's sports bottom to top, cut at the cap so one huge week doesn't flatten the rest.
    private func segments(_ week: WeeklyVolume.Week) -> [Segment] {
        var room = volume.cap
        let parts: [(VolumeGroup, Double)] = VolumeGroup.allCases.compactMap { group in
            let hours = min(week.hours[group] ?? 0, room)
            room -= hours
            return hours > 0.01 ? (group, hours) : nil
        }
        return parts.enumerated().map { index, part in Segment(group: part.0, hours: part.1, isTop: index == parts.count - 1) }
    }

    private func opacity(_ week: WeeklyVolume.Week) -> Double {
        if let selection { return selection == week.index ? 1 : 0.28 }
        return week.index >= volume.weeks.count - 2 ? 1 : 0.8
    }

    private var labelled: Set<String> {
        let keys = volume.weeks.map(\.key)
        return Set(keys.enumerated().filter { $0.offset % 3 == 2 || $0.offset == keys.count - 1 }.map(\.element))
    }

    private var chart: some View {
        Chart {
            if volume.typical > 0 {
                RuleMark(y: .value("Typical", volume.typical))
                    .foregroundStyle(Color.inkSoft.opacity(0.55))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
                    // Over the dashed slot at the right, where the week in progress is still short.
                    .annotation(position: .top, alignment: .trailing, spacing: 2) {
                        Text("typical \(TrendsFormat.hours(volume.typical))")
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(Color.inkSoft)
                            .padding(.horizontal, 4)
                            .background(Color.card, in: RoundedRectangle(cornerRadius: 3))
                    }
            }
            ForEach(volume.weeks) { week in
                ForEach(segments(week)) { segment in
                    BarMark(x: .value("Week", week.key), y: .value("Hours", segment.hours), width: .ratio(0.72))
                        .foregroundStyle(segment.group.color.opacity(opacity(week)))
                        .annotation(position: .top, spacing: 3) {
                            if segment.isTop { topLabel(week) }
                        }
                        .annotation(position: .overlay, alignment: .top) {
                            // A slanted cut across a week taller than the scale.
                            if segment.isTop && week.total > volume.cap {
                                Rectangle().fill(Color.card).frame(width: 44, height: 3).rotationEffect(.degrees(-14)).offset(y: 7)
                            }
                        }
                }
            }
        }
        .chartXScale(domain: volume.weeks.map(\.key))
        .chartYScale(domain: 0...volume.cap * 1.12)
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: volume.weeks.map(\.key)) { value in
                AxisValueLabel {
                    if let key = value.as(String.self), labelled.contains(key) {
                        let now = key == volume.thisWeek?.key
                        Text(now ? "now" : FoodFormat.parse(key)?.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB"))) ?? "")
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(now ? Color.volt : Color.muted)
                            .fixedSize()
                    }
                }
            }
        }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                let plot = proxy.plotFrame.map { geometry[$0] } ?? .zero
                ZStack(alignment: .topLeading) {
                    // This week, until something is logged: a dashed slot.
                    if let current = volume.thisWeek, current.total == 0, let x = proxy.position(forX: current.key) {
                        let width = plot.width / CGFloat(max(volume.weeks.count, 1)) * 0.72
                        RoundedRectangle(cornerRadius: 3)
                            .strokeBorder(Color.volt.opacity(0.7), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                            .frame(width: width, height: 12)
                            .position(x: plot.minX + x, y: plot.maxY - 6)
                    }
                    Rectangle().fill(.clear).contentShape(Rectangle())
                        .onTapGesture { location in
                            guard let key: String = proxy.value(atX: location.x - plot.minX),
                                  let week = volume.weeks.first(where: { $0.key == key }) else { return }
                            selection = selection == week.index ? nil : week.index
                        }
                }
            }
        }
    }

    /// Only a week taller than the scale gets its total; last week's is in the header.
    @ViewBuilder
    private func topLabel(_ week: WeeklyVolume.Week) -> some View {
        if week.total > volume.cap {
            Text("\(Int(week.total.rounded()))h").font(AppFont.number(11, weight: .semibold)).foregroundStyle(Color.inkSoft)
        }
    }

    // MARK: Legend and footer

    private var shownGroups: [VolumeGroup] {
        VolumeGroup.allCases.filter { group in volume.weeks.contains { ($0.hours[group] ?? 0) > 0 } }
    }

    private var legend: some View {
        let groups = shownGroups
        return HStack(spacing: 12) {
            ForEach(groups, id: \.self) { group in
                HStack(spacing: 5) {
                    Circle().fill(group.color).frame(width: 6, height: 6)
                    Text(groups.count > 4 ? group.short : group.label)
                }
            }
        }
        .font(AppFont.body(11))
        .foregroundStyle(Color.inkSoft)
        .lineLimit(1)
    }

    /// Last week against a typical week for the three sports with the most time.
    private var summary: some View {
        let groups = shownGroups
            .sorted { (volume.lastWeek?.hours[$0] ?? 0) + volume.typicalByGroup[$0, default: 0] > (volume.lastWeek?.hours[$1] ?? 0) + volume.typicalByGroup[$1, default: 0] }
            .prefix(3)
        return HStack(alignment: .top, spacing: 0) {
            ForEach(Array(groups), id: \.self) { group in
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 5) {
                        Circle().fill(group.color).frame(width: 6, height: 6)
                        Text(group.short).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                    Text(TrendsFormat.hours(volume.lastWeek?.hours[group] ?? 0)).font(AppFont.number(20)).foregroundStyle(Color.ink)
                    Text("typical \(TrendsFormat.hours(volume.typicalByGroup[group] ?? 0))").font(AppFont.body(11)).foregroundStyle(Color.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private func breakdown(_ week: WeeklyVolume.Week) -> some View {
        VStack(spacing: 0) {
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 3) {
                    Kicker(TrendsFormat.weekRange(week.start), color: .ink)
                    Text(TrendsFormat.weekNote(week)).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer()
                Text(TrendsFormat.hours(week.total)).font(AppFont.number(24)).foregroundStyle(Color.ink)
            }
            .padding(.bottom, 4)
            ForEach(VolumeGroup.allCases.filter { (week.hours[$0] ?? 0) > 0.05 }, id: \.self) { group in
                HStack {
                    Circle().fill(group.color).frame(width: 6, height: 6)
                    Text(group.label).font(AppFont.body(13)).foregroundStyle(Color.ink)
                    Spacer()
                    Text(TrendsFormat.hours(week.hours[group] ?? 0)).font(AppFont.number(17)).foregroundStyle(Color.ink)
                }
                .padding(.vertical, 8)
            }
        }
    }
}

/// "6h 32" with a small h, or "45 min".
private struct BigHours: View {
    let value: Double

    var body: some View {
        let minutes = Int((value * 60).rounded())
        HStack(alignment: .firstTextBaseline, spacing: 2) {
            if minutes >= 60 {
                Text("\(minutes / 60)").font(AppFont.number(44)).foregroundStyle(Color.ink)
                Text("h").font(AppFont.number(22)).foregroundStyle(Color.muted)
                Text(String(format: "%02d", minutes % 60)).font(AppFont.number(44)).foregroundStyle(Color.ink).padding(.leading, 6)
            } else {
                Text("\(minutes)").font(AppFont.number(44)).foregroundStyle(Color.ink)
                Text("min").font(AppFont.number(22)).foregroundStyle(Color.muted)
            }
        }
    }
}
