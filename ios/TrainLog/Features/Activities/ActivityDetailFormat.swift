import CoreLocation
import SwiftUI

/// Everything the detail screen computes from `GET /activities/{id}`, kept out of the views so it
/// can be tested. The page itself (header, grid, sections) is in ActivityDetailPage.swift.
enum ActivityDetailFormat {
    static let good = Color.mobility
    static let warn = Color(hex: 0xFFC83A)
    static let bad = Color(hex: 0xFF5C6F)

    static func painColor(_ pain: Int) -> Color {
        switch pain {
        case 0: .mobility
        case 1...3: warn
        default: bad
        }
    }

    /// Pain worth the red block under the header rather than a cell in How it felt.
    static func painAlert(_ feedback: ActivityFeedback?) -> (pain: Int, note: String?)? {
        guard let pain = feedback?.painLevel, pain >= 4 else { return nil }
        return (pain, feedback?.note?.nilIfEmpty)
    }

    static func number(_ detail: ActivityDetail, _ key: String) -> Double? {
        detail.stats.first { $0.key == key }?.value?.number.flatMap { $0 > 0 ? $0 : nil }
    }

    static func avgPaceText(_ detail: ActivityDetail) -> String? {
        if case .text(let text)? = detail.stats.first(where: { $0.key == "avg_pace" })?.value { return text }
        return nil
    }

    static func isIndoorRide(_ detail: ActivityDetail) -> Bool {
        detail.cycling?.environment == "indoor" || detail.activity.type == "VirtualRide"
    }

    static func platform(_ activity: ActivitySummary) -> String? {
        ["MyWhoosh", "Zwift", "Rouvy", "TrainerRoad"].first { activity.name.localizedCaseInsensitiveContains($0) }
    }

    /// Average of the non-zero cadence samples (coasting reads as zero).
    static func averageCadence(_ detail: ActivityDetail) -> Double? {
        let values = chart(detail, "cadence")?.values.filter { $0 > 0 } ?? []
        guard values.count > 10 else { return nil }
        return values.reduce(0, +) / Double(values.count)
    }

    // MARK: Streams

    static func chart(_ detail: ActivityDetail, _ key: String) -> ActivityDetail.Chart? {
        detail.charts.first { $0.key == key }
    }

    /// A stream worth drawing: something above zero, and (for elevation) some actual climbing.
    static func usable(_ detail: ActivityDetail, _ key: String) -> ActivityDetail.Chart? {
        guard let chart = chart(detail, key), (chart.values.max() ?? 0) > 0, chart.values.count >= 2 else { return nil }
        if key == "altitude", let low = chart.min, let high = chart.max, high - low < 15 { return nil }
        return chart
    }

    static func hasStreams(_ detail: ActivityDetail) -> Bool {
        ["heartrate", "watts", "pace", "speed", "altitude"].contains { usable(detail, $0) != nil }
    }

    /// Moving average over `window` samples either side.
    static func smooth(_ values: [Double], window: Int) -> [Double] {
        guard window > 0 else { return values }
        return values.indices.map { index in
            let slice = values[Swift.max(0, index - window)...Swift.min(values.count - 1, index + window)]
            return slice.reduce(0, +) / Double(slice.count)
        }
    }

    // MARK: Main chart

    struct ChartChip: Equatable {
        let key: String
        let title: String
        let color: Color
    }

    static func chipColor(_ key: String) -> Color {
        switch key {
        case "pace", "speed": Metric.pace.color
        case "heartrate": Metric.heartRate.color
        case "altitude": Metric.elevation.color
        case "watts": Metric.power.color
        case "cadence": Metric.cadence.color
        default: Metric.grade.color
        }
    }

    static func chipTitle(_ key: String) -> String {
        switch key {
        case "watts": "Power"
        case "pace": "Pace"
        case "altitude": "Elevation"
        case "cadence": "Cadence"
        case "speed": "Speed"
        case "heartrate": "Heart rate"
        case "grade_smooth": "Grade"
        default: key.capitalized
        }
    }

    /// The chips a sport gets, in order, from the streams that have something in them.
    static func chips(_ detail: ActivityDetail) -> [ChartChip] {
        let keys: [String] = switch ActivityFormat.sport(detail.activity) {
        case .ride: isIndoorRide(detail) ? ["watts", "heartrate", "cadence", "speed"] : ["speed", "heartrate", "altitude", "grade_smooth"]
        case .run: ["pace", "heartrate", "altitude", "watts"]
        case .hike, .walk: ["altitude", "heartrate", "speed"]
        default: ["heartrate"]
        }
        return keys.compactMap { key in
            if key == "grade_smooth" {
                guard usable(detail, "altitude") != nil, let grade = chart(detail, key), grade.values.contains(where: { $0 != 0 }) else { return nil }
            } else if usable(detail, key) == nil {
                return nil
            }
            return ChartChip(key: key, title: chipTitle(key), color: chipColor(key))
        }
    }

    /// Hikes and walks read along the route; everything else along the clock.
    static func chartsByDistance(_ detail: ActivityDetail) -> Bool {
        [.hike, .walk].contains(ActivityFormat.sport(detail.activity))
            && (chart(detail, "altitude")?.points.last?.x ?? 0) > 0.5
    }

    static func chartModel(_ detail: ActivityDetail, key: String) -> MetricChartModel? {
        guard let source = key == "grade_smooth" ? chart(detail, key) : usable(detail, key) else { return nil }
        let byDistance = chartsByDistance(detail)
        let raw = source.points.compactMap { point -> (x: Double, y: Double)? in
            guard let y = point.y else { return nil }
            return (byDistance ? (point.x ?? point.t) : point.t, y)
        }
        guard raw.count >= 2 else { return nil }
        let values = raw.map(\.y)
        let sorted = values.sorted()
        let clip: ClosedRange<Double>? = switch key {
        case "pace": paceClip(sorted)
        case "watts": 0...(sorted.percentile(0.99) ?? 2000)
        case "heartrate": (sorted.percentile(0.01) ?? 0)...(sorted.last ?? 250)
        default: nil
        }
        let clipped = values.map { y in clip.map { Swift.min(Swift.max(y, $0.lowerBound), $0.upperBound) } ?? y }
        let window = ["pace": 3, "watts": 3, "speed": 3, "cadence": 3, "heartrate": 1, "grade_smooth": 3][key] ?? 1
        let smoothed = smooth(clipped, window: window)
        let points = zip(raw, smoothed).map { MetricChartModel.Point(x: $0.x, y: $1) }

        let sortedSmooth = smoothed.sorted()
        // Dropouts (stops, coasting) shouldn't squash the rest of the line against the top.
        var lo = ["watts", "speed", "cadence"].contains(key) ? (sortedSmooth.percentile(0.03) ?? 0) : (sortedSmooth.first ?? 0)
        var hi = sortedSmooth.last ?? 1
        let pad = Swift.max((hi - lo) * 0.1, key == "pace" ? 0.05 : 1)
        hi += pad
        lo = Swift.max(lo - pad, key == "pace" ? 0 : -1000)
        let ticks = niceTicks(lo...hi, steps: key == "pace" ? [0.25, 0.5, 1, 2] : [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000])
            .map { MetricChartModel.Tick(value: $0, label: tickLabel(key, $0)) }

        let duration = raw.last?.x ?? 1
        var ghost: [MetricChartModel.Point] = []
        if ["pace", "speed", "watts"].contains(key), !isIndoorRide(detail), let altitude = usable(detail, "altitude"), let low = altitude.min, let high = altitude.max {
            ghost = altitude.points.compactMap { point in
                point.y.map { MetricChartModel.Point(x: byDistance ? (point.x ?? point.t) : point.t, y: ($0 - low) / Swift.max(high - low, 1)) }
            }
        }
        let average = averageValue(detail, key, fallback: clipped)
        return MetricChartModel(
            key: key, title: chipTitle(key), color: chipColor(key), points: points, ghost: ghost,
            yDomain: lo...hi, invert: key == "pace", yTicks: ticks,
            xDomain: (raw.first?.x ?? 0)...duration, xTicks: xTicks(duration, byDistance: byDistance),
            average: key == "altitude" || key == "grade_smooth" ? nil : average,
            averageLabel: key == "altitude" || key == "grade_smooth" ? nil : average.map { tickLabel(key, $0, precise: true) }
        )
    }

    private static func averageValue(_ detail: ActivityDetail, _ key: String, fallback: [Double]) -> Double? {
        switch key {
        case "pace": return avgPaceText(detail).flatMap(seconds).map { $0 / 60 }
        case "heartrate": return number(detail, "avg_hr") ?? detail.activity.avgHr
        case "watts": return (detail.cycling?.power?.avgWatts ?? number(detail, "avg_watts"))
        case "speed": return number(detail, "avg_speed_kmh")
        case "cadence": return averageCadence(detail)
        default: return fallback.isEmpty ? nil : fallback.reduce(0, +) / Double(fallback.count)
        }
    }

    /// Pace clipped to a sensible running window around the median (walk breaks would flatten the rest).
    private static func paceClip(_ sorted: [Double]) -> ClosedRange<Double> {
        let median = sorted.percentile(0.5) ?? 6
        return Swift.max(2.5, median - 1.5)...(median + 2)
    }

    static func tickLabel(_ key: String, _ value: Double, precise: Bool = false) -> String {
        switch key {
        case "pace": paceText(value * 60)
        case "speed": precise ? value.formatted(ActivityFormat.oneDecimal) : "\(Int(value.rounded()))"
        default: "\(Int(value.rounded()))"
        }
    }

    /// Two to four round values inside `range`, from the first step that fits.
    static func niceTicks(_ range: ClosedRange<Double>, steps: [Double]) -> [Double] {
        for step in steps {
            let first = (range.lowerBound / step).rounded(.up) * step
            let values = Array(stride(from: first, through: range.upperBound, by: step))
            if values.count <= 4 { return values.count >= 2 ? values : [first] }
        }
        return []
    }

    /// Round marks (0:00, 10:00…) and the end; for distance, quarters of the route.
    static func xTicks(_ end: Double, byDistance: Bool) -> [MetricChartModel.Tick] {
        if byDistance {
            let marks = [0, 0.25, 0.5, 0.75].map { $0 * end } + [end]
            return marks.enumerated().map { index, km in
                let text = km.formatted(ActivityFormat.upToOneDecimal)
                return .init(value: km, label: index == 0 || index == marks.count - 1 ? "\(text) km" : text)
            }
        }
        let step = [5.0, 10, 15, 20, 30, 50, 60, 90, 120, 180].first { end / $0 <= 3.5 } ?? 240
        let marks = Array(stride(from: 0, to: end - step * 0.4, by: step)) + [end]
        return marks.map { .init(value: $0, label: ActivityFormat.clock($0)) }
    }

    /// Value text for the scrub pill.
    static func scrubValue(_ key: String, _ raw: Double) -> String {
        switch key {
        case "pace": "\(paceText(raw * 60)) /km"
        case "watts": "\(Int(raw.rounded())) W"
        case "altitude": "\(Int(raw.rounded())) m"
        case "cadence": "\(Int(raw.rounded())) rpm"
        case "speed": "\(raw.formatted(ActivityFormat.oneDecimal)) km/h"
        case "grade_smooth": "\(raw.formatted(ActivityFormat.oneDecimal))%"
        default: "\(Int(raw.rounded())) bpm"
        }
    }

    /// The raw sample of a stream nearest to `t` minutes.
    static func sample(_ detail: ActivityDetail, _ key: String, at t: Double) -> Double? {
        guard let points = chart(detail, key)?.points, !points.isEmpty else { return nil }
        return points.min { abs($0.t - t) < abs($1.t - t) }?.y
    }

    // MARK: Zones

    struct ZoneRow: Equatable {
        let name: String
        let range: String
        let minutes: Double
        let pct: Double
        let color: Color
    }

    /// Zone rows, with a tail of near-empty zones folded into one "Zone 4+" row unless `full`.
    static func zoneRows(_ zones: ActivityDetail.Zones?, full: Bool = false) -> [ZoneRow] {
        guard zones?.available == true, let list = zones?.zones, !list.isEmpty else { return [] }
        var rows = list.enumerated().map { index, zone in
            ZoneRow(name: "Zone \(index + 1)", range: zone.range ?? "", minutes: zone.minutes ?? 0, pct: zone.pct ?? 0,
                    color: ZonePalette.color(index))
        }
        if !full, let cut = rows.indices.first(where: { index in index >= 3 && rows[index...].allSatisfy { $0.pct < 1 } }), rows.count - cut > 1 {
            let tail = rows[cut...]
            rows = Array(rows[..<cut]) + [ZoneRow(name: "Zone \(cut + 1)+", range: "", minutes: tail.map(\.minutes).reduce(0, +),
                                                  pct: tail.map(\.pct).reduce(0, +), color: ZonePalette.color(cut))]
        }
        return rows
    }

    /// "5m 54s", "2h 28m", "–" for nothing.
    static func zoneTime(_ minutes: Double) -> String {
        let seconds = Int((minutes * 60).rounded())
        if seconds == 0 { return "–" }
        if seconds >= 3600 { return "\(seconds / 3600)h \(seconds % 3600 / 60)m" }
        return "\(seconds / 60)m \(String(format: "%02d", seconds % 60))s"
    }

    /// One line under the zone bars: easy all the way, too hot for an easy day, or where it mostly sat.
    static func zoneSummary(_ detail: ActivityDetail) -> (tone: StatusTone, text: String)? {
        let zones = (detail.heartRateZones?.available == true ? detail.heartRateZones?.zones : nil) ?? []
        guard zones.count >= 3 else { return nil }
        let pcts = zones.map { $0.pct ?? 0 }
        let easyTwo = Int((pcts[0] + pcts[1]).rounded())
        let above = Int(pcts.dropFirst(2).reduce(0, +).rounded())
        let dominant = (pcts.indices.max { pcts[$0] < pcts[$1] } ?? 0) + 1
        let sport = ActivityFormat.sport(detail.activity)
        let easyIntent = ["recovery", "easy", "endurance", "z2"].contains(detail.activity.workoutIntent ?? "")
        if easyTwo >= 95 { return (.good, "Easy all the way: \(easyTwo)% in Zones 1–2.") }
        if sport == .ride, easyIntent || detail.workoutExecution != nil {
            return (above <= 15 ? .good : .warn, "Easy rides stay under 15% above Zone 2. This one: \(above)%.")
        }
        if easyIntent && dominant >= 3 {
            return (.warn, "Mostly Zone \(dominant). An easy \(sport == .run ? "run" : "session") wants most of it in Zone 2.")
        }
        return (.info, "Mostly Zone \(dominant), \(Int(pcts[dominant - 1].rounded()))% of the time.")
    }

    // MARK: Lifts

    struct LiftRow: Identifiable {
        let id: String
        let name: String
        let muscle: String?
        let sets: [(value: String, unit: String)]
        let badge: (text: String, tone: String)?
        let last: String?
        let next: String?
    }

    static func liftRows(_ detail: ActivityDetail) -> [LiftRow] {
        guard let exercises = detail.strengthDetail?.session?.exercises else { return [] }
        let progression = detail.strengthDetail?.progression?.exercises ?? [:]
        return exercises.map { exercise in
            let lift = progression.values.first { $0.exerciseName == exercise.exerciseName }
            let sets = exercise.sets.filter { $0.isWarmup != true }.map { set -> (String, String) in
                guard let kg = set.weightKg, kg > 0 else { return ("\(set.reps ?? 0)", " reps") }
                return (kg.formatted(ActivityFormat.upToOneDecimal), set.reps.map { "×\($0)" } ?? "")
            }
            let muscle = MuscleRules.classify(exercise.exerciseName)?.primary.first?.label
            return LiftRow(id: exercise.id, name: exercise.exerciseName, muscle: muscle, sets: sets,
                           badge: lift.flatMap(badge), last: lift?.previous.flatMap(lastTime),
                           next: lift?.nextHint.flatMap(hint)?.action)
        }
    }

    /// "Last 4 × 8 @ 60 kg · 10 Oct", "Last 12 · 10 reps · 18 Oct".
    static func lastTime(_ previous: ActivityDetail.StrengthDetail.Progression.Lift.Snapshot) -> String? {
        guard let sets = previous.sets, !sets.isEmpty else { return nil }
        let day = previous.date.map { " · " + ActivityFormat.longDay($0).split(separator: " ").dropFirst().joined(separator: " ") } ?? ""
        let weights = Set(sets.compactMap(\.weightKg))
        let reps = sets.compactMap(\.reps)
        if weights.count == 1, let kg = weights.first, kg > 0, Set(reps).count == 1, let rep = reps.first {
            return "Last \(sets.count) × \(rep) @ \(kg.formatted(ActivityFormat.upToOneDecimal)) kg\(day)"
        }
        if weights.isEmpty || weights == [0] {
            return "Last \(reps.map(String.init).joined(separator: " · ")) reps\(day)"
        }
        let text = sets.map { set in "\(set.weightKg.map { $0.formatted(ActivityFormat.upToOneDecimal) } ?? "BW")×\(set.reps ?? 0)" }
        return "Last \(text.joined(separator: ", "))\(day)"
    }

    /// "▲ 3.2 kg e1RM", "▼ 2 reps", "= Matched", "PR".
    static func badge(_ lift: ActivityDetail.StrengthDetail.Progression.Lift) -> (text: String, tone: String)? {
        if lift.isPr == true { return ("PR", "pr") }
        guard let direction = lift.direction else { return nil }
        if direction == "same" { return ("= Matched", "same") }
        let arrow = direction == "up" ? "▲" : "▼"
        let tone = direction == "up" ? "good" : "warn"
        let amount = abs(lift.delta ?? 0)
        guard amount >= 0.05 else { return ("\(arrow) \(direction)", tone) }
        switch lift.metric {
        case "e1rm": return ("\(arrow) \(amount.formatted(ActivityFormat.upToOneDecimal)) kg e1RM", tone)
        case "reps": return ("\(arrow) \(Int(amount.rounded())) reps", tone)
        default: return ("\(arrow) \(amount.formatted(ActivityFormat.upToOneDecimal)) kg", tone)
        }
    }

    /// "Every set at 62.5 kg × 8 — try 65 kg next time." → lead + action ("65 kg next time").
    static func hint(_ text: String) -> (lead: String?, action: String)? {
        let parts = text.components(separatedBy: " — ")
        if parts.count == 2 {
            let action = parts[1].replacingOccurrences(of: "try ", with: "").trimmingCharacters(in: CharacterSet(charactersIn: ". "))
            return (parts[0], action)
        }
        return text.nilIfEmpty.map { (nil, $0.trimmingCharacters(in: CharacterSet(charactersIn: ". "))) }
    }

    /// "vs 10 Oct" when every lift was compared with the same session.
    static func liftsComparedTo(_ detail: ActivityDetail) -> String? {
        let dates = Set(detail.strengthDetail?.progression?.exercises.values.compactMap { $0.previous?.date } ?? [])
        guard dates.count == 1, let date = dates.first else { return dates.isEmpty ? nil : "vs last time" }
        return "vs \(ActivityFormat.longDay(date).split(separator: " ").dropFirst().joined(separator: " "))"
    }

    // MARK: Coach

    struct CoachTake: Equatable {
        let headline: String?
        let body: String?
        var observations: [String] = []
    }

    enum CoachState: Equatable {
        case take(CoachTake)
        case pending
        case canAsk(failed: Bool)
        case none
    }

    static func coachState(_ analysis: ActivityDetail.Analysis?) -> CoachState {
        guard let analysis else { return .none }
        if ["ready", "stale"].contains(analysis.status), let summary = analysis.summary?.nilIfEmpty {
            return .take(CoachTake(headline: analysis.headline?.nilIfEmpty, body: summary, observations: analysis.keyObservations ?? []))
        }
        if analysis.available == false { return .none }
        switch analysis.status {
        case "pending": return .pending
        case "failed": return .canAsk(failed: true)
        case "not_requested": return .canAsk(failed: false)
        default: return .none
        }
    }

    // MARK: Pace and route

    /// "5:24" from seconds per km.
    static func paceText(_ secondsPerKm: Double) -> String {
        let total = Int(secondsPerKm.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    static func seconds(_ pace: String) -> Double? {
        let parts = pace.split(separator: ":").compactMap { Double($0) }
        return parts.count == 2 ? parts[0] * 60 + parts[1] : nil
    }

    /// Google encoded polyline → coordinates.
    static func decodePolyline(_ encoded: String) -> [CLLocationCoordinate2D] {
        let bytes = Array(encoded.utf8)
        var coordinates: [CLLocationCoordinate2D] = []
        var index = 0, lat = 0, lng = 0
        func next() -> Int? {
            var result = 0, shift = 0
            while index < bytes.count {
                let byte = Int(bytes[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20 { return (result & 1) != 0 ? ~(result >> 1) : result >> 1 }
            }
            return nil
        }
        while index < bytes.count {
            guard let dLat = next(), let dLng = next() else { break }
            lat += dLat
            lng += dLng
            coordinates.append(CLLocationCoordinate2D(latitude: Double(lat) / 1e5, longitude: Double(lng) / 1e5))
        }
        return coordinates
    }

    /// The route, if it's somewhere you actually were: virtual rides carry the game world's.
    static func route(_ detail: ActivityDetail) -> [CLLocationCoordinate2D]? {
        guard !isIndoorRide(detail), let polyline = detail.route?.polyline else { return nil }
        let coordinates = decodePolyline(polyline)
        return coordinates.count >= 2 ? coordinates : nil
    }

    /// Strava activities have numeric ids; manual ones don't link anywhere.
    static func stravaURL(_ id: String) -> URL? {
        guard !id.isEmpty, id.allSatisfy(\.isNumber) else { return nil }
        return URL(string: "https://www.strava.com/activities/\(id)")
    }

    static func clamp(_ value: Double) -> Double { Swift.min(Swift.max(value, 0), 1) }
}

extension ActivityDetail.Chart {
    var values: [Double] { points.compactMap(\.y) }
    var min: Double? { values.min() }
    var max: Double? { values.max() }
}

extension Array where Element == Double {
    /// `self` must be sorted.
    func percentile(_ p: Double) -> Double? {
        isEmpty ? nil : self[Swift.min(count - 1, Int(Double(count - 1) * p))]
    }
}
