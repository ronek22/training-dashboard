import SwiftUI

// The page's sections, top to bottom (docs/design/artboards/iOSActivityDetailV3.dc.html, D2).
// Sections sit on the background: hairline, 32 pt rhythm, Barlow 22 titles.

// MARK: Pain, grid, log prompt

struct PainBlock: View {
    let pain: Int
    let note: String?

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("!")
                .font(AppFont.body(15, weight: .heavy))
                .foregroundStyle(ActivityDetailFormat.bad)
                .frame(width: 28, height: 28)
                .background(ActivityDetailFormat.bad.opacity(0.18), in: Circle())
            VStack(alignment: .leading, spacing: 10) {
                Text("Pain \(pain)/10: check it before the next hard session")
                    .font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let note {
                    Text(note).font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(2)
                        .padding(.leading, 12)
                        .overlay(alignment: .leading) { Rectangle().fill(ActivityDetailFormat.bad.opacity(0.4)).frame(width: 2) }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .background(ActivityDetailFormat.bad.opacity(0.08), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(ActivityDetailFormat.bad.opacity(0.3)))
        .padding(.top, 16)
    }
}

struct MetricGrid: View {
    let cells: [ActivityDetailFormat.Cell]
    var compact = false
    var onInfo: (() -> Void)?

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 16, alignment: .topLeading), GridItem(.flexible(), alignment: .topLeading)], alignment: .leading, spacing: 24) {
            ForEach(Array(cells.enumerated()), id: \.offset) { _, cell in
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 4) {
                        Text(cell.label).font(AppFont.body(13)).foregroundStyle(Color.muted).lineLimit(1)
                        if cell.info, let onInfo {
                            Button(action: onInfo) {
                                Image(systemName: "info.circle.fill").font(.system(size: 11)).foregroundStyle(Color.faint)
                                    .frame(width: 24, height: 20).contentShape(Rectangle())
                            }
                            .accessibilityLabel("What \(cell.label.lowercased()) means")
                        }
                    }
                    MetricValue(parts: cell.parts, size: compact ? 28 : 34, color: cell.metric.color)
                    if let status = cell.status {
                        StatusLine(tone: status.tone, text: status.text)
                    }
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

struct LogFeelPrompt: View {
    var disabled = false
    let action: () -> Void

    var body: some View {
        DetailSection(nil) {
            VStack(alignment: .leading, spacing: 0) {
                Text("How did it feel?").font(AppFont.body(18, weight: .semibold)).foregroundStyle(Color.ink)
                Text("Effort, energy, soreness and pain. Takes ten seconds while it's fresh.")
                    .font(AppFont.body(15)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                    .padding(.top, 8)
                Button("Log how it felt", action: action)
                    .buttonStyle(VoltPromptStyle())
                    .padding(.top, 16)
            }
            .padding(.top, 24)
        }
    }
}

/// The page's one volt control: 48 high, radius 24.
private struct VoltPromptStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(AppFont.body(16, weight: .bold))
            .foregroundStyle(Color.bg)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(Color.volt.opacity(configuration.isPressed ? 0.8 : 1), in: Capsule())
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.snappy(duration: 0.15), value: configuration.isPressed)
    }
}

// MARK: Session read

struct SessionReadSection: View {
    let read: ActivityDetailFormat.Read

    var body: some View {
        DetailSection("Session read") {
            if let badge = read.badge {
                ToneBadge(text: badge, color: read.tone == .info ? .inkSoft : (read.tone == .good ? .mobility : ActivityDetailFormat.bad),
                          fill: read.tone == .info ? Color(hex: 0x1A1E27) : nil)
            }
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                Text(read.headline)
                    .font(AppFont.body(18, weight: .semibold)).foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 12)
                if let explanation = read.explanation {
                    Text(explanation).font(AppFont.body(15)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 8)
                }
                if !read.lines.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(read.lines.enumerated()), id: \.offset) { _, line in
                            HStack(alignment: .center, spacing: 8) {
                                StatusLine(tone: line.tone, text: line.text)
                                Spacer(minLength: 0)
                                if !line.series.isEmpty {
                                    Spark(values: line.series, color: line.tone.color).frame(width: 40, height: 22)
                                }
                            }
                        }
                    }
                    .padding(.top, 12)
                }
                if let next = read.nextTime {
                    Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.top, 16)
                    Text("\(Text("Next time").font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink))  \(Text(next).foregroundStyle(Color(hex: 0xC9CFDA)))")
                        .font(AppFont.body(14)).lineSpacing(3)
                        .padding(.top, 12)
                }
            }
        }
    }
}

private struct Spark: View {
    let values: [Double]
    let color: Color

    var body: some View {
        Canvas { context, size in
            guard let lo = values.min(), let hi = values.max() else { return }
            let span = max(hi - lo, 0.0001)
            let points = values.enumerated().map { index, value in
                CGPoint(x: size.width * CGFloat(index) / CGFloat(max(values.count - 1, 1)), y: 2 + (size.height - 4) * (1 - CGFloat((value - lo) / span)))
            }
            var path = Path()
            path.addLines(points)
            context.stroke(path, with: .color(color), style: StrokeStyle(lineWidth: 1.6, lineCap: .round, lineJoin: .round))
            if let last = points.last { context.fill(Path(ellipseIn: CGRect(x: last.x - 2.5, y: last.y - 2.5, width: 5, height: 5)), with: .color(color)) }
        }
        .accessibilityHidden(true)
    }
}

// MARK: Main chart

struct MainChartSection: View {
    let detail: ActivityDetail
    let chips: [ActivityDetailFormat.ChartChip]
    /// Strength: one fixed heart-rate chart, no chips.
    var fixedTitle: String?
    let onMore: (String) -> Void
    @State private var selected: String?

    private var key: String { selected ?? chips.first?.key ?? "heartrate" }

    var body: some View {
        if let model = ActivityDetailFormat.chartModel(detail, key: key) {
            DetailSection(fixedTitle ?? model.title) {
                ShowMoreButton { onMore(key) }
            } content: {
                VStack(alignment: .leading, spacing: 0) {
                    MetricChart(model: model, height: fixedTitle == nil ? 132 : 104)
                        .padding(.top, 16)
                    if chips.count > 1 && fixedTitle == nil {
                        ScrollView(.horizontal) {
                            HStack(spacing: 6) {
                                ForEach(chips, id: \.key) { chip in
                                    Button {
                                        withAnimation(.snappy) { selected = chip.key }
                                    } label: {
                                        HStack(spacing: 5) {
                                            Circle().fill(chip.color).frame(width: 8, height: 8)
                                            Text(chip.title)
                                        }
                                        .font(AppFont.body(12, weight: .semibold))
                                        .foregroundStyle(chip.key == key ? Color.ink : Color.inkSoft)
                                        .padding(.horizontal, 10)
                                        .frame(height: 32)
                                        .background(chip.key == key ? Color.raised : Color(hex: 0x151922), in: Capsule())
                                        .frame(minHeight: 44)
                                        .contentShape(Rectangle())
                                    }
                                    .accessibilityAddTraits(chip.key == key ? .isSelected : [])
                                }
                            }
                        }
                        .scrollIndicators(.hidden)
                        .padding(.top, 6)
                    }
                }
            }
        }
    }
}

// MARK: Splits

struct SplitsSection: View {
    let rows: [ActivityDetailFormat.SplitRow]
    let lines: [(tone: StatusTone, text: String)]
    let onMore: () -> Void

    var body: some View {
        DetailSection("Splits") {
            ShowMoreButton(action: onMore)
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                row(km: "Km", pace: nil, hr: "HR", cadence: "Cad", power: "W", header: true)
                    .padding(.top, 12)
                    .padding(.bottom, 8)
                ForEach(rows, id: \.km) { split in
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    row(km: "\(split.km)", pace: split, hr: split.heartRate.map(String.init) ?? "–",
                        cadence: split.cadence.map(String.init) ?? "–", power: split.power.map(String.init) ?? "–", header: false)
                        .frame(height: 40)
                }
                if !lines.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(lines.enumerated()), id: \.offset) { _, line in StatusLine(tone: line.tone, text: line.text) }
                    }
                    .padding(.top, 12)
                }
            }
        }
    }

    private func row(km: String, pace: ActivityDetailFormat.SplitRow?, hr: String, cadence: String, power: String, header: Bool) -> some View {
        HStack(spacing: 8) {
            Text(km).frame(width: 24, alignment: .leading)
                .foregroundStyle(header ? Color.muted : Color.muted)
            Group {
                if let pace {
                    GeometryReader { proxy in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .fill(pace.fastest ? Metric.pace.color : Metric.pace.color.opacity(0.22))
                                .frame(width: proxy.size.width * pace.share)
                            Text(pace.pace).foregroundStyle(pace.fastest ? Color.bg : Metric.pace.color).padding(.leading, 10)
                        }
                    }
                    .frame(height: 26)
                } else {
                    Text("Pace").foregroundStyle(Color.muted).frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(maxWidth: .infinity)
            Text(hr).frame(width: 40, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.heartRate.color)
            Text(cadence).frame(width: 40, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.cadence.color)
            Text(power).frame(width: 40, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.power.color)
        }
        .font(header ? AppFont.body(12) : AppFont.number(18))
    }
}

// MARK: Running form

struct RunningFormSection: View {
    let cells: [ActivityDetailFormat.FormCell]
    let summary: (tone: StatusTone, text: String)?
    let onMore: () -> Void

    var body: some View {
        DetailSection("Running form") {
            ShowMoreButton(action: onMore)
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12, alignment: .topLeading), count: 3), alignment: .leading, spacing: 16) {
                    ForEach(cells, id: \.label) { cell in
                        VStack(alignment: .leading, spacing: 0) {
                            Text(cell.label).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1).minimumScaleFactor(0.8)
                            MetricValue(parts: [(cell.value, cell.unit)], size: 24, color: cell.metric.color, unitColor: Color.muted)
                                .padding(.top, 4)
                            ThreeStepMeter(step: cell.step, lit: cell.ranged ? (cell.good ? Color.mobility : ActivityDetailFormat.warn) : Color.inkSoft)
                                .padding(.top, 10)
                            Text("\(Text(cell.word).font(AppFont.body(12, weight: .semibold)).foregroundStyle(cell.ranged ? (cell.good ? Color.mobility : ActivityDetailFormat.warn) : Color.ink))\(Text(cell.usual.map { " · usual \($0)" } ?? ""))")
                                .font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1).minimumScaleFactor(0.8)
                                .padding(.top, 6)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                .padding(.top, 16)
                if let summary {
                    StatusLine(tone: summary.tone, text: summary.text).padding(.top, 16)
                }
            }
        }
    }
}

// MARK: Zones

struct ZoneBars: View {
    let rows: [ActivityDetailFormat.ZoneRow]
    var trackColor = Color(hex: 0x151922)

    var body: some View {
        VStack(spacing: 12) {
            ForEach(rows, id: \.name) { row in
                let off = row.pct < 0.5
                HStack(spacing: 12) {
                    Text(row.name).font(AppFont.body(13)).foregroundStyle(off ? Color.dim : Color.inkSoft).frame(width: 60, alignment: .leading)
                    GeometryReader { proxy in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 6, style: .continuous).fill(trackColor)
                            if !off {
                                RoundedRectangle(cornerRadius: 6, style: .continuous).fill(row.color)
                                    .frame(width: max(proxy.size.width * min(row.pct, 100) / 100, 4))
                            }
                        }
                    }
                    .frame(height: 20)
                    Text("\(Int(row.pct.rounded()))%").font(AppFont.number(17)).foregroundStyle(off ? Color.dim : Color.ink).frame(width: 40, alignment: .trailing)
                    Text(ActivityDetailFormat.zoneTime(row.minutes)).font(AppFont.body(13)).foregroundStyle(Color.muted).frame(width: 60, alignment: .trailing)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

struct ZonesSection: View {
    let heartRate: [ActivityDetailFormat.ZoneRow]
    let power: [ActivityDetailFormat.ZoneRow]
    let summary: (tone: StatusTone, text: String)?
    let onMore: () -> Void
    @State private var showPower = false

    var body: some View {
        DetailSection("Time in zones") {
            ShowMoreButton(action: onMore)
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                if !heartRate.isEmpty && !power.isEmpty {
                    SegmentedPills(options: ["Heart rate", "Power"], selection: Binding(get: { showPower ? 1 : 0 }, set: { showPower = $0 == 1 }))
                        .padding(.top, 16)
                }
                ZoneBars(rows: showPower || heartRate.isEmpty ? power : heartRate).padding(.top, 16)
                if let summary, !showPower {
                    StatusLine(tone: summary.tone, text: summary.text).padding(.top, 16)
                }
            }
        }
    }
}

struct SegmentedPills: View {
    let options: [String]
    @Binding var selection: Int

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(options.enumerated()), id: \.offset) { index, title in
                Button {
                    withAnimation(.snappy) { selection = index }
                } label: {
                    Text(title)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(index == selection ? Color.ink : Color.muted)
                        .frame(maxWidth: .infinity, minHeight: 30)
                        .background(index == selection ? Color.raised : .clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                        .contentShape(Rectangle())
                }
                .accessibilityAddTraits(index == selection ? .isSelected : [])
            }
        }
        .padding(2)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(Color.cardBorder))
        .frame(minHeight: 44)
    }
}

// MARK: Bests and comparisons

struct ComparedSection: View {
    let cells: [ActivityDetailFormat.Cell]

    var body: some View {
        DetailSection("Compared with your rides") {
            MetricGrid(cells: cells, compact: true).padding(.top, 16)
        }
    }
}

struct PowerBestsSection: View {
    let rows: [ActivityDetailFormat.BestRow]

    var body: some View {
        DetailSection("Power bests") {
            Text("vs all-time").font(AppFont.body(13, weight: .medium)).foregroundStyle(Color.muted)
        } content: {
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                    let color = ColorScale.share.color(row.share)
                    HStack(spacing: 10) {
                        Text(row.label).font(AppFont.number(16)).foregroundStyle(Color(hex: 0xC9CFDA)).frame(width: 44, alignment: .leading)
                        GeometryReader { proxy in
                            ZStack(alignment: .leading) {
                                Capsule().fill(Color(hex: 0x151922))
                                Capsule().fill(color).frame(width: proxy.size.width * row.share)
                            }
                        }
                        .frame(height: 10)
                        MetricValue(parts: [("\(row.watts)", "W")], size: 22, color: Metric.power.color, unitColor: Metric.power.color.opacity(0.75))
                            .frame(width: 56, alignment: .trailing)
                        VStack(alignment: .trailing, spacing: 0) {
                            Text(row.record ? "PR" : "\(Int((row.share * 100).rounded()))%").font(AppFont.number(15)).foregroundStyle(row.record ? Color.volt : color)
                            if let best = row.best, !row.record { Text("of \(best)").font(AppFont.body(10, weight: .medium)).foregroundStyle(Color.muted) }
                        }
                        .frame(width: 52, alignment: .trailing)
                    }
                    .frame(height: 44)
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(.top, 8)
        }
    }
}

struct BestEffortsSection: View {
    let rows: [ActivityDetailFormat.EffortRow]

    var body: some View {
        DetailSection("Best efforts") {
            VStack(spacing: 0) {
                line("Distance", "Pace", "Time", "HR", header: true).padding(.top, 12).padding(.bottom, 8)
                ForEach(rows, id: \.label) { row in
                    Rectangle().fill(Color.cardBorder).frame(height: 1)
                    line(row.label, row.pace, row.time, row.heartRate.map(String.init) ?? "–", header: false).frame(height: 48)
                }
            }
        }
    }

    private func line(_ a: String, _ b: String, _ c: String, _ d: String, header: Bool) -> some View {
        HStack {
            Text(a).frame(maxWidth: .infinity, alignment: .leading).foregroundStyle(header ? Color.muted : Color.ink)
            Text(b).frame(maxWidth: .infinity, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.pace.color)
            Text(c).frame(maxWidth: .infinity, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.time.color)
            Text(d).frame(width: 60, alignment: .trailing).foregroundStyle(header ? Color.muted : Metric.heartRate.color)
        }
        .font(header ? AppFont.body(12) : AppFont.number(18))
    }
}

// MARK: Lifts

struct LiftsSection: View {
    let rows: [ActivityDetailFormat.LiftRow]
    let comparedTo: String?

    var body: some View {
        DetailSection("The work you did") {
            if comparedTo != nil { Text("vs last time").font(AppFont.body(13, weight: .medium)).foregroundStyle(Color.muted) }
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                    if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                    HStack(alignment: .top, spacing: 12) {
                        Text(String(format: "%02d", index + 1)).font(AppFont.number(17)).foregroundStyle(Color.strength).frame(width: 20, alignment: .leading)
                        VStack(alignment: .leading, spacing: 0) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(row.name).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                                    if let muscle = row.muscle { Text(muscle).font(AppFont.body(12)).foregroundStyle(Color.muted) }
                                }
                                Spacer(minLength: 8)
                                if let badge = row.badge { badgeView(badge) }
                            }
                            FlowLayout(spacing: 4) {
                                ForEach(Array(row.sets.enumerated()), id: \.offset) { _, set in
                                    Text("\(Text(set.value).font(AppFont.number(15)).foregroundStyle(Color(hex: 0xC9CFDA)))\(Text(set.unit).font(AppFont.body(10, weight: .medium)).foregroundStyle(Color.faint))")
                                        .padding(.horizontal, 8)
                                        .frame(height: 26)
                                        .background(Color.inset, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                                        .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color.cardBorder))
                                }
                            }
                            .padding(.top, 8)
                            if let last = row.last {
                                Text(last).font(AppFont.body(12)).foregroundStyle(Color.muted).padding(.top, 8)
                            }
                            if let next = row.next {
                                Text("\(Text("Next: ").foregroundStyle(Color.muted))\(Text(next).font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.volt))")
                                    .font(AppFont.body(12)).padding(.top, 6)
                            }
                        }
                    }
                    .padding(.vertical, 12)
                }
            }
            .padding(.top, 4)
        }
    }

    private func badgeView(_ badge: (text: String, tone: String)) -> some View {
        let color: Color = switch badge.tone {
        case "pr": .volt
        case "good": .mobility
        case "warn": ActivityDetailFormat.warn
        default: .inkSoft
        }
        return ToneBadge(text: badge.text, color: color, fill: badge.tone == "same" ? Color(hex: 0x1A1E27) : nil)
    }
}

// MARK: How it felt, win, coach

struct FeelSection: View {
    let cells: [ActivityDetailFormat.Feel]
    let note: String?
    let onEdit: () -> Void

    var body: some View {
        DetailSection("How it felt") {
            QuietPillButton(title: "Edit", action: onEdit)
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top, spacing: 0) {
                    ForEach(Array(cells.enumerated()), id: \.offset) { index, cell in
                        VStack(alignment: .leading, spacing: 0) {
                            Text(cell.label).font(AppFont.body(13)).foregroundStyle(Color.muted)
                            Text("\(Text("\(cell.value)").font(AppFont.number(28)).foregroundStyle(cell.color))\(Text("/\(cell.scale)").font(AppFont.number(14)).foregroundStyle(Color.muted))")
                                .padding(.top, 6)
                            Text(cell.word).font(AppFont.body(13, weight: .semibold)).foregroundStyle(cell.color).lineLimit(1).minimumScaleFactor(0.8)
                                .padding(.top, 4)
                        }
                        .padding(.leading, index > 0 ? 12 : 0)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .overlay(alignment: .leading) {
                            if index > 0 { Rectangle().fill(Color.cardBorder).frame(width: 1) }
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(cell.label) \(cell.value) of \(cell.scale), \(cell.word)")
                    }
                }
                .padding(.top, 16)
                if let note {
                    Text(note).font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                        .padding(.leading, 12)
                        .overlay(alignment: .leading) { Rectangle().fill(Color.outline).frame(width: 2) }
                        .padding(.top, 16)
                }
            }
        }
    }
}

struct WinRow: View {
    let win: ActivityDetail.Win

    private var symbol: String {
        switch win.kind {
        case "progress": "arrow.up.right"
        case "consistency": "flame.fill"
        default: "trophy.fill"
        }
    }

    var body: some View {
        DetailSection(nil) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: symbol)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(Color.volt)
                    .frame(width: 44, height: 44)
                    .background(Color.volt.opacity(0.12), in: Circle())
                VStack(alignment: .leading, spacing: 4) {
                    Text(win.headline ?? "").font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color.ink)
                    if let detail = win.detail?.nilIfEmpty {
                        Text(detail).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.top, 24)
            .accessibilityElement(children: .combine)
        }
    }
}

struct CoachSection: View {
    let state: ActivityDetailFormat.CoachState
    let asking: Bool
    let offline: Bool
    let sport: String
    let onAsk: () -> Void
    let onMore: () -> Void

    var body: some View {
        DetailSection("Coach take") {
            if case .take = state { ShowMoreButton(action: onMore) }
        } content: {
            VStack(alignment: .leading, spacing: 0) {
                switch state {
                case .take(let take):
                    if let headline = take.headline {
                        Text(headline).font(AppFont.body(17, weight: .semibold)).foregroundStyle(Color.ink).lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 12)
                    }
                    if let body = take.body {
                        Text(body).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).lineSpacing(5).lineLimit(4)
                            .padding(.top, 12)
                    }
                case .pending:
                    HStack(spacing: 10) {
                        ProgressView().tint(.muted)
                        Text("Coach is writing… it lands here and on the web page.").font(AppFont.body(15)).foregroundStyle(Color(hex: 0xC9CFDA))
                    }
                    .padding(.top, 12)
                case .canAsk(let failed):
                    if !offline {
                        Text(failed ? "The last try failed. Ask again and it lands here and on the web page."
                                    : "No written take yet. Ask what to take from this \(sport); it lands here and on the web page.")
                            .font(AppFont.body(15)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(4)
                            .padding(.top, 12)
                    }
                    Button(action: onAsk) {
                        HStack(spacing: 8) {
                            if asking { ProgressView().tint(.ink) }
                            Text(offline ? "Ask the coach · needs connection" : "Ask the coach")
                        }
                    }
                    .buttonStyle(OutlineButtonStyle(height: 44))
                    .opacity(offline ? 0.45 : 1)
                    .disabled(asking || offline)
                    .padding(.top, 16)
                case .none:
                    EmptyView()
                }
            }
        }
    }
}

struct NoStreamsPlaceholder: View {
    var body: some View {
        DetailSection(nil) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "waveform.path.ecg").font(.system(size: 15, weight: .semibold)).foregroundStyle(Color.muted)
                VStack(alignment: .leading, spacing: 4) {
                    Text("No recorded streams").font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                    Text("No map, charts or zones for this one. Record with the Watch next time to get them.")
                        .font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
                }
                Spacer(minLength: 0)
            }
            .padding(16)
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.outline, style: StrokeStyle(lineWidth: 1, dash: [4, 4])))
            .padding(.top, 24)
        }
    }
}
