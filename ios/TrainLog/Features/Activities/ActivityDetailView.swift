import Charts
import SwiftUI

@MainActor
@Observable
final class ActivityDetailModel {
    private(set) var detail: ActivityDetail?
    private(set) var feedback: ActivityFeedback?
    private(set) var offline = false
    private(set) var error: String?

    let id: String
    private let client: () -> APIClient

    init(id: String, client: @escaping () -> APIClient = { .current }) {
        self.id = id
        self.client = client
    }

    func load() async {
        do {
            // The first open of an activity can fetch streams from Strava, so allow longer.
            let loaded = try await client().get("/activities/\(id)", as: ActivityDetail.self, timeout: 30)
            detail = loaded.value
            feedback = loaded.value.feedback
            offline = loaded.fromCache
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Shows saved feedback straight away; the list model sends it.
    func showFeedback(_ input: ActivityFeedbackInput) {
        feedback = ActivityFeedback(rpe: input.rpe, energy: input.energy, muscleSoreness: input.muscleSoreness,
                                    painLevel: input.painLevel, note: input.note)
    }
}

/// Read-only, phone-sized: six stat tiles, one chart, how it felt and the coach's take. Laps,
/// zones and segments stay on the web page.
struct ActivityDetailView: View {
    let summary: ActivitySummary?
    let onSaveFeedback: (ActivityFeedbackInput) -> Void
    @State private var model: ActivityDetailModel
    @State private var editingFeedback = false

    init(id: String, summary: ActivitySummary?, onSaveFeedback: @escaping (ActivityFeedbackInput) -> Void) {
        self.summary = summary
        self.onSaveFeedback = onSaveFeedback
        _model = State(initialValue: ActivityDetailModel(id: id))
    }

    private var activity: ActivitySummary? { model.detail?.activity ?? summary }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let activity {
                    header(activity)
                }
                if let detail = model.detail {
                    tiles(detail)
                    if let exercises = detail.strengthDetail?.session?.exercises, !exercises.isEmpty {
                        ExercisesCard(exercises: exercises)
                    } else if let series = ActivityDetailFormat.chartSeries(detail.charts, sport: ActivityFormat.sport(detail.activity), minutes: detail.activity.durationMin) {
                        StreamChartCard(series: series)
                    }
                    feelingCard
                    if let take = ActivityDetailFormat.coachTake(detail.analysis) {
                        coachCard(take)
                    }
                } else if let error = model.error {
                    VStack(alignment: .leading, spacing: 8) {
                        Kicker("Not loaded")
                        Text(error).font(AppFont.body(14)).foregroundStyle(Color.inkSoft)
                    }
                    .card()
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 240)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .background(Color.bg)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let url = ActivityDetailFormat.stravaURL(model.id) {
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: url) { Image(systemName: "square.and.arrow.up") }
                        .tint(.inkSoft)
                }
            }
        }
        .refreshable { await model.load() }
        .task { await model.load() }
        .sheet(isPresented: $editingFeedback) {
            FeedbackSheet(title: activity?.title ?? "", existing: model.feedback) { input in
                model.showFeedback(input)
                onSaveFeedback(input)
            }
        }
    }

    private func header(_ activity: ActivitySummary) -> some View {
        let sport = ActivityFormat.sport(activity)
        return VStack(alignment: .leading, spacing: 6) {
            Kicker(ActivityDetailFormat.kicker(activity), color: sport.color)
            Text(activity.title.uppercased())
                .font(AppFont.title(36))
                .foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 4)
    }

    private func tiles(_ detail: ActivityDetail) -> some View {
        let tiles = ActivityDetailFormat.tiles(detail, feedback: model.feedback)
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
            ForEach(tiles, id: \.label) { tile in
                VStack(alignment: .leading, spacing: 6) {
                    Text(tile.label.uppercased())
                        .font(AppFont.body(9, weight: .semibold))
                        .tracking(9 * 0.14)
                        .foregroundStyle(Color.muted)
                        .lineLimit(1)
                    Text("\(Text(tile.value).font(AppFont.number(26)).foregroundStyle(tile.color ?? Color.ink))\(Text(tile.unit.map { " \($0)" } ?? "").font(AppFont.body(12)).foregroundStyle(Color.muted))")
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.cardBorder))
            }
        }
    }

    private var feelingCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Kicker("How it felt")
                Spacer()
                if model.feedback != nil {
                    Button("Edit") { editingFeedback = true }
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .frame(minHeight: 32)
                }
            }
            if let feedback = model.feedback {
                HStack(spacing: 8) {
                    if let rpe = feedback.rpe { outlinePill("RPE \(rpe)") }
                    if let energy = feedback.energy { outlinePill("Energy \(energy)") }
                    if let pain = feedback.painLevel {
                        let color = ActivityDetailFormat.painColor(pain)
                        Text("Pain \(pain)")
                            .font(AppFont.body(12, weight: .semibold))
                            .foregroundStyle(color)
                            .padding(.horizontal, 10)
                            .frame(height: 26)
                            .background(color.opacity(0.12), in: Capsule())
                    }
                }
                if let note = feedback.note?.nilIfEmpty {
                    Text("“\(note)”")
                        .font(AppFont.body(14))
                        .foregroundStyle(Color(hex: 0xC9CFDA))
                        .lineSpacing(3)
                }
            } else {
                Button("Add how it felt") { editingFeedback = true }
                    .buttonStyle(OutlineButtonStyle(height: 44))
            }
        }
        .card()
    }

    private func outlinePill(_ text: String) -> some View {
        Text(text)
            .font(AppFont.body(12, weight: .semibold))
            .foregroundStyle(Color.inkSoft)
            .padding(.horizontal, 10)
            .frame(height: 26)
            .overlay(Capsule().strokeBorder(Color.outline))
    }

    private func coachCard(_ take: ActivityDetailFormat.CoachTake) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker("Coach take", color: .volt)
            if let headline = take.headline {
                Text(headline).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
            }
            if let body = take.body {
                Text(body).font(AppFont.body(14)).foregroundStyle(Color.ink).lineSpacing(3)
            }
        }
        .card(border: Color.volt.opacity(0.25))
    }
}

/// Power (or elevation) as a filled area and heart rate as a line, each on its own scale.
struct StreamChartCard: View {
    let series: ActivityDetailFormat.ChartSeries

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Kicker(series.title)
                Spacer()
                HStack(spacing: 8) {
                    if let area = series.area {
                        HStack(spacing: 4) {
                            RoundedRectangle(cornerRadius: 2).fill(series.areaColor).frame(width: 8, height: 8)
                            Text(area.unit)
                        }
                    }
                    if series.heartRate != nil {
                        HStack(spacing: 4) {
                            Rectangle().fill(ActivityDetailFormat.heartRateColor).frame(width: 8, height: 2)
                            Text("bpm")
                        }
                    }
                }
                .font(AppFont.body(11))
                .foregroundStyle(Color.muted)
            }
            Chart {
                if let area = series.area {
                    ForEach(area.points, id: \.x) { point in
                        AreaMark(x: .value("Time", point.x), y: .value(area.unit, point.y), series: .value("Series", "area"))
                            .foregroundStyle(series.areaColor.opacity(0.28))
                        LineMark(x: .value("Time", point.x), y: .value(area.unit, point.y), series: .value("Series", "areaLine"))
                            .foregroundStyle(series.areaColor)
                            .lineStyle(StrokeStyle(lineWidth: 1.6))
                    }
                }
                if let hr = series.heartRate {
                    ForEach(hr.points, id: \.x) { point in
                        LineMark(x: .value("Time", point.x), y: .value("bpm", point.y), series: .value("Series", "hr"))
                            .foregroundStyle(ActivityDetailFormat.heartRateColor)
                            .lineStyle(StrokeStyle(lineWidth: 2))
                            .interpolationMethod(.catmullRom)
                    }
                }
            }
            .chartYScale(domain: 0...1)
            .chartYAxis(.hidden)
            .chartXScale(domain: 0...series.duration)
            .chartXAxis {
                let ticks = series.ticks
                AxisMarks(values: ticks) { value in
                    let minutes = value.as(Double.self) ?? 0
                    AxisValueLabel(anchor: minutes == 0 ? .topLeading : minutes == ticks.last ? .topTrailing : .top) {
                        Text(ActivityFormat.clock(minutes)).font(AppFont.body(10)).foregroundStyle(Color.muted)
                    }
                }
            }
            .frame(height: 140)
        }
        .padding(.top, -2)
        .card()
    }
}

/// Strength sessions show their lifts instead of a stream chart.
struct ExercisesCard: View {
    let exercises: [ActivityDetail.StrengthDetail.Exercise]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Kicker("Exercises").padding(.bottom, 6)
            ForEach(Array(exercises.enumerated()), id: \.element.id) { index, exercise in
                if index > 0 { Divider().overlay(Color.cardBorder) }
                HStack(alignment: .firstTextBaseline) {
                    Text(String(format: "%02d", index + 1))
                        .font(AppFont.number(15))
                        .foregroundStyle(Color.strength)
                        .frame(width: 24, alignment: .leading)
                    Text(exercise.exerciseName).font(AppFont.body(14, weight: .medium)).foregroundStyle(Color.ink)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    Text(ActivityDetailFormat.setsLine(exercise)).font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
                }
                .padding(.vertical, 9)
            }
        }
        .card()
    }
}

enum ActivityDetailFormat {
    static let heartRateColor = Color(hex: 0xFF5A6E)

    struct Tile: Equatable {
        let label: String
        let value: String
        var unit: String?
        var color: Color?
    }

    struct CoachTake: Equatable {
        let headline: String?
        let body: String?
    }

    struct Series: Equatable {
        struct Point: Equatable {
            let x: Double
            let y: Double
        }
        let unit: String
        /// Normalised to 0...1 so two units share one chart.
        let points: [Point]
    }

    struct ChartSeries: Equatable {
        let title: String
        let area: Series?
        let areaColor: Color
        let heartRate: Series?
        let duration: Double

        /// Round marks (0:00, 10:00, 20:00…) and the end, in minutes.
        var ticks: [Double] {
            let step = [5.0, 10, 15, 20, 30, 60, 90, 120, 180].first { duration / $0 <= 3.5 } ?? 240
            let marks = stride(from: 0, to: duration - step * 0.4, by: step)
            return Array(marks) + [duration]
        }
    }

    /// "Ride · Tue 27 Oct · Virtual ride · Recovery".
    static func kicker(_ activity: ActivitySummary) -> String {
        let sport = ActivityFormat.sport(activity)
        var parts = [sport.label, ActivityFormat.longDay(activity.date)]
        let type = ActivityFormat.typeLabel(activity)
        if type.lowercased() != sport.label.lowercased() { parts.append(type) }
        if let intent = activity.workoutIntentLabel, activity.guidedSession == nil, !parts.contains(intent) {
            parts.append(intent)
        }
        return parts.joined(separator: " · ")
    }

    /// Up to six tiles, sport first, then pain when it was logged, then whatever else there is.
    static func tiles(_ detail: ActivityDetail, feedback: ActivityFeedback?) -> [Tile] {
        let activity = detail.activity
        let stats = Dictionary(detail.stats.map { ($0.key, $0) }, uniquingKeysWith: { first, _ in first })
        func number(_ key: String) -> Double? { stats[key]?.value?.number.flatMap { $0 > 0 ? $0 : nil } }

        let minutes = number("moving_time_min") ?? activity.durationMin
        let distance = number("distance_km").map { Tile(label: "Distance", value: $0.formatted(ActivityFormat.oneDecimal), unit: "km") }
        let time = minutes.map { Tile(label: "Time", value: ActivityFormat.clock($0)) }
        let avgHr = number("avg_hr").map { Tile(label: "Avg HR", value: "\(Int($0.rounded()))", unit: "bpm") }
        let maxHr = number("max_hr").map { Tile(label: "Max HR", value: "\(Int($0.rounded()))") }
        let power = number("avg_watts").map { Tile(label: "Avg power", value: "\(Int($0.rounded()))", unit: "W") }
        let normalized = number("normalized_power").map { Tile(label: "NP", value: "\(Int($0.rounded()))", unit: "W") }
        let speed = number("avg_speed_kmh").map { Tile(label: "Avg speed", value: $0.formatted(ActivityFormat.oneDecimal), unit: "km/h") }
        let climb = number("elevation_m").flatMap { $0 >= 10 ? Tile(label: "Climb", value: "\(Int($0.rounded()))", unit: "m") : nil }
        let pace: Tile? = {
            if case .text(let text)? = stats["avg_pace"]?.value { return Tile(label: "Pace", value: text, unit: "/km") }
            return nil
        }()
        let session = detail.strengthDetail?.session
        let sets = session?.setCount.map { Tile(label: "Sets", value: "\($0)") }
        let volume = session?.totalVolumeKg.flatMap { $0 > 0 ? Tile(label: "Volume", value: ($0 / 1000).formatted(ActivityFormat.oneDecimal), unit: "t") : nil }
        let pain = feedback?.painLevel.map { Tile(label: "Pain", value: "\($0)", unit: "/10", color: painColor($0)) }
        let rpe = feedback?.rpe.map { Tile(label: "RPE", value: "\($0)", unit: "/10") }

        let primary: [Tile?]
        let extra: [Tile?]
        switch ActivityFormat.sport(activity) {
        case .ride:
            primary = [distance, time, power ?? speed, avgHr, maxHr]
            extra = [normalized, climb, speed]
        case .run:
            primary = [distance, time, pace, avgHr, maxHr]
            extra = [climb, power]
        case .hike, .walk:
            primary = [distance, time, climb, avgHr, maxHr]
            extra = [speed]
        case .strength:
            primary = [time, sets, volume, avgHr, maxHr]
            extra = [rpe]
        default:
            primary = [distance, time, avgHr, maxHr]
            extra = [rpe, climb]
        }
        return Array((primary + [pain] + extra).compactMap { $0 }.prefix(6))
    }

    static func painColor(_ pain: Int) -> Color {
        switch pain {
        case 0: .mobility
        case 1...3: .warning
        default: .danger
        }
    }

    /// Power or (on hilly days) elevation as the area, heart rate as the line. Nil without either.
    static func chartSeries(_ charts: [ActivityDetail.Chart], sport: Sport, minutes: Double? = nil) -> ChartSeries? {
        func chart(_ key: String) -> ActivityDetail.Chart? { charts.first { $0.key == key } }
        func values(_ chart: ActivityDetail.Chart) -> [Double] { chart.points.compactMap(\.y) }

        var area: ActivityDetail.Chart?
        var areaColor = sport.color
        var title = "Heart rate"
        if let watts = chart("watts"), (values(watts).max() ?? 0) > 0 {
            area = watts
            title = "Power & heart rate"
        } else if let altitude = chart("altitude"), let low = values(altitude).min(), let high = values(altitude).max(), high - low >= 15 {
            area = altitude
            areaColor = .other
            title = "Elevation & heart rate"
        }
        let heartRate = chart("heartrate").flatMap { values($0).isEmpty ? nil : $0 }
        guard area != nil || heartRate != nil else { return nil }
        // The streams stop a few seconds short; the axis ends at the activity's own time.
        let duration = max(charts.flatMap { $0.points.map(\.t) }.max() ?? 0, minutes ?? 0)
        guard duration > 0 else { return nil }
        if area != nil && heartRate == nil { title = area?.key == "watts" ? "Power" : "Elevation" }

        return ChartSeries(
            title: title,
            // Raw power jumps every few seconds; a ~30 s average reads like the web chart.
            area: area.map { normalize($0, floorAtZero: $0.key == "watts", band: 0...0.8, smoothing: $0.key == "watts" ? 4 : 0) },
            areaColor: areaColor,
            heartRate: heartRate.map { normalize($0, floorAtZero: false, band: 0.15...1) },
            duration: duration
        )
    }

    /// Scales a stream into `band` of the 0...1 chart. Power starts at zero; heart rate and
    /// elevation use their own range so the shape shows.
    static func normalize(_ chart: ActivityDetail.Chart, floorAtZero: Bool, band: ClosedRange<Double>, smoothing: Int = 0) -> Series {
        let raw = chart.points.compactMap { point in point.y.map { (t: point.t, y: $0) } }
        let smoothed = raw.indices.map { index in
            let window = raw[max(0, index - smoothing)...min(raw.count - 1, index + smoothing)]
            return (t: raw[index].t, y: window.map(\.y).reduce(0, +) / Double(window.count))
        }
        let ys = smoothed.map(\.y)
        let low = floorAtZero ? 0 : (ys.min() ?? 0)
        let span = max((ys.max() ?? 1) - low, 1)
        let points = smoothed.map { Series.Point(x: $0.t, y: band.lowerBound + ($0.y - low) / span * (band.upperBound - band.lowerBound)) }
        return Series(unit: chart.unit ?? chart.label, points: points)
    }

    /// The saved analysis when there is one, otherwise the automatic session read.
    static func coachTake(_ analysis: ActivityDetail.Analysis?) -> CoachTake? {
        guard let analysis else { return nil }
        if ["ready", "stale"].contains(analysis.status), let summary = analysis.summary?.nilIfEmpty {
            return CoachTake(headline: analysis.headline?.nilIfEmpty, body: summary)
        }
        let read = analysis.sessionRead
        let headline = read?.verdict?.headline?.nilIfEmpty
        let detail = read?.wins?.first?.detail?.nilIfEmpty
        guard headline != nil || detail != nil else { return nil }
        return CoachTake(headline: headline, body: detail)
    }

    /// "4 × 8 · 62.5 kg": work sets, the most common rep count, the top weight.
    static func setsLine(_ exercise: ActivityDetail.StrengthDetail.Exercise) -> String {
        let work = exercise.sets.filter { $0.isWarmup != true }
        guard !work.isEmpty else { return "" }
        let reps = work.compactMap(\.reps)
        let commonReps = Dictionary(grouping: reps, by: { $0 }).max { $0.value.count < $1.value.count }?.key
        var line = "\(work.count)" + (commonReps.map { " × \($0)" } ?? " sets")
        if let top = work.compactMap(\.weightKg).max(), top > 0 {
            line += " · \(top.formatted(ActivityFormat.oneDecimal.precision(.fractionLength(0...1)))) kg"
        }
        return line
    }

    /// Strava activities have numeric ids; manual ones don't link anywhere.
    static func stravaURL(_ id: String) -> URL? {
        guard !id.isEmpty, id.allSatisfy(\.isNumber) else { return nil }
        return URL(string: "https://www.strava.com/activities/\(id)")
    }
}
