import Charts
import MapKit
import SwiftUI

// The detail screen's cards, top to bottom (docs/design/artboards/iOSActivityDetail.dc.html).

private typealias Format = ActivityDetailFormat

private func numberText(_ value: String, size: CGFloat, unit: String?, unitSize: CGFloat = 13, color: Color = .ink) -> Text {
    Text("\(Text(value).font(AppFont.number(size)).foregroundStyle(color))\(Text(unit.map { " \($0)" } ?? "").font(AppFont.body(unitSize, weight: .medium)).foregroundStyle(Color.muted))")
}

private struct SmallKicker: View {
    let text: String
    var size: CGFloat = 9
    var color: Color = .muted

    var body: some View {
        Text(text.uppercased())
            .font(AppFont.body(size, weight: .semibold))
            .tracking(size * 0.14)
            .foregroundStyle(color)
            .lineLimit(1)
    }
}

// MARK: Pain alert and win

struct PainAlertCard: View {
    let pain: Int
    let note: String?

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(Format.bad)
            VStack(alignment: .leading, spacing: 3) {
                Text("Pain \(pain)/10 logged").font(AppFont.body(15, weight: .bold)).foregroundStyle(Color.ink)
                if let note {
                    Text("“\(note)”").font(AppFont.body(13)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(2)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Format.bad.opacity(0.08), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Format.bad.opacity(0.3)))
    }
}

struct WinStrip: View {
    let win: ActivityDetail.Win

    private var symbol: String {
        switch win.kind {
        case "progress": "chart.line.uptrend.xyaxis"
        case "consistency": "flame"
        default: "trophy"
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: symbol)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(Color.volt)
                .frame(width: 22)
            VStack(alignment: .leading, spacing: 3) {
                Text(win.headline ?? "").font(AppFont.body(15, weight: .bold)).foregroundStyle(Color.ink)
                if let detail = win.detail?.nilIfEmpty {
                    Text(detail).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.volt.opacity(0.07), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.volt.opacity(0.22)))
    }
}

// MARK: Route map

struct RouteMapCard: View {
    let coordinates: [CLLocationCoordinate2D]
    let color: Color
    let tags: [String]
    @State private var expanded = false

    var body: some View {
        RouteMap(coordinates: coordinates, color: color, interactive: false)
            .frame(height: 210)
            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cardBorder))
            .overlay(alignment: .topLeading) {
                HStack(spacing: 6) {
                    ForEach(tags, id: \.self) { tag in
                        Text(tag)
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(Color.ink)
                            .padding(.horizontal, 10)
                            .frame(height: 26)
                            .background(Color.bg.opacity(0.82), in: Capsule())
                            .overlay(Capsule().strokeBorder(Color.outline))
                    }
                }
                .padding(12)
            }
            .overlay(alignment: .topTrailing) {
                Image(systemName: "arrow.up.left.and.arrow.down.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 32, height: 32)
                    .background(Color.bg.opacity(0.82), in: Circle())
                    .overlay(Circle().strokeBorder(Color.outline))
                    .padding(12)
            }
            .contentShape(Rectangle())
            .onTapGesture { expanded = true }
            .accessibilityAddTraits(.isButton)
            .accessibilityLabel("Route map")
            .fullScreenCover(isPresented: $expanded) {
                RouteMap(coordinates: coordinates, color: color, interactive: true)
                    .ignoresSafeArea()
                    .overlay(alignment: .topTrailing) {
                        Button { expanded = false } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 15, weight: .bold))
                                .foregroundStyle(Color.ink)
                                .frame(width: 44, height: 44)
                                .background(Color.bg.opacity(0.85), in: Circle())
                        }
                        .padding(.trailing, 16)
                        .padding(.top, 8)
                        .accessibilityLabel("Close map")
                    }
            }
    }
}

private struct RouteMap: View {
    let coordinates: [CLLocationCoordinate2D]
    let color: Color
    let interactive: Bool

    private var region: MapCameraPosition {
        let points = coordinates.map { MKMapPoint($0) }
        var rect = points.reduce(MKMapRect.null) { $0.union(MKMapRect(origin: $1, size: MKMapSize(width: 0, height: 0))) }
        let pad = max(rect.width, rect.height) * 0.18 + 200
        rect = rect.insetBy(dx: -pad, dy: -pad)
        return .rect(rect)
    }

    var body: some View {
        Map(initialPosition: region, interactionModes: interactive ? .all : []) {
            MapPolyline(coordinates: coordinates)
                .stroke(color, style: StrokeStyle(lineWidth: interactive ? 4.5 : 3.5, lineCap: .round, lineJoin: .round))
            if let start = coordinates.first {
                Annotation("Start", coordinate: start, anchor: .center) {
                    Circle().fill(Color.mobility).frame(width: 12, height: 12).overlay(Circle().stroke(Color.bg, lineWidth: 2))
                }
                .annotationTitles(.hidden)
            }
            if let end = coordinates.last {
                Annotation("Finish", coordinate: end, anchor: .center) {
                    Circle().fill(Color.ink).frame(width: 10, height: 10).overlay(Circle().stroke(Color.bg, lineWidth: 2))
                }
                .annotationTitles(.hidden)
            }
        }
        .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll))
        .environment(\.colorScheme, .dark)
        .allowsHitTesting(interactive)
    }
}

// MARK: Stat block

struct StatBlockCard: View {
    let block: ActivityDetailFormat.StatBlock

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 0) {
                ForEach(block.headline, id: \.label) { item in
                    VStack(alignment: .leading, spacing: 6) {
                        Kicker(item.label)
                        numberText(item.value, size: 48, unit: item.unit)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            ForEach(Array(block.gauges.enumerated()), id: \.offset) { _, gauge in
                Divider().overlay(Color.cardBorder).padding(.vertical, 16)
                GaugeView(gauge: gauge)
            }
            if !block.footer.isEmpty {
                Divider().overlay(Color.cardBorder).padding(.top, 16).padding(.bottom, 12)
                HStack(spacing: 16) {
                    ForEach(block.footer, id: \.0) { label, value in
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            SmallKicker(text: label, size: 10)
                            Text(value).font(AppFont.number(16)).foregroundStyle(Color.ink)
                        }
                    }
                    Spacer(minLength: 0)
                }
            }
        }
        .padding(2)
        .card()
    }
}

struct GaugeView: View {
    let gauge: ActivityDetailFormat.Gauge

    private var icon: (symbol: String, color: Color) {
        switch gauge.icon {
        case .power: ("bolt.fill", .ride)
        case .heart: ("heart.fill", Format.heartRateColor)
        case .pace: ("stopwatch", .run)
        case .climb: ("mountain.2.fill", Color(hex: 0xA99CFF))
        case .volume: ("dumbbell.fill", .strength)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .bottom) {
                HStack(spacing: 10) {
                    Image(systemName: icon.symbol)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(icon.color)
                        .frame(width: 32, height: 32)
                        .background(icon.color.opacity(0.14), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    VStack(alignment: .leading, spacing: 3) {
                        SmallKicker(text: gauge.label, size: 10)
                        numberText(gauge.value, size: 28, unit: gauge.unit, color: gauge.valueColor ?? .ink)
                    }
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 1) {
                    ForEach(Array(gauge.side.enumerated()), id: \.offset) { _, line in
                        Text("\(Text(line.bold).font(AppFont.number(16)).foregroundStyle(Color.ink)) \(Text(line.text).font(AppFont.body(12)).foregroundStyle(Color.muted))")
                    }
                }
            }
            GaugeTrack(gauge: gauge).frame(height: 16).padding(.top, 10)
            GaugeLabels(labels: gauge.labels).frame(height: 13).padding(.top, 3)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct GaugeTrack: View {
    let gauge: ActivityDetailFormat.Gauge

    var body: some View {
        GeometryReader { proxy in
            let width = proxy.size.width
            let gaps = CGFloat(max(gauge.bands.count - 1, 0)) * 2
            ZStack(alignment: .leading) {
                if gauge.bands.isEmpty {
                    Capsule().fill(Color(hex: 0x5B6478).opacity(0.28)).frame(height: 8)
                } else {
                    HStack(spacing: 2) {
                        ForEach(Array(gauge.bands.enumerated()), id: \.offset) { _, band in
                            RoundedRectangle(cornerRadius: 2)
                                .fill(band.color.opacity(0.28))
                                .frame(width: max(0, (width - gaps) * band.width), height: 8)
                        }
                    }
                }
                if let range = gauge.range, range.upperBound > range.lowerBound {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.ink.opacity(0.35))
                        .frame(width: width * (range.upperBound - range.lowerBound), height: 8)
                        .offset(x: width * range.lowerBound)
                }
                if let tick = gauge.tick {
                    RoundedRectangle(cornerRadius: 1).fill(Color.ink).frame(width: 2, height: 16).offset(x: width * tick - 1)
                }
                Circle()
                    .fill(Color.ink)
                    .frame(width: 16, height: 16)
                    .overlay(Circle().stroke(Color.card, lineWidth: 3))
                    .offset(x: min(max(width * gauge.dot - 8, -2), width - 14))
            }
            .frame(height: 16)
        }
    }
}

private struct GaugeLabels: View {
    let labels: [ActivityDetailFormat.Gauge.AxisLabel]

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .topLeading) {
                ForEach(Array(labels.enumerated()), id: \.offset) { _, label in
                    let text = Text(label.text).font(AppFont.body(10)).foregroundStyle(Color.faint)
                    if let at = label.at {
                        text.fixedSize().offset(x: min(proxy.size.width * at, proxy.size.width - 70))
                    } else {
                        text.fixedSize().frame(width: proxy.size.width, alignment: .trailing)
                    }
                }
            }
        }
    }
}

// MARK: Session read

struct SessionReadView: View {
    let read: ActivityDetailFormat.SessionReadCard

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Session read")
                Spacer()
                if let badge = read.badge?.nilIfEmpty { Pill(text: badge, color: Format.toneColor(read.tone)) }
            }
            Text(read.headline)
                .font(AppFont.body(17, weight: .bold))
                .foregroundStyle(Color.ink)
                .padding(.top, 8)
                .fixedSize(horizontal: false, vertical: true)
            if !read.signals.isEmpty {
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible())], spacing: 8) {
                    ForEach(Array(read.signals.enumerated()), id: \.offset) { _, signal in
                        VStack(alignment: .leading, spacing: 5) {
                            HStack(spacing: 6) {
                                Circle().fill(Format.toneColor(signal.tone)).frame(width: 6, height: 6)
                                SmallKicker(text: signal.label)
                            }
                            Text(signal.value ?? "").font(AppFont.number(20)).foregroundStyle(Color.ink).lineLimit(1).minimumScaleFactor(0.7)
                            if let detail = signal.detail?.nilIfEmpty {
                                Text(detail).font(AppFont.body(11)).foregroundStyle(Color.muted).lineLimit(2)
                            }
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .frame(maxWidth: .infinity, minHeight: 96, alignment: .topLeading)
                        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
                    }
                }
                .padding(.top, 12)
            }
            if let next = read.nextTime {
                Divider().overlay(Color.cardBorder).padding(.vertical, 12)
                Text("\(Text("Next time · ").font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink))\(Text(next).font(AppFont.body(13)).foregroundStyle(Color(hex: 0xC9CFDA)))")
                    .lineSpacing(2)
            }
        }
        .card()
    }
}

// MARK: Stream chart

struct StreamChartCard: View {
    let charts: ActivityDetailFormat.ChartSet
    @State private var selectedKey: String?
    @State private var scrub: Double?

    private var tab: ActivityDetailFormat.ChartTab {
        charts.tabs.first { $0.key == selectedKey } ?? charts.tabs[0]
    }

    private var title: String {
        if charts.compact || tab.key == "heartrate" { return "Heart rate" }
        return tab.heartRate != nil ? "\(tab.title) & heart rate" : tab.title
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker(title)
                Spacer()
                if let average = tab.averageText {
                    Text(average).font(AppFont.body(11)).foregroundStyle(Color.muted).lineLimit(1)
                }
            }
            if charts.tabs.count > 1 {
                ScrollView(.horizontal) {
                    HStack(spacing: 6) {
                        ForEach(charts.tabs, id: \.key) { item in
                            Button(item.title) {
                                selectedKey = item.key
                                scrub = nil
                            }
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(item.key == tab.key ? Color.ink : Color.inkSoft)
                            .padding(.horizontal, 11)
                            .frame(height: 28)
                            .background(item.key == tab.key ? Color.raised : .clear, in: Capsule())
                            .overlay(Capsule().strokeBorder(item.key == tab.key ? Color.raised : Color.outline))
                            .frame(minHeight: 44)
                            .contentShape(Rectangle())
                        }
                    }
                }
                .scrollIndicators(.hidden)
                .padding(.top, 4)
            }
            chart
                .frame(height: charts.compact ? 80 : 130)
                .padding(.top, charts.tabs.count > 1 ? 4 : 12)
        }
        .padding(.top, -2)
        .card()
        .sensoryFeedback(.selection, trigger: scrub.map { Int($0) })
    }

    private var chart: some View {
        Chart {
            if let area = tab.area {
                ForEach(area.points, id: \.x) { point in
                    AreaMark(x: .value("Time", point.x), y: .value(area.unit, point.y), series: .value("Series", "area"))
                        .foregroundStyle(tab.color.opacity(tab.key == "heartrate" ? 0.14 : 0.22))
                    LineMark(x: .value("Time", point.x), y: .value(area.unit, point.y), series: .value("Series", "areaLine"))
                        .foregroundStyle(tab.color)
                        .lineStyle(StrokeStyle(lineWidth: 1.5))
                }
                if let average = area.average, !charts.compact {
                    RuleMark(y: .value("Average", average))
                        .foregroundStyle(Color.ink.opacity(0.35))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
                }
            }
            if let hr = tab.heartRate {
                ForEach(hr.points, id: \.x) { point in
                    LineMark(x: .value("Time", point.x), y: .value("bpm", point.y), series: .value("Series", "hr"))
                        .foregroundStyle(Format.heartRateColor)
                        .lineStyle(StrokeStyle(lineWidth: 1.8))
                        .interpolationMethod(.catmullRom)
                }
            }
            if let scrub {
                RuleMark(x: .value("Time", scrub))
                    .foregroundStyle(Color.ink.opacity(0.5))
                    .annotation(position: .top, spacing: 0, overflowResolution: .init(x: .fit(to: .chart), y: .disabled)) {
                        scrubPill(scrub)
                    }
            }
        }
        .chartYScale(domain: 0...1.12)
        .chartYAxis(.hidden)
        .chartXScale(domain: 0...charts.duration)
        .chartXSelection(value: $scrub)
        .chartXAxis {
            let ticks = charts.ticks
            AxisMarks(values: ticks) { value in
                let minutes = value.as(Double.self) ?? 0
                AxisValueLabel(anchor: minutes == 0 ? .topLeading : minutes == ticks.last ? .topTrailing : .top) {
                    Text(ActivityFormat.clock(minutes)).font(AppFont.body(10)).foregroundStyle(Color.muted)
                }
            }
        }
    }

    private func scrubPill(_ minute: Double) -> some View {
        var parts = [ActivityFormat.clock(minute)]
        if let point = Format.nearest(tab.area, at: minute) { parts.append(Format.scrubValue(tab.key, point.raw)) }
        if let hr = Format.nearest(tab.heartRate, at: minute) { parts.append("\(Int(hr.raw.rounded())) bpm") }
        return Text(parts.joined(separator: " · "))
            .font(AppFont.body(11, weight: .semibold))
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 10)
            .frame(height: 22)
            .background(Color.raised, in: Capsule())
    }
}

// MARK: Zones

struct ZonesCard: View {
    let heartRate: [ActivityDetailFormat.ZoneRow]
    let power: [ActivityDetailFormat.ZoneRow]
    @State private var showPower = false

    private var rows: [ActivityDetailFormat.ZoneRow] { showPower && !power.isEmpty ? power : (heartRate.isEmpty ? power : heartRate) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker(heartRate.isEmpty || power.isEmpty ? (power.isEmpty ? "Time in HR zones" : "Time in power zones") : "Time in zones")
                Spacer()
                if !heartRate.isEmpty && !power.isEmpty {
                    HStack(spacing: 6) {
                        toggle("HR", on: !showPower) { showPower = false }
                        toggle("Power", on: showPower) { showPower = true }
                    }
                }
            }
            GeometryReader { proxy in
                let visible = rows.filter { $0.pct > 0 }
                let total = max(visible.map(\.pct).reduce(0, +), 1)
                let gaps = CGFloat(max(visible.count - 1, 0)) * 2
                HStack(spacing: 2) {
                    ForEach(visible, id: \.name) { row in
                        Rectangle().fill(row.color).frame(width: (proxy.size.width - gaps) * row.pct / total)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 5))
            }
            .frame(height: 10)
            .padding(.top, 12)
            VStack(spacing: 0) {
                ForEach(rows, id: \.name) { row in
                    HStack(spacing: 10) {
                        Text(row.name)
                            .font(AppFont.number(15))
                            .foregroundStyle(row.name == "Z1" ? Color.muted : row.color)
                            .frame(width: 30, alignment: .leading)
                        VStack(alignment: .leading, spacing: 3) {
                            GeometryReader { proxy in
                                ZStack(alignment: .leading) {
                                    Capsule().fill(Color(hex: 0x1A1E27))
                                    Capsule().fill(row.color).frame(width: proxy.size.width * min(row.pct, 100) / 100)
                                }
                            }
                            .frame(height: 6)
                            Text(row.range).font(AppFont.body(11)).foregroundStyle(Color.muted).lineLimit(1)
                        }
                        Text(ActivityFormat.clock(row.minutes))
                            .font(AppFont.body(12))
                            .monospacedDigit()
                            .foregroundStyle(Color(hex: 0xC9CFDA))
                            .frame(width: 52, alignment: .trailing)
                        Text("\(Int(row.pct.rounded()))%")
                            .font(AppFont.number(15))
                            .foregroundStyle(row.pct == 0 ? Color.muted : (row.highlight ? Color.mobility : Color.ink))
                            .frame(width: 38, alignment: .trailing)
                    }
                    .padding(.vertical, 5)
                }
            }
            .padding(.top, 10)
        }
        .card()
    }

    private func toggle(_ title: String, on: Bool, action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .font(AppFont.body(12, weight: .semibold))
            .foregroundStyle(on ? Color.ink : Color.inkSoft)
            .padding(.horizontal, 11)
            .frame(height: 28)
            .background(on ? Color.raised : .clear, in: Capsule())
            .overlay(Capsule().strokeBorder(on ? Color.raised : Color.outline))
            .frame(minHeight: 44)
            .contentShape(Rectangle())
    }
}

// MARK: Ride load and best power

struct LoadCard: View {
    let note: String
    let tiles: [ActivityDetailFormat.LoadTile]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Kicker("Load")
                Spacer()
                Text(note).font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                ForEach(tiles, id: \.label) { tile in
                    VStack(alignment: .leading, spacing: 6) {
                        SmallKicker(text: tile.label)
                        if tile.muted {
                            Text(tile.value).font(AppFont.number(18)).foregroundStyle(Color.muted).lineLimit(1).minimumScaleFactor(0.7)
                        } else {
                            numberText(tile.value, size: 24, unit: tile.unit, unitSize: 11)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, minHeight: 64, alignment: .topLeading)
                    .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
                }
            }
        }
        .card()
    }
}

struct BestPowerCard: View {
    let efforts: [ActivityDetail.Cycling.PowerEffort]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Best power")
                Spacer()
                Text("vs your all-time").font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            .padding(.bottom, 6)
            ForEach(Array(efforts.enumerated()), id: \.offset) { index, effort in
                if index > 0 { Divider().overlay(Color.cardBorder) }
                HStack(spacing: 10) {
                    Text(effort.label.replacingOccurrences(of: " sec", with: " s"))
                        .font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color(hex: 0xC9CFDA))
                        .frame(width: 52, alignment: .leading)
                    numberText("\(Int((effort.watts ?? 0).rounded()))", size: 20, unit: "W", unitSize: 11)
                        .frame(width: 66, alignment: .leading)
                    if effort.isRecord == true {
                        Pill(text: "PR", color: .volt)
                        Spacer()
                    } else {
                        GeometryReader { proxy in
                            ZStack(alignment: .leading) {
                                Capsule().fill(Color(hex: 0x1A1E27))
                                Capsule().fill(Color.ride).frame(width: proxy.size.width * min((effort.pctOfBest ?? 0) / 100, 1))
                            }
                        }
                        .frame(height: 6)
                    }
                    Text(effort.bestWatts.map { "\(Int($0.rounded()))" } ?? "")
                        .font(AppFont.body(12)).foregroundStyle(Color.muted)
                        .frame(width: 40, alignment: .trailing)
                }
                .padding(.vertical, 9)
            }
        }
        .card()
    }
}

// MARK: Run best efforts

struct BestEffortsCard: View {
    let efforts: [ActivityDetail.BestEfforts.Effort]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Best efforts")
                Spacer()
                Text("pace · time · avg HR").font(AppFont.body(11)).foregroundStyle(Color.muted)
            }
            .padding(.bottom, 6)
            ForEach(Array(efforts.enumerated()), id: \.offset) { index, effort in
                if index > 0 { Divider().overlay(Color.cardBorder) }
                HStack(spacing: 10) {
                    Text(effort.label.replacingOccurrences(of: "m", with: " m", options: .anchored.union(.backwards)))
                        .font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color(hex: 0xC9CFDA))
                        .frame(width: 64, alignment: .leading)
                    numberText(effort.metricValue.map { Format.paceText($0 * 60) } ?? "–", size: 20, unit: "/km", unitSize: 11,
                               color: index == 0 ? .run : .ink)
                    Spacer()
                    Text(ActivityFormat.clock(effort.durationS / 60)).font(AppFont.body(12)).monospacedDigit().foregroundStyle(Color.muted)
                    Text(effort.avgHr.map { "\(Int($0.rounded()))" } ?? "")
                        .font(AppFont.body(12)).foregroundStyle(Color.muted)
                        .frame(width: 32, alignment: .trailing)
                }
                .padding(.vertical, 9)
            }
        }
        .card()
    }
}

// MARK: Lifts

struct LiftsCard: View {
    let rows: [ActivityDetailFormat.LiftRow]
    let comparedTo: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Kicker("Lifts")
                Spacer()
                if let comparedTo { Text(comparedTo).font(AppFont.body(11)).foregroundStyle(Color.muted) }
            }
            .padding(.bottom, 4)
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                if index > 0 { Divider().overlay(Color.cardBorder) }
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(row.name).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                        Spacer(minLength: 8)
                        if let badge = row.badge { badgeView(badge) }
                    }
                    HStack(alignment: .bottom) {
                        FlowLayout(spacing: 6) {
                            ForEach(Array(row.sets.enumerated()), id: \.offset) { _, set in setChip(set) }
                        }
                        if !row.series.isEmpty {
                            Sparkline(values: row.series).frame(width: 58, height: 24)
                        }
                    }
                    if let hint = row.hint {
                        Text("\(Text("Next: ").foregroundStyle(Color.muted))\(Text(hint.action).font(AppFont.body(12, weight: .semibold)).foregroundStyle(Color.volt))\(Text(hint.lead.map { " · \($0.prefix(1).lowercased() + $0.dropFirst())" } ?? "").foregroundStyle(Color.muted))")
                            .font(AppFont.body(12))
                    }
                }
                .padding(.vertical, 12)
            }
        }
        .card()
    }

    private func setChip(_ text: String) -> some View {
        let parts = text.split(separator: "×", maxSplits: 1)
        return Text("\(Text(String(parts.first ?? "")).font(AppFont.number(15)).foregroundStyle(Color(hex: 0xC9CFDA)))\(Text(parts.count > 1 ? "×\(parts[1])" : "").font(AppFont.body(10, weight: .medium)).foregroundStyle(Color.faint))")
            .padding(.horizontal, 9)
            .frame(height: 26)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func badgeView(_ badge: (text: String, tone: String)) -> some View {
        let color: Color = switch badge.tone {
        case "pr": .volt
        case "good": Format.good
        case "warn": Format.warn
        default: .inkSoft
        }
        return Text(badge.text.uppercased())
            .font(AppFont.body(11, weight: .bold))
            .tracking(1.1)
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .frame(height: 24)
            .background(badge.tone == "same" ? Color(hex: 0x1A1E27) : color.opacity(0.12), in: Capsule())
    }
}

private struct Sparkline: View {
    let values: [Double]

    var body: some View {
        Chart {
            ForEach(Array(values.enumerated()), id: \.offset) { index, value in
                LineMark(x: .value("Session", index), y: .value("Value", value))
                    .foregroundStyle(Color.strength)
                    .lineStyle(StrokeStyle(lineWidth: 1.6))
            }
            if let last = values.last {
                PointMark(x: .value("Session", values.count - 1), y: .value("Value", last))
                    .foregroundStyle(Color.strength)
                    .symbolSize(24)
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartYScale(domain: (values.min() ?? 0)...(values.max() ?? 1), range: .plotDimension(padding: 3))
        .chartXScale(range: .plotDimension(padding: 3))
        .accessibilityHidden(true)
    }
}

// MARK: How it felt

struct FeelCard: View {
    let feedback: ActivityFeedback?
    let showNote: Bool
    let onEdit: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Kicker("How it felt")
                Spacer()
                if feedback != nil {
                    Button("Edit", action: onEdit)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .frame(minWidth: 44, minHeight: 32)
                }
            }
            if let feedback {
                HStack(alignment: .top, spacing: 10) {
                    meter("RPE", feedback.rpe, of: 10)
                    meter("Energy", feedback.energy, of: 5)
                    meter("Soreness", feedback.muscleSoreness, of: 5)
                    meter("Pain", feedback.painLevel, of: 10, color: feedback.painLevel.map(Format.painColor))
                }
                if showNote, let note = feedback.note?.nilIfEmpty {
                    Text("“\(note)”").font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                }
            } else {
                Text("Ten seconds now keeps your load and pain trends honest.")
                    .font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                Button("Add how it felt", action: onEdit).buttonStyle(OutlineButtonStyle(height: 44))
            }
        }
        .card()
    }

    private func meter(_ label: String, _ value: Int?, of scale: Int, color: Color? = nil) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            SmallKicker(text: label)
            numberText(value.map(String.init) ?? "–", size: 22, unit: "/\(scale)", unitSize: 11, color: color ?? .ink)
            HStack(spacing: 2) {
                ForEach(0..<scale, id: \.self) { index in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(index < (value ?? 0) ? (color == .mobility ? Color.ink : color ?? .ink) : Color.raised)
                        .frame(height: 4)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label) \(value.map(String.init) ?? "not set") of \(scale)")
    }
}

// MARK: Coach

struct CoachCard: View {
    let state: ActivityDetailFormat.CoachState
    let asking: Bool
    let onAsk: () -> Void
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker("Coach take", color: .volt)
                Spacer()
                switch state {
                case .canAsk(let failed):
                    Text(failed ? "last try failed" : "not requested yet").font(AppFont.body(11)).foregroundStyle(Color.muted)
                default: EmptyView()
                }
            }
            switch state {
            case .take(let take):
                if let headline = take.headline {
                    Text(headline).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink).lineSpacing(2)
                }
                if let body = take.body {
                    Text(body).font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                        .lineLimit(expanded ? nil : 4)
                }
                if !take.observations.isEmpty {
                    Divider().overlay(Color.cardBorder).padding(.top, 4)
                    Button {
                        withAnimation(.snappy) { expanded.toggle() }
                    } label: {
                        HStack {
                            Text(expanded ? "Hide observations" : "\(take.observations.count) observations")
                                .font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.inkSoft)
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Color.muted)
                                .rotationEffect(.degrees(expanded ? 90 : 0))
                        }
                        .frame(minHeight: 32)
                        .contentShape(Rectangle())
                    }
                    if expanded {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(Array(take.observations.enumerated()), id: \.offset) { _, line in
                                HStack(alignment: .top, spacing: 8) {
                                    Circle().fill(Color.volt).frame(width: 5, height: 5).padding(.top, 7)
                                    Text(line).font(AppFont.body(13)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(2)
                                }
                            }
                        }
                    }
                }
            case .pending:
                HStack(spacing: 10) {
                    ProgressView().tint(.muted)
                    Text("Coach is writing… it lands here and on the web page.").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                }
            case .canAsk:
                Text("Ask for a written analysis of this session. It lands here and on the web page.")
                    .font(AppFont.body(14)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(3)
                Button(action: onAsk) {
                    HStack(spacing: 8) {
                        if asking { ProgressView().tint(.ink) }
                        Text("Ask the coach")
                    }
                }
                .buttonStyle(OutlineButtonStyle(height: 44))
                .disabled(asking)
                .padding(.top, 4)
            case .none:
                EmptyView()
            }
        }
        .card(border: Color.volt.opacity(0.25))
    }
}
