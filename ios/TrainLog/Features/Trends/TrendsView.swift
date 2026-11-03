import Charts
import SwiftUI

/// Pushed from the Activities header.
struct TrendsRoute: Hashable {}

struct TrendsView: View {
    @State private var model = TrendsModel()

    private var year: Int { Calendar.current.component(.year, from: .now) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if model.offline, let syncedAt = model.syncedAt {
                    OfflineNote(syncedAt: syncedAt)
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
                if let weekly = model.weekly {
                    WeeklyCard(volume: weekly)
                }
                if !model.yearRows.isEmpty {
                    sectionTitle("\(String(year)) so far",
                                 model.trends == nil ? "Tap a sport for its months." : "Against this date last year. Tap a sport for months.")
                    YearCard(rows: model.yearRows, lastYear: year - 1)
                }
                if !model.metrics.isEmpty {
                    HStack(alignment: .bottom) {
                        sectionTitle("Recovery", healthSubtitle)
                        Spacer()
                        rangePicker
                    }
                    recovery
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .smoothRefreshable {
            await APIClient.current.reconnect()
            await model.load()
        }
        .task { await model.load() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(TrendsFormat.dayOfYear())
            Text("TRENDS").font(AppFont.title(44)).foregroundStyle(Color.ink)
            if let line = model.weekly.flatMap(TrendsFormat.headline) {
                Text(line)
                    .font(AppFont.body(14))
                    .foregroundStyle(Color.inkSoft)
                    .lineSpacing(2)
                    .padding(.top, 4)
            }
        }
        .padding(.horizontal, 4)
    }

    private func sectionTitle(_ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title.uppercased()).font(AppFont.title(26)).foregroundStyle(Color.ink)
            Text(subtitle).font(AppFont.body(13)).foregroundStyle(Color.muted)
        }
        .padding(.horizontal, 4)
        .padding(.top, 14)
    }

    private var healthSubtitle: String {
        guard let exported = model.health?.lastImport?.exportDate.flatMap({ FoodFormat.parse(String($0.prefix(10))) }) else {
            return "Apple Health · line = 7-day average"
        }
        return "Apple Health · \(exported.formatted(.dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB")))) · line = 7-day avg"
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

    /// Sleep full width, HRV and resting HR side by side, steps as a slim strip.
    @ViewBuilder
    private var recovery: some View {
        let metrics = Dictionary(model.metrics.map { ($0.kind, $0) }, uniquingKeysWith: { first, _ in first })
        if let sleep = metrics[.sleep] { SleepCard(trend: sleep) }
        let pair = [metrics[.hrv], metrics[.restingHr]].compactMap { $0 }
        if !pair.isEmpty {
            HStack(alignment: .top, spacing: 10) {
                ForEach(pair) { CompactHealthCard(trend: $0) }
            }
        }
        if let steps = metrics[.steps] { StepsCard(trend: steps) }
    }
}

// MARK: - Year card

/// One row per sport: the total so far, how it compares with last year, a sparkline of the months.
private struct YearCard: View {
    let rows: [SportYearRow]
    let lastYear: Int

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                if index > 0 { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                if let year = row.year {
                    NavigationLink {
                        SportYearView(row: row, year: year, lastYear: lastYear).hidesTabBar()
                    } label: {
                        content(row, chevron: true)
                    }
                    .buttonStyle(.plain)
                } else {
                    content(row, chevron: false)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private func content(_ row: SportYearRow, chevron: Bool) -> some View {
        let color = row.sport.color
        return HStack(alignment: .center, spacing: 12) {
            Image(systemName: row.sport.symbol)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(color)
                .frame(width: 40, height: 40)
                .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
                .frame(maxHeight: .infinity, alignment: .top)
            VStack(alignment: .leading, spacing: 5) {
                Kicker(row.title, color: color)
                HStack(alignment: .firstTextBaseline, spacing: 5) {
                    Text(TrendsFormat.total(row.total)).font(AppFont.number(30)).foregroundStyle(Color.ink)
                    Text(row.unit).font(AppFont.body(13)).foregroundStyle(Color.muted)
                }
                if let comparison = TrendsFormat.comparison(row, year: lastYear) {
                    if comparison.pill {
                        Pill(text: comparison.text, color: .mobility)
                    } else {
                        Text(comparison.text).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
                if let idle = TrendsFormat.idleNote(row) {
                    Text(idle).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
            }
            Spacer(minLength: 8)
            if let year = row.year { Sparkline(year: year) }
            if chevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color.dim)
            }
        }
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }
}

/// This year's months as small bars, the latest one bright.
private struct Sparkline: View {
    let year: SportYear

    var body: some View {
        let peak = max(year.maxMonthly, 0.001)
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(year.months) { month in
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(year.sport.color.opacity(month.index == year.shown?.index ? 1 : 0.55))
                    .frame(width: 6, height: max(month.value / peak * 30, 1.5))
            }
        }
        .frame(height: 30, alignment: .bottom)
    }
}

// MARK: - Recovery

private func deltaPill(_ trend: HealthTrend) -> Pill? {
    TrendsFormat.delta(trend).map { Pill(text: $0.text, color: $0.good.map { $0 ? Color.mobility : Color.danger } ?? .muted) }
}

private func dayLabel(_ date: Date) -> String {
    date.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated).locale(Locale(identifier: "en_GB")))
}

/// Sleep stages per night with the 7-day average over them.
private struct SleepCard: View {
    let trend: HealthTrend
    private let color = Color.other

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Kicker("Sleep · last night", color: color)
                    if let latest = trend.latest {
                        Text(TrendsFormat.health(latest.value, .sleep)).font(AppFont.title(38)).foregroundStyle(Color.ink)
                        Text(subtitle(latest)).font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
                Spacer(minLength: 8)
                deltaPill(trend)
            }
            chart.frame(height: 100)
            if let stages = trend.latest?.stages {
                HStack(spacing: 14) {
                    stage("Deep", stages.deep, opacity: 1)
                    stage("REM", stages.rem, opacity: 0.65)
                    stage("Core", stages.core, opacity: 0.35)
                }
            }
        }
        .card()
    }

    private func subtitle(_ latest: HealthTrend.Day) -> String {
        guard let average = trend.weekAverage else { return dayLabel(latest.date) }
        return "\(dayLabel(latest.date)) · 7-day avg \(TrendsFormat.health(average, .sleep))"
    }

    private func stage(_ name: String, _ hours: Double?, opacity: Double) -> some View {
        HStack(spacing: 5) {
            RoundedRectangle(cornerRadius: 3).fill(color.opacity(opacity)).frame(width: 10, height: 10)
            Text(name).font(AppFont.body(11)).foregroundStyle(Color.inkSoft)
            Text(TrendsFormat.hours(hours ?? 0)).font(AppFont.number(13)).foregroundStyle(Color.ink)
        }
    }

    private var chart: some View {
        Chart {
            if let baseline = trend.baseline {
                RuleMark(y: .value("30-day", baseline))
                    .foregroundStyle(Color.inkSoft.opacity(0.5))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
            }
            ForEach(trend.days) { day in
                if let stages = day.stages {
                    stageBar(day, stages.deep, opacity: 1)
                    stageBar(day, stages.rem, opacity: 0.65)
                    stageBar(day, stages.core, opacity: 0.35)
                } else {
                    BarMark(x: .value("Day", day.date, unit: .day), y: .value("Hours", day.value))
                        .foregroundStyle(color.opacity(0.45))
                }
            }
            ForEach(trend.average) { day in
                LineMark(x: .value("Day", day.date, unit: .day), y: .value("Average", day.value), series: .value("Series", "avg"))
                    .foregroundStyle(Color.ink)
                    .lineStyle(StrokeStyle(lineWidth: 2.2, lineCap: .round, lineJoin: .round))
                    .interpolationMethod(.monotone)
            }
        }
        .chartYScale(domain: 0...max((trend.days.map(\.value).max() ?? 8) * 1.08, 1))
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel("\(Int((value.as(Double.self) ?? 0).rounded()))")
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

    private func stageBar(_ day: HealthTrend.Day, _ hours: Double?, opacity: Double) -> some ChartContent {
        BarMark(x: .value("Day", day.date, unit: .day), y: .value("Hours", hours ?? 0))
            .foregroundStyle(color.opacity(opacity))
    }
}

/// HRV or resting HR at half width: the 7-day average as the number and the line, nights as dots.
private struct CompactHealthCard: View {
    let trend: HealthTrend

    /// Resting HR stays neutral: only the pill says whether a change is good or bad.
    private var color: Color { trend.kind == .hrv ? .mobility : .inkSoft }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker(trend.kind.title, color: color)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(trend.weekAverage.map { TrendsFormat.health($0, trend.kind) } ?? "—")
                    .font(AppFont.title(32))
                    .foregroundStyle(Color.ink)
                Text("\(trend.kind.unit) avg").font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            .padding(.top, 5)
            if let latest = trend.latest {
                Text("last night \(TrendsFormat.health(latest.value, trend.kind))")
                    .font(AppFont.body(11))
                    .foregroundStyle(Color.muted)
                    .padding(.top, 2)
            }
            deltaPill(trend)?
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .padding(.top, 8)
            chart.frame(height: 64).padding(.top, 10)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Radius.card, style: .continuous).strokeBorder(Color.cardBorder))
    }

    private var chart: some View {
        Chart {
            if let baseline = trend.baseline {
                RuleMark(y: .value("30-day", baseline))
                    .foregroundStyle(Color.inkSoft.opacity(0.5))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
            }
            ForEach(trend.days) { day in
                PointMark(x: .value("Day", day.date, unit: .day), y: .value(trend.kind.title, day.value))
                    .foregroundStyle(color.opacity(0.35))
                    .symbolSize(10)
            }
            ForEach(trend.average) { day in
                LineMark(x: .value("Day", day.date, unit: .day), y: .value("Average", day.value))
                    .foregroundStyle(color)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    .interpolationMethod(.monotone)
            }
            if let last = trend.average.last {
                PointMark(x: .value("Day", last.date, unit: .day), y: .value("Average", last.value))
                    .symbol {
                        Circle().fill(Color.card).stroke(color, lineWidth: 2.2).frame(width: 9, height: 9)
                    }
            }
        }
        .chartYScale(domain: yDomain)
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
    }

    /// Hugs the range so a few beats or milliseconds show.
    private var yDomain: ClosedRange<Double> {
        let values = trend.days.map(\.value)
        guard let low = values.min(), let high = values.max() else { return 0...1 }
        let pad = max((high - low) * 0.12, 2)
        return (low - pad)...(high + pad)
    }
}

/// Steps per day as a slim strip with a 10k line; the header is this week's daily average.
private struct StepsCard: View {
    let trend: HealthTrend
    private let color = Color.warning

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Kicker("Steps", color: color)
                    Text(trend.weekAverage.map { TrendsFormat.health($0, .steps) } ?? "—")
                        .font(AppFont.number(22))
                        .foregroundStyle(Color.ink)
                    Text("/ day this week").font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                .lineLimit(1)
                .minimumScaleFactor(0.85)
                Spacer(minLength: 8)
                deltaPill(trend)
            }
            chart.frame(height: 40)
        }
        .card()
    }

    private var chart: some View {
        Chart {
            RuleMark(y: .value("Goal", 10_000))
                .foregroundStyle(Color.inkSoft.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
            ForEach(trend.days) { day in
                BarMark(x: .value("Day", day.date, unit: .day), y: .value("Steps", min(day.value, 20_000)))
                    .foregroundStyle(color.opacity(day == trend.latest ? 1 : 0.45))
                    .cornerRadius(1.5)
            }
        }
        .chartYScale(domain: 0...20_000)
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
    }
}
