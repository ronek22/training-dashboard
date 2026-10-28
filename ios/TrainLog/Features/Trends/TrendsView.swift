import Charts
import SwiftUI

/// Pushed from the Activities header.
struct TrendsRoute: Hashable {}

struct TrendsView: View {
    @State private var model = TrendsModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if model.offline, let syncedAt = model.syncedAt {
                    Text("Offline · showing \(syncedAt.formatted(date: .abbreviated, time: .shortened)) data")
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                }
                if !model.loaded {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                } else if model.years.isEmpty && model.metrics.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not loaded")
                        Text(model.error ?? "No data on the server yet.").font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                }
                if !model.years.isEmpty {
                    sectionTitle("Your \(String(Calendar.current.component(.year, from: .now))) so far",
                                 "Monthly volume as bars, the running total as a line.")
                    ForEach(model.years) { YearCard(year: $0) }
                }
                if !model.metrics.isEmpty {
                    HStack(alignment: .bottom) {
                        sectionTitle("Recovery", healthSubtitle)
                        Spacer()
                        rangePicker
                    }
                    .padding(.top, 12)
                    ForEach(model.metrics) { HealthCard(trend: $0) }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
        .task { await model.load() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(TrendsFormat.dayOfYear())
            Text("TRENDS").font(AppFont.title(44)).foregroundStyle(Color.ink)
        }
        .padding(.horizontal, 4)
    }

    private func sectionTitle(_ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title.uppercased()).font(AppFont.title(26)).foregroundStyle(Color.ink)
            Text(subtitle).font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .padding(.horizontal, 4)
        .padding(.top, 4)
    }

    private var healthSubtitle: String {
        guard let exported = model.health?.lastImport?.exportDate.flatMap({ FoodFormat.parse(String($0.prefix(10))) }) else {
            return "From Apple Health."
        }
        return "Apple Health · export \(exported.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB"))))"
    }

    private var rangePicker: some View {
        HStack(spacing: 4) {
            ForEach([30, 90], id: \.self) { days in
                let selected = model.range == days
                Button("\(days)D") { model.range = days }
                    .font(AppFont.body(12, weight: .semibold))
                    .foregroundStyle(selected ? Color.bg : Color.inkSoft)
                    .frame(width: 44, height: 30)
                    .background(selected ? Color.ink : .clear, in: Capsule())
                    .overlay(Capsule().strokeBorder(selected ? .clear : Color.outline))
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
            }
        }
    }
}

/// Bars for each month, the cumulative total as a line over them; tap a month for its numbers.
private struct YearCard: View {
    let year: SportYear
    @State private var selection: String?

    private var color: Color { year.sport.color }
    private var selected: SportYear.Month? {
        selection.flatMap { name in year.months.first { $0.name == name } }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(color)
                    .frame(width: 40, height: 40)
                    .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Kicker(year.title, color: color)
                    Text(year.caption).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(TrendsFormat.total(year.total)).font(AppFont.title(56)).foregroundStyle(Color.ink)
                Text(year.unit).font(AppFont.body(16)).foregroundStyle(Color.muted)
            }
            chart.frame(height: 150)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            footer
        }
        .card()
        .sensoryFeedback(.selection, trigger: selection)
    }

    private var icon: String {
        switch year.sport {
        case .ride: "bicycle"
        case .run: "figure.run"
        default: "dumbbell.fill"
        }
    }

    // Bars and line share one 0…1 scale: bars fill the lower 60 %, the running total ends near the top.
    private func barHeight(_ month: SportYear.Month) -> Double {
        year.maxMonthly > 0 ? month.value / year.maxMonthly * 0.6 : 0
    }

    private func lineHeight(_ month: SportYear.Month) -> Double {
        year.total > 0 ? month.cumulative / year.total * 0.92 + 0.03 : 0.03
    }

    private var labelled: Set<Int> {
        Set([year.best?.index, year.current?.index, selected?.index].compactMap { $0 })
    }

    private var chart: some View {
        Chart {
            ForEach(year.months) { month in
                BarMark(x: .value("Month", month.name), y: .value("Volume", barHeight(month)), width: .ratio(0.6))
                    .foregroundStyle(color.opacity(highlighted(month) ? 1 : 0.42))
                    .cornerRadius(3)
                    .annotation(position: .top, spacing: 3) {
                        if labelled.contains(month.index), month.value > 0 {
                            Text(year.unit == "h" ? month.value.formatted(ActivityFormat.oneDecimal) : "\(Int(month.value.rounded()))")
                                .font(AppFont.number(11, weight: .semibold))
                                .foregroundStyle(Color.inkSoft)
                        }
                    }
                LineMark(x: .value("Month", month.name), y: .value("Total", lineHeight(month)))
                    .foregroundStyle(color)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .interpolationMethod(.monotone)
            }
            if let marker = selected ?? year.current {
                if selected != nil {
                    RuleMark(x: .value("Month", marker.name))
                        .foregroundStyle(color.opacity(0.6))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 3]))
                }
                PointMark(x: .value("Month", marker.name), y: .value("Total", lineHeight(marker)))
                    .symbol {
                        Circle().fill(Color.bg).stroke(color, lineWidth: 2.5).frame(width: 10, height: 10)
                    }
            }
        }
        .chartXScale(domain: TrendsFormat.monthNames)
        .chartYScale(domain: 0...1.05)
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: TrendsFormat.monthNames) { value in
                AxisValueLabel {
                    if let name = value.as(String.self) {
                        let past = year.months.contains { $0.name == name }
                        Text(String(name.prefix(1)))
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(past ? Color.muted : Color.dim)
                    }
                }
            }
        }
        // A tap keeps the month (the built-in selection clears on lift); tap it again to clear.
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle().fill(.clear).contentShape(Rectangle())
                    .onTapGesture { location in
                        let x = location.x - (proxy.plotFrame.map { geometry[$0].origin.x } ?? 0)
                        guard let name: String = proxy.value(atX: x), year.months.contains(where: { $0.name == name }) else { return }
                        selection = selection == name ? nil : name
                    }
            }
        }
    }

    private func highlighted(_ month: SportYear.Month) -> Bool {
        if let selected { return selected.index == month.index }
        return month.index == year.current?.index
    }

    @ViewBuilder
    private var footer: some View {
        if let month = selected {
            HStack(alignment: .top) {
                stat("Month", month.name)
                if year.unit == "km" {
                    stat("Distance", TrendsFormat.monthValue(month.value, unit: "km"))
                }
                stat("Time", TrendsFormat.monthValue(month.hours, unit: "h"))
                if year.unit == "h" {
                    stat("Sessions", "\(month.sessions)")
                }
                stat("Year total", TrendsFormat.monthValue(month.cumulative, unit: year.unit))
            }
        } else {
            HStack(alignment: .top) {
                if let current = year.current {
                    stat("\(current.name) so far", TrendsFormat.monthValue(current.value, unit: year.unit))
                }
                if let best = year.best {
                    stat("Best month", "\(best.name) · \(TrendsFormat.monthValue(best.value, unit: year.unit))")
                }
            }
        }
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
            Text(value).font(AppFont.number(20)).foregroundStyle(Color.ink).lineLimit(1).minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// One Apple Health metric: the latest reading, last week against the month before, and the range as a chart.
private struct HealthCard: View {
    let trend: HealthTrend

    private var color: Color {
        switch trend.kind {
        case .sleep: .other
        case .hrv: .mobility
        case .restingHr: .danger
        case .steps: .warning
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Kicker(trend.kind.title, color: color)
                    if let latest = trend.latest {
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            Text(TrendsFormat.health(latest.value, trend.kind)).font(AppFont.title(38)).foregroundStyle(Color.ink)
                            if trend.kind != .sleep, !trend.kind.unit.isEmpty {
                                Text(trend.kind.unit).font(AppFont.body(14)).foregroundStyle(Color.muted)
                            }
                        }
                        Text(subtitle(latest)).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
                Spacer(minLength: 8)
                if let delta = TrendsFormat.delta(trend) {
                    Pill(text: delta.text, color: delta.good.map { $0 ? Color.mobility : Color.danger } ?? .muted)
                }
            }
            chart.frame(height: 110)
        }
        .card()
    }

    private func subtitle(_ latest: HealthTrend.Day) -> String {
        let day = latest.date.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated).locale(Locale(identifier: "en_GB")))
        guard let average = trend.weekAverage else { return day }
        return "\(day) · 7-day avg \(TrendsFormat.health(average, trend.kind))"
    }

    private var chart: some View {
        Chart {
            if let baseline = trend.baseline {
                RuleMark(y: .value("30-day", baseline))
                    .foregroundStyle(Color.faint)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
            }
            ForEach(trend.days) { day in
                switch trend.kind {
                case .sleep:
                    if let stages = day.stages {
                        stageBar(day, "Deep", stages.deep, opacity: 1)
                        stageBar(day, "REM", stages.rem, opacity: 0.65)
                        stageBar(day, "Core", stages.core, opacity: 0.35)
                    } else {
                        BarMark(x: .value("Day", day.date, unit: .day), y: .value("Hours", day.value))
                            .foregroundStyle(color.opacity(0.6))
                    }
                case .steps:
                    BarMark(x: .value("Day", day.date, unit: .day), y: .value("Steps", day.value))
                        .foregroundStyle(color.opacity(day == trend.latest ? 1 : 0.5))
                        .cornerRadius(2)
                case .hrv, .restingHr:
                    LineMark(x: .value("Day", day.date, unit: .day), y: .value(trend.kind.title, day.value))
                        .foregroundStyle(color)
                        .lineStyle(StrokeStyle(lineWidth: 2, lineCap: .round))
                        .interpolationMethod(.monotone)
                    PointMark(x: .value("Day", day.date, unit: .day), y: .value(trend.kind.title, day.value))
                        .foregroundStyle(color)
                        .symbolSize(day == trend.latest ? 40 : 10)
                }
            }
        }
        .chartYScale(domain: yDomain)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel(axisLabel(value.as(Double.self) ?? 0))
                    .font(AppFont.body(10))
                    .foregroundStyle(Color.faint)
            }
        }
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisValueLabel(format: .dateTime.day().month(.abbreviated)).font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
    }

    /// "40k" rather than a locale's "40.000".
    private func axisLabel(_ number: Double) -> String {
        number >= 1000 ? "\(Int(number / 1000))k" : "\(Int(number.rounded()))"
    }

    /// Bars start at zero; HRV and resting HR hug their range so a few beats show.
    private var yDomain: ClosedRange<Double> {
        let values = trend.days.map(\.value)
        guard let low = values.min(), let high = values.max() else { return 0...1 }
        if trend.kind == .sleep || trend.kind == .steps { return 0...high * 1.08 }
        let pad = max((high - low) * 0.15, 2)
        return (low - pad)...(high + pad)
    }

    private func stageBar(_ day: HealthTrend.Day, _ stage: String, _ hours: Double?, opacity: Double) -> some ChartContent {
        BarMark(x: .value("Day", day.date, unit: .day), y: .value("Hours", hours ?? 0))
            .foregroundStyle(color.opacity(opacity))
    }
}
