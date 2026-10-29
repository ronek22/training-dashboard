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
                    if data.vitals.hrv != nil || data.vitals.restingHr != nil || data.vitals.sleep != nil {
                        VitalsCard(vitals: data.vitals, today: data.date)
                    }
                    if let sleep = data.sleep {
                        SleepCard(sleep: sleep, today: data.date)
                    }
                    StepsCard(steps: model.steps, vital: data.vitals.steps, hours: model.live?.steps ?? [], today: data.date)
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
        .smoothRefreshable { await model.refresh() }
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
        let style = ReadinessStyle(level: readiness.level)
        VStack(alignment: .leading, spacing: 16) {
            Kicker("Readiness", color: style.color)
            VStack(alignment: .leading, spacing: 2) {
                Text(style.headline.uppercased())
                    .font(AppFont.title(46))
                    .foregroundStyle(style.color)
                Text(readiness.factors.isEmpty ? style.label : "\(style.label) · \(steady.count) of \(readiness.factors.count) signals steady")
                    .font(AppFont.body(13, weight: .medium))
                    .foregroundStyle(Color.inkSoft)
            }
            if !readiness.factors.isEmpty {
                balance
            }
            if let advice = readiness.advice {
                Text(advice).font(AppFont.body(14)).foregroundStyle(Color.inkSoft).lineSpacing(3)
            }
            if !drivers.isEmpty {
                group("Pulling it down", drivers)
            }
            if !steady.isEmpty {
                group("On your side", steady)
            }
        }
        .card()
    }

    private var drivers: [PhoneBody.Factor] {
        readiness.factors.filter { ($0.points ?? 0) > 0 || Self.tone($0) != "steady" }
            .sorted { ($0.points ?? 0) > ($1.points ?? 0) }
    }

    private var steady: [PhoneBody.Factor] {
        readiness.factors.filter { !drivers.contains($0) }
    }

    /// Every signal as one slice: green steady, amber caution, red risk.
    private var balance: some View {
        let tones = ["steady", "caution", "risk"]
        let sorted = readiness.factors.map { Self.tone($0) }.sorted { tones.firstIndex(of: $0)! < tones.firstIndex(of: $1)! }
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 3) {
                ForEach(sorted.indices, id: \.self) { index in
                    Capsule().fill(BodyFormat.toneColor(sorted[index]))
                }
            }
            .frame(height: 8)
            HStack(spacing: 14) {
                ForEach(tones, id: \.self) { tone in
                    let count = sorted.filter { $0 == tone }.count
                    if count > 0 {
                        HStack(spacing: 5) {
                            Circle().fill(BodyFormat.toneColor(tone)).frame(width: 7, height: 7)
                            Text("\(count) \(tone)").font(AppFont.body(11, weight: .semibold)).foregroundStyle(Color.muted)
                        }
                    }
                }
            }
        }
    }

    /// Neutral and quiet signals count as steady.
    private static func tone(_ factor: PhoneBody.Factor) -> String {
        ["caution", "risk"].contains(factor.tone) ? factor.tone : "steady"
    }

    private func group(_ title: String, _ factors: [PhoneBody.Factor]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(title)
            VStack(spacing: 0) {
                ForEach(factors) { factor in
                    row(factor)
                    if factor != factors.last {
                        Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.leading, 48)
                    }
                }
            }
            .padding(.horizontal, 12)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
    }

    private func row(_ factor: PhoneBody.Factor) -> some View {
        let color = BodyFormat.toneColor(factor.tone)
        return HStack(spacing: 12) {
            SignalChip(key: factor.key, tone: factor.tone, size: 36)
            VStack(alignment: .leading, spacing: 2) {
                Text(factor.label).font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink)
                Text(factor.detail.prefix(1).uppercased() + factor.detail.dropFirst())
                    .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if Self.tone(factor) != "steady" || (factor.points ?? 0) > 0 {
                let points = factor.points ?? 0
                // How hard this signal pulls: one bar per point, up to four.
                HStack(alignment: .bottom, spacing: 3) {
                    ForEach(0..<max(points, 2), id: \.self) { index in
                        Capsule()
                            .fill(index < points ? color : Color.track)
                            .frame(width: 4, height: 8 + CGFloat(index) * 4)
                    }
                }
                .accessibilityLabel("\(points) point\(points == 1 ? "" : "s") against readiness")
            } else {
                Image(systemName: "checkmark")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(color.opacity(0.8))
            }
        }
        .padding(.vertical, 10)
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

// MARK: - Overnight vitals

/// The Watch's Vitals view: a week of each overnight reading against its typical range.
private struct VitalsCard: View {
    let vitals: PhoneBody.Vitals
    let today: String

    var body: some View {
        let rows = self.rows
        let outliers = rows.filter { status($0.kind, $0.vital).isOutlier }.count
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Kicker("Overnight vitals")
                Spacer()
                Pill(text: outliers == 0 ? "All typical" : "\(outliers) outlier\(outliers == 1 ? "" : "s")",
                     color: outliers == 0 ? .mobility : .warning)
            }
            Text("Shaded: your typical range over the last 30 days")
                .font(AppFont.body(11))
                .foregroundStyle(Color.faint)
                .padding(.bottom, 6)
            ForEach(rows, id: \.kind) { row in
                if row.kind != rows.first?.kind {
                    Rectangle().fill(Color.cardBorder).frame(height: 1).padding(.vertical, 6)
                }
                line(row.kind, row.vital)
            }
        }
        .card()
    }

    private var rows: [(kind: VitalKind, vital: PhoneBody.Vital)] {
        [(VitalKind.hrv, vitals.hrv), (.restingHr, vitals.restingHr), (.sleep, vitals.sleep)]
            .compactMap { kind, vital in vital.map { (kind, $0) } }
    }

    private func status(_ kind: VitalKind, _ vital: PhoneBody.Vital) -> VitalStatus {
        VitalStatus(value: vital.value, low: vital.typicalLow, high: vital.typicalHigh)
    }

    private func line(_ kind: VitalKind, _ vital: PhoneBody.Vital) -> some View {
        let status = status(kind, vital)
        return HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 5) {
                    Image(systemName: kind.icon).font(.system(size: 10, weight: .bold))
                    Text(kind.label).font(AppFont.body(12, weight: .semibold))
                }
                .foregroundStyle(kind.color)
                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    Text(kind.format(vital.value)).font(AppFont.title(32)).foregroundStyle(Color.ink)
                    Text(kind.unit).font(AppFont.body(12, weight: .medium)).foregroundStyle(Color.muted)
                }
                Text(status.label)
                    .font(AppFont.body(11, weight: .semibold))
                    .foregroundStyle(status.isOutlier ? status.color(kind) : Color.faint)
            }
            .frame(width: 100, alignment: .leading)
            VitalWeekChart(kind: kind, days: vital.days ?? [], low: vital.typicalLow, high: vital.typicalHigh, today: today)
                .frame(height: 78)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(kind.label) \(kind.format(vital.value)) \(kind.unit), \(status.label)")
    }
}

// MARK: - Steps

private struct StepsCard: View {
    let steps: Double?
    let vital: PhoneBody.Vital?
    let hours: [LiveDay.Hour]
    let today: String

    private let color = Color.warning

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 16) {
                ZStack {
                    Circle().stroke(color.opacity(0.16), lineWidth: 10)
                    Circle()
                        .trim(from: 0, to: min(progress, 1))
                        .stroke(color, style: StrokeStyle(lineWidth: 10, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    if progress > 1 {
                        // A second lap past the average, like the Activity rings.
                        Circle()
                            .trim(from: 0, to: min(progress - 1, 1))
                            .stroke(Color.volt, style: StrokeStyle(lineWidth: 10, lineCap: .round))
                            .rotationEffect(.degrees(-90))
                    }
                    Image(systemName: "figure.walk").font(.system(size: 22, weight: .semibold)).foregroundStyle(color)
                }
                .frame(width: 78, height: 78)
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Steps today", color: color)
                    Text(steps.map(BodyFormat.steps) ?? "–").font(AppFont.title(44)).foregroundStyle(Color.ink)
                    if let baseline = vital?.baseline {
                        Text(progress >= 1 ? "Past your \(BodyFormat.steps(baseline)) daily average" : "\(Int((progress * 100).rounded()))% of your \(BodyFormat.steps(baseline)) average")
                            .font(AppFont.body(12)).foregroundStyle(Color.muted)
                    }
                }
            }
            if week.count >= 2 {
                VStack(alignment: .leading, spacing: 8) {
                    Kicker("Last 7 days")
                    weekChart.frame(height: 96)
                }
            }
            if !hours.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Kicker("Today by hour")
                    hourChart.frame(height: 70)
                }
            }
        }
        .card()
    }

    private var progress: Double {
        guard let steps, let baseline = vital?.baseline, baseline > 0 else { return 0 }
        return steps / baseline
    }

    /// The last 7 days, today's bar from the phone's own count when it's ahead of the last push.
    private var week: [(date: Date, value: Double, isToday: Bool)] {
        var days = (vital?.days ?? []).compactMap { day in TodayFormat.parse(day.date).map { (date: $0, value: day.value, isToday: day.date == today) } }
        if let steps, let date = TodayFormat.parse(today) {
            days.removeAll { $0.isToday }
            days.append((date, steps, true))
        }
        return days
    }

    private var weekChart: some View {
        let week = week
        return Chart {
            if let baseline = vital?.baseline {
                RuleMark(y: .value("Average", baseline))
                    .foregroundStyle(Color.faint)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                    .annotation(position: .top, alignment: .trailing, spacing: 2) {
                        Text("avg \(BodyFormat.steps(baseline))").font(AppFont.body(9, weight: .semibold)).foregroundStyle(Color.faint)
                    }
            }
            ForEach(week, id: \.date) { day in
                BarMark(x: .value("Day", day.date, unit: .day), y: .value("Steps", max(day.value, 1)), width: .ratio(0.55))
                    .foregroundStyle(day.isToday ? color : color.opacity(0.4))
                    .cornerRadius(4)
                    .annotation(position: .top, spacing: 3) {
                        if day.isToday {
                            Text(BodyFormat.steps(day.value)).font(AppFont.number(12)).foregroundStyle(color)
                        }
                    }
            }
        }
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: .stride(by: .day)) { value in
                AxisValueLabel(format: .dateTime.weekday(.narrow).locale(Locale(identifier: "en_GB")), centered: true)
                    .font(AppFont.body(10, weight: .medium))
                    .foregroundStyle(Color.faint)
            }
        }
    }

    private var hourChart: some View {
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

/// Today's heart rate like the Watch's Heart Rate app: the latest reading, each hour's range,
/// and resting rate as a dashed line through it.
private struct HeartCard: View {
    let vitals: PhoneBody.Vitals
    let live: LiveDay?

    private let color = Color.danger

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Kicker("Heart rate", color: color)
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text(headline.map { "\(Int($0.rounded()))" } ?? "–").font(AppFont.title(44)).foregroundStyle(Color.ink)
                        Text("bpm").font(AppFont.body(14)).foregroundStyle(Color.muted)
                    }
                    Text(caption).font(AppFont.body(12)).foregroundStyle(Color.muted)
                }
                Spacer()
                Image(systemName: "heart.fill")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(color)
                    .symbolEffect(.pulse, options: .repeating, isActive: live?.latestHeartRate != nil)
                    .frame(width: 40, height: 40)
                    .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            if let heart = live?.heart, !heart.isEmpty {
                chart(heart).frame(height: 120)
            }
            HStack(spacing: 0) {
                if let range = dayRange {
                    stat("Range today", "\(Int(range.low.rounded()))–\(Int(range.high.rounded()))")
                }
                if live?.latestHeartRate != nil {
                    stat("Resting", vitals.restingHr.map { "\(Int($0.value.rounded()))" } ?? "–")
                }
                stat("HRV", vitals.hrv.map { "\(Int($0.value.rounded())) ms" } ?? "–")
            }
        }
        .card()
    }

    /// The latest reading when the phone has today's, otherwise the resting rate.
    private var headline: Double? { live?.latestHeartRate ?? vitals.restingHr?.value }

    private var caption: String {
        if let at = live?.latestHeartRateAt { return "Latest · \(at.formatted(date: .omitted, time: .shortened))" }
        return vitals.restingHr == nil ? "No heart rate yet" : "Resting · from your Watch"
    }

    private var dayRange: (low: Double, high: Double)? {
        guard let heart = live?.heart, let low = heart.map(\.low).min(), let high = heart.map(\.high).max() else { return nil }
        return (low, high)
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(AppFont.body(11, weight: .medium)).foregroundStyle(Color.muted)
            Text(value).font(AppFont.number(22)).foregroundStyle(Color.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Each hour's lowest to highest heart rate as a capsule, resting rate dashed behind.
    private func chart(_ hours: [LiveDay.HeartHour]) -> some View {
        let start = Calendar.current.startOfDay(for: .now)
        let resting = vitals.restingHr?.value
        let low = min(hours.map(\.low).min() ?? 40, resting ?? .infinity)
        let high = hours.map(\.high).max() ?? 160
        return Chart {
            if let resting {
                RuleMark(y: .value("Resting", resting))
                    .foregroundStyle(Color.faint)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
            }
            ForEach(hours) { hour in
                RectangleMark(
                    x: .value("Hour", hour.start, unit: .hour),
                    yStart: .value("Low", hour.low),
                    yEnd: .value("High", max(hour.high, hour.low + 2)),
                    width: .ratio(0.55)
                )
                .foregroundStyle(color.opacity(hour == hours.last ? 1 : 0.6))
                .clipShape(Capsule())
            }
            if let latest = live?.latestHeartRate, let at = live?.latestHeartRateAt {
                PointMark(x: .value("Hour", at), y: .value("Latest", latest))
                    .symbol { Circle().fill(Color.ink).overlay(Circle().strokeBorder(color, lineWidth: 2)).frame(width: 9, height: 9) }
            }
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
