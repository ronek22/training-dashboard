import SwiftUI

// Depth one tap away: every "Show more" opens a sheet with the big chart (scrub), the full zones
// table and the explanation lines (artboard frame "D2 · Show more sheet").

extension ActivityDetailFormat {
    struct SheetStat: Equatable {
        let label: String
        let value: String
        let unit: String
        let color: Color
    }

    /// The 2×2 numbers at the top of a metric sheet.
    static func sheetStats(_ detail: ActivityDetail, key: String) -> [SheetStat] {
        switch key {
        case "heartrate":
            var stats: [SheetStat] = []
            if let avg = number(detail, "avg_hr") { stats.append(.init(label: "Average", value: "\(Int(avg.rounded()))", unit: "bpm", color: Metric.heartRate.color)) }
            if let max = number(detail, "max_hr") { stats.append(.init(label: "Maximum", value: "\(Int(max.rounded()))", unit: "bpm", color: Metric.heartRate.color)) }
            if let drift = drift(detail)?.pct { stats.append(.init(label: "Drift", value: String(format: "%.1f", drift), unit: "%", color: .ink)) }
            if let load = detail.cycling?.hrLoad {
                stats.append(.init(label: "Load", value: "\(Int(load.rounded()))", unit: signal(detail, "load")?.detail?.components(separatedBy: " ").first ?? "", color: .ink))
            }
            return stats
        case "watts":
            let power = detail.cycling?.power
            return [
                (power?.avgWatts ?? number(detail, "avg_watts")).map { SheetStat(label: "Average", value: "\(Int($0.rounded()))", unit: "W", color: Metric.power.color) },
                power?.normalizedWatts.map { SheetStat(label: "Normalized", value: "\(Int($0.rounded()))", unit: "W", color: Metric.power.color) },
                power?.intensityFactor.map { SheetStat(label: "Intensity", value: String(format: "%.2f", $0), unit: "IF", color: .ink) },
                power?.workKj.map { SheetStat(label: "Work", value: "\(Int($0.rounded()))", unit: "kJ", color: .ink) },
            ].compactMap { $0 }
        case "pace":
            let best = detail.bestEfforts?.efforts.first { $0.label == "1K" }
            return [
                avgPaceText(detail).map { SheetStat(label: "Average", value: $0, unit: "/km", color: Metric.pace.color) },
                best?.metricValue.map { SheetStat(label: "Best km", value: paceText($0 * 60), unit: "/km", color: Metric.pace.color) },
                number(detail, "distance_km").map { SheetStat(label: "Distance", value: $0.formatted(ActivityFormat.twoDecimals), unit: "km", color: Metric.distance.color) },
                number(detail, "elevation_m").map { SheetStat(label: "Climb", value: "\(Int($0.rounded()))", unit: "m", color: Metric.elevation.color) },
            ].compactMap { $0 }
        default:
            guard let values = chart(detail, key)?.values.filter({ $0 > 0 || key == "altitude" }), let lo = values.min(), let hi = values.max() else { return [] }
            let avg = values.reduce(0, +) / Double(values.count)
            let color = chipColor(key)
            let unit = chart(detail, key)?.unit ?? ""
            let text = { (v: Double) in key == "speed" ? v.formatted(ActivityFormat.oneDecimal) : "\(Int(v.rounded()))" }
            return [SheetStat(label: key == "altitude" ? "Top" : "Maximum", value: text(hi), unit: unit, color: color),
                    SheetStat(label: key == "altitude" ? "Lowest" : "Average", value: text(key == "altitude" ? lo : avg), unit: unit, color: color)]
        }
    }

    /// First half vs second half: heart rate and power, from the workout match or the ride's decoupling.
    static func drift(_ detail: ActivityDetail) -> (pct: Double, text: String?)? {
        if let drift = detail.workoutExecution?.drift, let pct = drift.decouplingPct {
            var text: String?
            if let a = drift.firstHr, let b = drift.secondHr, let w1 = drift.firstWatts, let w2 = drift.secondWatts {
                text = "Drift \(String(format: "%.1f", pct))%: \(Int(a)) → \(Int(b)) bpm while power \(w2 < w1 ? "fell" : "rose") \(Int(w1)) → \(Int(w2)) W"
            }
            return (pct, text)
        }
        if let decoupling = detail.cycling?.decoupling, decoupling.available == true, let pct = decoupling.decouplingPct {
            return (pct, "Drift \(String(format: "%.1f", pct))% from the first half to the second")
        }
        return nil
    }

    /// What a metric sheet can stack under its chart, best first: heart rate next to anything else,
    /// and for heart rate itself, what drove it (power, then pace, then speed).
    static func compareKeys(_ detail: ActivityDetail, key: String) -> [String] {
        let preferred = ["heartrate", "watts", "pace", "speed", "altitude", "cadence"]
        return preferred.filter { $0 != key && usable(detail, $0) != nil }
    }

    /// "Zones: < 140 · 140–152 · …".
    static func zoneRangesLine(_ zones: ActivityDetail.Zones?, unit: String) -> String? {
        let ranges = (zones?.zones ?? []).compactMap { $0.range?.replacingOccurrences(of: " \(unit)", with: "").replacingOccurrences(of: "-", with: "–").replacingOccurrences(of: ">=", with: "≥") }
        return ranges.isEmpty ? nil : "Zones: " + ranges.joined(separator: " · ") + " \(unit)"
    }
}

struct MetricSheet: View {
    let detail: ActivityDetail
    let key: String
    /// The chart stacked under the main one; nil until picked, "" for none.
    @State private var compare: String?
    @State private var scrub: Double?
    @Environment(\.dismiss) private var dismiss

    private var chartKey: String { key }
    private var options: [String] { ActivityDetailFormat.compareKeys(detail, key: key) }
    private var compareKey: String? {
        guard let compare else { return options.first }
        return compare.isEmpty ? nil : compare
    }

    private var subtitle: String {
        let place = ActivityDetailFormat.isIndoorRide(detail) ? ActivityDetailFormat.platform(detail.activity) : nil
        return [place ?? detail.activity.title, ActivityFormat.longDay(detail.activity.date)].joined(separator: " · ")
    }

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                VStack(spacing: 2) {
                    Text(ActivityDetailFormat.chipTitle(key)).font(AppFont.body(17, weight: .semibold)).foregroundStyle(Color.ink)
                    Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(1)
                }
                .padding(.horizontal, 72)
                HStack {
                    Spacer()
                    Button("Done") { dismiss() }
                        .font(AppFont.body(16, weight: .semibold))
                        .foregroundStyle(Color(hex: 0x6FAEFF))
                        .frame(minWidth: 44, minHeight: 44)
                }
                .padding(.horizontal, 16)
            }
            .padding(.top, 20)
            .padding(.bottom, 12)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    stats
                    if let model = ActivityDetailFormat.chartModel(detail, key: chartKey) {
                        MetricChart(model: model, height: 180, scrub: $scrub) { x in scrubText(x, model: model) }
                            .padding(.top, 48)
                        if !options.isEmpty { comparePicker.padding(.top, 20) }
                        if let compareKey, let second = stacked(compareKey, under: model) {
                            HStack(spacing: 6) {
                                Circle().fill(second.color).frame(width: 8, height: 8)
                                Text(second.title).font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.inkSoft)
                                Spacer()
                                if let average = second.averageLabel { Text("avg \(average)").font(AppFont.body(12)).foregroundStyle(Color.muted) }
                            }
                            .padding(.top, 20)
                            MetricChart(model: second, height: 120, scrub: $scrub, showsScrubPill: false)
                                .padding(.top, 10)
                        }
                    }
                    zones
                    lines
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 32)
            }
            .scrollIndicators(.hidden)
        }
        .background(Color.card)
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.card)
    }

    private var stats: some View {
        let stats = ActivityDetailFormat.sheetStats(detail, key: key)
        return LazyVGrid(columns: [GridItem(.flexible(), spacing: 16, alignment: .leading), GridItem(.flexible(), alignment: .leading)], spacing: 0) {
            ForEach(Array(stats.enumerated()), id: \.offset) { index, stat in
                VStack(alignment: .leading, spacing: 6) {
                    Text(stat.label).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    MetricValue(parts: [(stat.value, stat.unit)], size: 34, color: stat.color, unitUppercase: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 14)
                .overlay(alignment: .top) { if index >= 2 { Rectangle().fill(Color.cardBorder).frame(height: 1) } }
            }
        }
        .padding(.top, 8)
    }

    /// The second chart, on the same time (or distance) axis as the first.
    private func stacked(_ key: String, under model: MetricChartModel) -> MetricChartModel? {
        guard var second = ActivityDetailFormat.chartModel(detail, key: key) else { return nil }
        second.xDomain = model.xDomain
        second.xTicks = model.xTicks
        return second
    }

    /// "Compare with" chips; tapping the selected one again hides the second chart.
    private var comparePicker: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 6) {
                Text("Compare with").font(AppFont.body(12)).foregroundStyle(Color.muted).padding(.trailing, 4)
                ForEach(options, id: \.self) { option in
                    let on = option == compareKey
                    Button {
                        withAnimation(.snappy) { compare = on ? "" : option }
                    } label: {
                        HStack(spacing: 5) {
                            Circle().fill(ActivityDetailFormat.chipColor(option)).frame(width: 8, height: 8)
                            Text(ActivityDetailFormat.chipTitle(option))
                        }
                        .font(AppFont.body(12, weight: .semibold))
                        .foregroundStyle(on ? Color.ink : Color.inkSoft)
                        .padding(.horizontal, 10)
                        .frame(height: 32)
                        .background(on ? Color.raised : Color(hex: 0x1A1E27), in: Capsule())
                        .frame(minHeight: 44)
                        .contentShape(Rectangle())
                    }
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
        .scrollIndicators(.hidden)
    }

    /// One pill for both charts: "18:20 · 151 bpm · 146 W".
    private func scrubText(_ x: Double, model: MetricChartModel) -> String {
        var parts = [ActivityDetailFormat.chartsByDistance(detail) ? "\(x.formatted(ActivityFormat.upToOneDecimal)) km" : ActivityFormat.clock(x)]
        if let point = model.nearest(x) { parts.append(ActivityDetailFormat.scrubValue(chartKey, point.y)) }
        if let compareKey, let second = ActivityDetailFormat.chartModel(detail, key: compareKey)?.nearest(x) {
            parts.append(ActivityDetailFormat.scrubValue(compareKey, second.y))
        }
        return parts.joined(separator: " · ")
    }

    @ViewBuilder
    private var zones: some View {
        let power = key == "watts"
        let rows = ActivityDetailFormat.zoneRows(power ? detail.powerZones : detail.heartRateZones, full: true)
        if !rows.isEmpty {
            HStack {
                Text("Zones").font(AppFont.number(22)).foregroundStyle(Color.ink)
                Spacer()
                Text(power ? "FTP-based · \(rows.count) zones" : "\(rows.count) zones").font(AppFont.number(13, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .padding(.top, 32)
            ZoneBars(rows: rows, trackColor: Color(hex: 0x1A1E27)).padding(.top, 16)
        }
    }

    @ViewBuilder
    private var lines: some View {
        let items: [(StatusTone, String)] = {
            var items: [(StatusTone, String)] = []
            if key == "heartrate" {
                if let ranges = ActivityDetailFormat.zoneRangesLine(detail.heartRateZones, unit: "bpm") { items.append((.info, ranges)) }
                if let drift = ActivityDetailFormat.drift(detail), let text = drift.text { items.append((drift.pct > 5 ? .warn : .good, text)) }
            } else if key == "watts", let ftp = detail.cycling?.ftpWatts {
                items.append((.info, "Zones from your \(Int(ftp.rounded())) W FTP"))
            }
            return items
        }()
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in StatusLine(tone: item.0, text: item.1) }
            }
            .padding(.top, 20)
        }
    }
}

struct CoachSheet: View {
    let take: ActivityDetailFormat.CoachTake
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Spacer()
                Text("Coach take").font(AppFont.body(17, weight: .semibold)).foregroundStyle(Color.ink)
                Spacer()
            }
            .overlay(alignment: .trailing) {
                Button("Done") { dismiss() }.font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color(hex: 0x6FAEFF))
                    .frame(minWidth: 44, minHeight: 44)
            }
            .padding(.horizontal, 16)
            .padding(.top, 20)
            .padding(.bottom, 12)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let headline = take.headline {
                        Text(headline).font(AppFont.body(18, weight: .semibold)).foregroundStyle(Color.ink).lineSpacing(3)
                    }
                    if let body = take.body {
                        Text(body).font(AppFont.body(15)).foregroundStyle(Color(hex: 0xC9CFDA)).lineSpacing(5)
                    }
                    if !take.observations.isEmpty {
                        Text("Observations").font(AppFont.number(22)).foregroundStyle(Color.ink).padding(.top, 12)
                        ForEach(Array(take.observations.enumerated()), id: \.offset) { _, line in
                            StatusLine(tone: .info, text: line, size: 14, color: Color(hex: 0xC9CFDA))
                        }
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.card)
    }
}
