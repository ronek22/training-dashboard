import Charts
import SwiftUI

struct BodyView: View {
    @State private var model = BodyModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                if let data = model.data {
                    if model.offline, let syncedAt = model.syncedAt {
                        Text("Offline · showing \(syncedAt.formatted(date: .abbreviated, time: .shortened)) data")
                            .font(AppFont.body(12, weight: .medium))
                            .foregroundStyle(Color.muted)
                            .padding(.horizontal, 4)
                    }
                    ReadinessHero(readiness: data.readiness)
                    if let sleep = data.sleep {
                        SleepCard(sleep: sleep, today: data.date)
                    }
                    StepsCard(steps: model.steps, baseline: data.vitals.steps?.baseline, hours: model.live?.steps ?? [])
                    HeartCard(vitals: data.vitals, live: model.live)
                    TrainingLoadCard(load: data.load)
                } else if let error = model.error {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not synced yet")
                        Text(error).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 300)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await model.refresh() }
        .task { await model.load() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(model.data.map { TodayFormat.dateKicker($0.date) } ?? " ")
            Text("BODY").font(AppFont.title(44)).foregroundStyle(Color.ink)
        }
        .padding(.horizontal, 4)
    }
}

// MARK: - Readiness

private struct ReadinessHero: View {
    let readiness: PhoneBody.Readiness

    var body: some View {
        let status = TodayFormat.readiness(readiness.level)
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                ZStack {
                    Circle().stroke(status.color.opacity(0.18), lineWidth: 6)
                    Circle()
                        .trim(from: 0, to: progress)
                        .stroke(status.color, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    Image(systemName: icon).font(.system(size: 20, weight: .bold)).foregroundStyle(status.color)
                }
                .frame(width: 58, height: 58)
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Readiness", color: status.color)
                    Text(status.label.uppercased()).font(AppFont.title(30)).foregroundStyle(Color.ink)
                }
            }
            if let advice = readiness.advice {
                Text(advice).font(AppFont.body(13)).foregroundStyle(Color.inkSoft).lineSpacing(2)
            }
            if !readiness.factors.isEmpty {
                VStack(spacing: 0) {
                    ForEach(readiness.factors) { factor in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Circle().fill(BodyFormat.toneColor(factor.tone)).frame(width: 7, height: 7).alignmentGuide(.firstTextBaseline) { $0[.bottom] - 1 }
                            Text(factor.label).font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink)
                                .frame(width: 112, alignment: .leading)
                            Text(factor.detail).font(AppFont.body(12)).foregroundStyle(Color.muted)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .padding(.vertical, 8)
                        if factor != readiness.factors.last {
                            Rectangle().fill(Color.cardBorder).frame(height: 1)
                        }
                    }
                }
                .padding(.horizontal, 12)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
        }
        .card()
    }

    private var progress: Double {
        switch readiness.level {
        case "green": 1
        case "amber": 0.62
        case "red": 0.3
        default: 0
        }
    }

    private var icon: String {
        switch readiness.level {
        case "green": "bolt.fill"
        case "amber": "gauge.with.dots.needle.33percent"
        case "red": "bed.double.fill"
        default: "questionmark"
        }
    }
}

// MARK: - Sleep

private struct SleepCard: View {
    let sleep: PhoneBody.Sleep
    let today: String

    private let laneHeight: CGFloat = 26

    var body: some View {
        let blocks = BodyFormat.blocks(sleep)
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Kicker(sleep.date == today ? "Last night" : "Sleep · \(TodayFormat.shortDay(sleep.date, relativeTo: today))", color: SleepStage.deep.color)
                    Text(BodyFormat.duration(sleep.asleepH)).font(AppFont.title(46)).foregroundStyle(Color.ink)
                    Text(subtitle).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer(minLength: 8)
                if let delta = BodyFormat.sleepDelta(sleep) {
                    Pill(text: delta.text, color: delta.good.map { $0 ? Color.mobility : Color.danger } ?? .muted)
                }
            }
            if !blocks.isEmpty {
                hypnogram(blocks)
            }
            stageBar
            stageLegend
        }
        .card()
    }

    private var subtitle: String {
        var parts = ["\(BodyFormat.clock(sleep.start)) – \(BodyFormat.clock(sleep.end))"]
        if let baseline = sleep.baselineH { parts.append("30-day avg \(BodyFormat.duration(baseline))") }
        return parts.joined(separator: " · ")
    }

    /// Four lanes like Apple Health: awake on top, deep at the bottom, each stretch a rounded block,
    /// with a faint line joining one stage to the next.
    private func hypnogram(_ blocks: [SleepBlock]) -> some View {
        VStack(spacing: 6) {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(SleepStage.allCases) { stage in
                        Text(stage.title)
                            .font(AppFont.body(10, weight: .semibold))
                            .foregroundStyle(stage.color.opacity(0.9))
                            .frame(height: laneHeight)
                    }
                }
                .frame(width: 38, alignment: .leading)
                GeometryReader { geometry in
                    let width = geometry.size.width
                    ZStack(alignment: .topLeading) {
                        ForEach(SleepStage.allCases) { stage in
                            RoundedRectangle(cornerRadius: 4).fill(Color.inset)
                                .frame(height: laneHeight - 6)
                                .offset(y: CGFloat(stage.lane) * laneHeight + 3)
                        }
                        Path { path in
                            for (index, block) in blocks.enumerated() where index > 0 {
                                let previous = blocks[index - 1]
                                let x = block.from * width
                                path.move(to: CGPoint(x: x, y: mid(previous.stage)))
                                path.addLine(to: CGPoint(x: x, y: mid(block.stage)))
                            }
                        }
                        .stroke(Color.faint.opacity(0.5), lineWidth: 1)
                        ForEach(blocks) { block in
                            let blockWidth = max(2, (block.to - block.from) * width)
                            RoundedRectangle(cornerRadius: 3, style: .continuous)
                                .fill(block.stage.color)
                                .frame(width: blockWidth, height: laneHeight - 10)
                                .offset(x: min(block.from * width, width - blockWidth), y: CGFloat(block.stage.lane) * laneHeight + 5)
                        }
                    }
                }
                .frame(height: laneHeight * 4)
            }
            HStack {
                Text(BodyFormat.clock(sleep.start))
                Spacer()
                Text(BodyFormat.clock(sleep.end))
            }
            .font(AppFont.body(10, weight: .medium))
            .foregroundStyle(Color.faint)
            .padding(.leading, 46)
        }
    }

    private func mid(_ stage: SleepStage) -> CGFloat {
        CGFloat(stage.lane) * laneHeight + laneHeight / 2
    }

    private var total: Double {
        SleepStage.allCases.map { BodyFormat.hours($0, sleep.stages) }.reduce(0, +)
    }

    private var stageBar: some View {
        GeometryReader { geometry in
            HStack(spacing: 2) {
                ForEach(SleepStage.allCases.reversed()) { stage in
                    let share = total > 0 ? BodyFormat.hours(stage, sleep.stages) / total : 0
                    if share > 0 {
                        Rectangle().fill(stage.color).frame(width: max(2, share * (geometry.size.width - 6)))
                    }
                }
            }
        }
        .frame(height: 8)
        .clipShape(Capsule())
    }

    private var stageLegend: some View {
        HStack(alignment: .top, spacing: 0) {
            ForEach(SleepStage.allCases.reversed()) { stage in
                let hours = BodyFormat.hours(stage, sleep.stages)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 5) {
                        Circle().fill(stage.color).frame(width: 7, height: 7)
                        Text(stage.title).font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                    }
                    Text(BodyFormat.duration(hours)).font(AppFont.number(19)).foregroundStyle(Color.ink)
                    Text(total > 0 ? "\(Int((hours / total * 100).rounded()))%" : "–")
                        .font(AppFont.body(11)).foregroundStyle(Color.faint)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// MARK: - Steps

private struct StepsCard: View {
    let steps: Double?
    let baseline: Double?
    let hours: [LiveDay.Hour]

    private let color = Color.warning

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 16) {
                ZStack {
                    Circle().stroke(color.opacity(0.16), lineWidth: 9)
                    Circle()
                        .trim(from: 0, to: min(progress, 1))
                        .stroke(color, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    Image(systemName: "figure.walk").font(.system(size: 20, weight: .semibold)).foregroundStyle(color)
                }
                .frame(width: 74, height: 74)
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Steps today", color: color)
                    Text(steps.map(BodyFormat.steps) ?? "–").font(AppFont.title(42)).foregroundStyle(Color.ink)
                    if let baseline {
                        Text(progress >= 1 ? "Past your 30-day average of \(BodyFormat.steps(baseline))" : "\(Int((progress * 100).rounded()))% of your \(BodyFormat.steps(baseline)) daily average")
                            .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
            }
            if !hours.isEmpty {
                chart.frame(height: 80)
            }
        }
        .card()
    }

    private var progress: Double {
        guard let steps, let baseline, baseline > 0 else { return 0 }
        return steps / baseline
    }

    private var chart: some View {
        let start = Calendar.current.startOfDay(for: .now)
        return Chart(hours) { hour in
            BarMark(x: .value("Hour", hour.start, unit: .hour), y: .value("Steps", hour.value))
                .foregroundStyle(color.opacity(hour == hours.last ? 1 : 0.55))
                .cornerRadius(2)
        }
        .chartXScale(domain: start...start.addingTimeInterval(86_400))
        .chartYAxis(.hidden)
        .chartXAxis { hourAxis }
    }
}

/// 00 · 06 · 12 · 18 along the bottom of today's hourly charts.
@AxisContentBuilder
private var hourAxis: some AxisContent {
    AxisMarks(values: .stride(by: .hour, count: 6)) { _ in
        AxisGridLine().foregroundStyle(Color.cardBorder)
        AxisValueLabel(format: .dateTime.hour(.twoDigits(amPM: .omitted)).locale(Locale(identifier: "en_GB")))
            .font(AppFont.body(10))
            .foregroundStyle(Color.faint)
    }
}

// MARK: - Heart

private struct HeartCard: View {
    let vitals: PhoneBody.Vitals
    let live: LiveDay?

    private let color = Color.danger

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Heart", color: color)
                    if let bpm = live?.latestHeartRate {
                        HStack(alignment: .firstTextBaseline, spacing: 5) {
                            Text("\(Int(bpm.rounded()))").font(AppFont.title(42)).foregroundStyle(Color.ink)
                            Text("bpm").font(AppFont.body(14)).foregroundStyle(Color.muted)
                        }
                        if let at = live?.latestHeartRateAt {
                            Text("Latest · \(at.formatted(date: .omitted, time: .shortened))").font(AppFont.body(12)).foregroundStyle(Color.muted)
                        }
                    } else {
                        Text("Resting heart rate and HRV").font(AppFont.body(13)).foregroundStyle(Color.muted)
                    }
                }
                Spacer()
                Image(systemName: "heart.fill")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(color)
                    .frame(width: 40, height: 40)
                    .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            if let heart = live?.heart, !heart.isEmpty {
                chart(heart).frame(height: 96)
            }
            HStack(spacing: 10) {
                vital("Resting HR", vitals.restingHr, unit: "bpm", higherIsBetter: false)
                vital("HRV", vitals.hrv, unit: "ms", higherIsBetter: true)
            }
        }
        .card()
    }

    private func vital(_ label: String, _ vital: PhoneBody.Vital?, unit: String, higherIsBetter: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(vital.map { "\(Int($0.value.rounded()))" } ?? "–").font(AppFont.number(30)).foregroundStyle(Color.ink)
                Text(unit).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            if let vital, let delta = BodyFormat.vitalDelta(vital, higherIsBetter: higherIsBetter, unit: unit) {
                HStack(spacing: 4) {
                    Text(delta.text).font(AppFont.body(11, weight: .semibold))
                        .foregroundStyle(delta.good.map { $0 ? Color.mobility : Color.danger } ?? .muted)
                    Text("vs 30 d").font(AppFont.body(11)).foregroundStyle(Color.faint)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    /// Each hour's lowest to highest heart rate as a capsule.
    private func chart(_ hours: [LiveDay.HeartHour]) -> some View {
        let start = Calendar.current.startOfDay(for: .now)
        let low = hours.map(\.low).min() ?? 40
        let high = hours.map(\.high).max() ?? 160
        return Chart(hours) { hour in
            RectangleMark(
                x: .value("Hour", hour.start, unit: .hour),
                yStart: .value("Low", hour.low),
                yEnd: .value("High", max(hour.high, hour.low + 2)),
                width: .ratio(0.5)
            )
            .foregroundStyle(color.opacity(hour == hours.last ? 1 : 0.6))
            .clipShape(Capsule())
        }
        .chartXScale(domain: start...start.addingTimeInterval(86_400))
        .chartYScale(domain: (low - 8)...(high + 8))
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel("\(Int(value.as(Double.self) ?? 0))").font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
        .chartXAxis { hourAxis }
    }
}

// MARK: - Training load

private struct TrainingLoadCard: View {
    let load: PhoneBody.Load

    private let fitnessColor = Color.ride
    private let fatigueColor = Color.strength

    var body: some View {
        let zone = BodyFormat.formZone(load.form)
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Kicker("Training load")
                Spacer()
                Pill(text: zone.label, color: zone.color)
            }
            HStack(alignment: .top, spacing: 0) {
                number("Fitness", "\(Int(load.fitness.rounded()))", fitnessColor)
                number("Fatigue", "\(Int(load.fatigue.rounded()))", fatigueColor)
                number("Form", BodyFormat.signed(load.form), zone.color)
            }
            chart.frame(height: 130)
            formChart.frame(height: 44)
            Rectangle().fill(Color.cardBorder).frame(height: 1)
            VStack(alignment: .leading, spacing: 4) {
                Text(zone.note).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                Text("Load ratio \(load.ratio.formatted(.number.precision(.fractionLength(2)).locale(Locale(identifier: "en_US")))) · \(load.ratioStatus) · last 42 days")
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
        }
        .card()
    }

    private var days: [(date: Date, day: PhoneBody.LoadDay)] {
        load.chart.compactMap { day in FoodFormat.parse(day.date).map { ($0, day) } }
    }

    private func number(_ label: String, _ value: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 5) {
                Capsule().fill(color).frame(width: 10, height: 3)
                Text(label).font(AppFont.body(12)).foregroundStyle(Color.muted)
            }
            Text(value).font(AppFont.title(36)).foregroundStyle(Color.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Fitness as a filled area, fatigue as a line over it, daily load as faint bars underneath.
    private var chart: some View {
        let days = days
        let top = (days.map { max($0.day.fitness, $0.day.fatigue) }.max() ?? 1) * 1.12
        let maxLoad = days.map(\.day.load).max() ?? 1
        return Chart {
            ForEach(days, id: \.date) { item in
                BarMark(x: .value("Day", item.date, unit: .day), y: .value("Load", maxLoad > 0 ? item.day.load / maxLoad * top * 0.35 : 0))
                    .foregroundStyle(Color.dim.opacity(0.7))
                    .cornerRadius(1)
                AreaMark(x: .value("Day", item.date, unit: .day), y: .value("Fitness", item.day.fitness), series: .value("Series", "Fitness"))
                    .foregroundStyle(fitnessColor.opacity(0.1))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Day", item.date, unit: .day), y: .value("Fitness", item.day.fitness), series: .value("Series", "Fitness"))
                    .foregroundStyle(fitnessColor)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Day", item.date, unit: .day), y: .value("Fatigue", item.day.fatigue), series: .value("Series", "Fatigue"))
                    .foregroundStyle(fatigueColor)
                    .lineStyle(StrokeStyle(lineWidth: 1.8, lineCap: .round))
                    .interpolationMethod(.monotone)
            }
            if let last = days.last {
                PointMark(x: .value("Day", last.date, unit: .day), y: .value("Fitness", last.day.fitness))
                    .symbol { Circle().fill(Color.bg).stroke(fitnessColor, lineWidth: 2.5).frame(width: 9, height: 9) }
                PointMark(x: .value("Day", last.date, unit: .day), y: .value("Fatigue", last.day.fatigue))
                    .symbol { Circle().fill(Color.bg).stroke(fatigueColor, lineWidth: 2).frame(width: 8, height: 8) }
            }
        }
        .chartYScale(domain: 0...max(top, 1))
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine().foregroundStyle(Color.cardBorder)
                AxisValueLabel("\(Int(value.as(Double.self) ?? 0))").font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
        .chartXAxis(.hidden)
    }

    /// Form per day: above zero fresh, below zero carrying fatigue.
    private var formChart: some View {
        let days = days
        let reach = max(days.map { abs($0.day.form) }.max() ?? 10, 10)
        return Chart {
            RuleMark(y: .value("Zero", 0)).foregroundStyle(Color.outline)
            ForEach(days, id: \.date) { item in
                BarMark(x: .value("Day", item.date, unit: .day), y: .value("Form", item.day.form))
                    .foregroundStyle(BodyFormat.formZone(item.day.form).color.opacity(item.date == days.last?.date ? 1 : 0.55))
                    .cornerRadius(1.5)
            }
        }
        .chartYScale(domain: -reach...reach)
        .chartYAxis(.hidden)
        .chartXAxis {
            // First, middle and last day, the ends anchored inward so they don't clip.
            let ticks = days.isEmpty ? [] : [days[0].date, days[days.count / 2].date, days[days.count - 1].date]
            AxisMarks(values: ticks) { value in
                let date = value.as(Date.self)
                AxisValueLabel(
                    format: .dateTime.day().month(.abbreviated).locale(Locale(identifier: "en_GB")),
                    anchor: date == ticks.first ? .topLeading : date == ticks.last ? .topTrailing : .top
                )
                .font(AppFont.body(10)).foregroundStyle(Color.faint)
            }
        }
    }
}
