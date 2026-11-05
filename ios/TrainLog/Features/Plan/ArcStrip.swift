import SwiftUI

/// The thin strip under the Plan header: where this week sits in the winter arc (one segment per
/// week, volt = this week, short = lighter) and, while one runs, the stall block's pips.
struct ArcStrip: View {
    let strip: ArcFormat.Strip?
    let stall: ArcFormat.StallLine?
    var onTap: (() -> Void)?

    var body: some View {
        if let onTap {
            Button(action: onTap) { content.contentShape(Rectangle()) }
                .buttonStyle(.plain)
                .accessibilityHint("Shows the winter arc")
        } else {
            content
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let strip {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    (strip.lead.isEmpty ? Text(strip.detail)
                     : Text("\(Text(strip.lead).foregroundStyle(Color.ink).fontWeight(.semibold)) · \(strip.detail)"))
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    if let next = strip.next { Text(next).lineLimit(1) }
                    if onTap != nil {
                        Image(systemName: "chevron.right").font(.system(size: 10, weight: .bold)).foregroundStyle(Color.faint)
                    }
                }
                .font(AppFont.body(13))
                .foregroundStyle(Color.muted)
                ArcTape(tape: strip.tape).padding(.top, 8)
            }
            if let stall {
                HStack(spacing: 8) {
                    StallPips(filled: stall.filled, total: stall.total)
                    Text("\(Text(stall.lift).foregroundStyle(Color.ink).fontWeight(.semibold)) · \(stall.detail)")
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.inkSoft)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                }
                .padding(.top, strip == nil ? 0 : 10)
            }
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 4)
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }
}

/// One segment per week, a gap between blocks; dashed while there's no arc.
struct ArcTape: View {
    let tape: [[ArcFormat.Segment]]
    var height: CGFloat = 8

    var body: some View {
        GeometryReader { geo in
            let blocks = tape.isEmpty ? [Array(repeating: ArcFormat.Segment(lighter: false, state: .future), count: ArcFormat.placeholderWeeks)] : tape
            let widths = ArcFormat.blockWidths(blocks.map(\.count), width: geo.size.width)
            HStack(spacing: ArcFormat.blockGap) {
                ForEach(Array(blocks.enumerated()), id: \.offset) { index, block in
                    HStack(spacing: ArcFormat.segmentGap) {
                        ForEach(Array(block.enumerated()), id: \.offset) { _, segment in
                            if tape.isEmpty {
                                RoundedRectangle(cornerRadius: 2)
                                    .strokeBorder(Color.outline, style: StrokeStyle(lineWidth: 1, dash: [2, 2]))
                                    .frame(height: height)
                            } else {
                                RoundedRectangle(cornerRadius: height > 10 ? 3 : 2)
                                    .fill(color(segment.state))
                                    .frame(height: segment.lighter ? height / 2 : height)
                            }
                        }
                    }
                    .frame(width: widths[index])
                }
            }
            .frame(maxHeight: .infinity)
        }
        .frame(height: height)
        .animation(Motion.layout, value: tape)
        .accessibilityHidden(true)
    }

    private func color(_ state: ArcFormat.Segment.State) -> Color {
        switch state {
        case .past: Color.ride.opacity(0.55)
        case .current: Color.volt
        case .future: Color.raised
        }
    }
}

/// Weeks of the stall block: pink as they pass.
struct StallPips: View {
    let filled: Int
    let total: Int

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<max(total, 0), id: \.self) { index in
                Capsule().fill(index < filled ? Color.strength : Color.raised).frame(width: 12, height: 4)
            }
        }
        .accessibilityHidden(true)
    }
}

/// Behind the strip: the whole arc, one row per block, and the stall block's plan. Read-only;
/// editing stays on the Mac.
struct ArcSheet: View {
    let blocks: [WinterArc.Block]
    let stall: StallBlock?
    let weekStart: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Kicker(ArcFormat.span(blocks) ?? "No arc saved")
                        Text("WINTER ARC").font(AppFont.title(28)).foregroundStyle(Color.ink)
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
                if blocks.isEmpty {
                    Text("No winter arc yet. Set one up on the Mac, on the Plan page: base, build and a VO2 touch, Nov to Feb.")
                        .font(AppFont.body(13))
                        .foregroundStyle(Color.inkSoft)
                        .lineSpacing(2)
                        .padding(.top, 12)
                } else {
                    let tape = ArcFormat.strip(blocks, weekStart: weekStart)?.tape ?? []
                    ArcTape(tape: tape, height: 14).padding(.top, 16)
                    labels.padding(.top, 6)
                    VStack(spacing: 0) {
                        ForEach(Array(ArcFormat.rows(blocks, weekStart: weekStart).enumerated()), id: \.offset) { index, row in
                            blockRow(row, first: index == 0)
                        }
                    }
                    .padding(.top, 12)
                }
                if let stall, stall.scope == "block" {
                    Kicker("Strength block").padding(.top, 20)
                    stallRow(stall)
                }
                Text("Edit the arc on the Mac · Plan")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 20)
            }
            .padding(.horizontal, Space.gutter + 4)
            .padding(.top, 20)
            .padding(.bottom, Space.l)
        }
        .scrollIndicators(.hidden)
    }

    private var labels: some View {
        GeometryReader { geo in
            let widths = ArcFormat.blockWidths(blocks.map(\.weeks), width: geo.size.width)
            HStack(spacing: ArcFormat.blockGap) {
                ForEach(Array(blocks.enumerated()), id: \.offset) { index, block in
                    let current = block.startDate <= weekStart && weekStart <= block.endDate
                    Text(block.name.uppercased())
                        .font(AppFont.body(10, weight: .semibold))
                        .tracking(0.6)
                        .foregroundStyle(current ? Color.ink : Color.faint)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                        .frame(width: widths[index], alignment: .leading)
                }
            }
        }
        .frame(height: 14)
    }

    private func blockRow(_ row: ArcFormat.BlockRow, first: Bool) -> some View {
        VStack(spacing: 0) {
            if !first { Rectangle().fill(Color.cardBorder).frame(height: 1) }
            HStack(alignment: .top, spacing: 12) {
                RoundedRectangle(cornerRadius: 2).fill(row.isCurrent ? Color.ride : Color.raised).frame(width: 4, height: 34).padding(.top, 2)
                VStack(alignment: .leading, spacing: 3) {
                    Text(row.title).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                    Text([row.mix, row.lighter].compactMap { $0 }.joined(separator: "\n"))
                        .font(AppFont.body(12))
                        .foregroundStyle(Color.muted)
                        .lineSpacing(2)
                }
                Spacer(minLength: 8)
                Text(row.range).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.vertical, 12)
            .opacity(row.isCurrent ? 1 : 0.7)
        }
        .accessibilityElement(children: .combine)
    }

    private func stallRow(_ stall: StallBlock) -> some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 2).fill(Color.strength).frame(width: 4, height: 34).padding(.top, 2)
            VStack(alignment: .leading, spacing: 3) {
                Text("\(ActivityDetailFormat.shortLift(stall.exerciseName)) · \(stall.label.lowercased())")
                    .font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                Text([stall.text, ArcFormat.stallDetail(stall)].compactMap { $0 }.joined(separator: "\n"))
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .lineSpacing(2)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 6) {
                StallPips(filled: stall.due ? stall.weeks : stall.week, total: stall.weeks)
                Text(ArcFormat.range(stall.startedOn, stall.endsOn)).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }
}
