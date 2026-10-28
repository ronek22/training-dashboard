import CoreLocation
import SwiftUI

/// Everything the detail screen computes from `GET /activities/{id}`, kept out of the views so it
/// can be tested.
enum ActivityDetailFormat {
    static let heartRateColor = Color(hex: 0xFF5A6E)
    static let zoneColors: [Color] = [Color(hex: 0x5B6478), .mobility, Color(hex: 0xFFC83A), .run, heartRateColor, .other, Color(hex: 0xC04DFF)]
    static let good = Color.mobility
    static let warn = Color(hex: 0xFFC83A)
    static let bad = heartRateColor

    static func toneColor(_ tone: String?) -> Color {
        switch tone {
        case "good": good
        case "warn": warn
        case "bad": bad
        default: Color(hex: 0x5B6478)
        }
    }

    // MARK: Header

    /// "Ride · Tue 27 Oct · Virtual ride". Intent moved to a chip.
    static func kicker(_ activity: ActivitySummary) -> String {
        let sport = ActivityFormat.sport(activity)
        var parts = [sport.label, ActivityFormat.longDay(activity.date)]
        let type = ActivityFormat.typeLabel(activity)
        if type.lowercased() != sport.label.lowercased() { parts.append(type) }
        return parts.joined(separator: " · ")
    }

    /// Indoor/outdoor, intent, FTP, mountain region, top altitude.
    static func chips(_ detail: ActivityDetail) -> [String] {
        let activity = detail.activity
        var chips: [String] = []
        if let environment = detail.cycling?.environment {
            chips.append(environment == "indoor" ? (activity.type == "VirtualRide" ? "Indoor · \(platform(activity) ?? "virtual")" : "Indoor") : "Outdoor")
        }
        if let intent = activity.workoutIntentLabel, activity.guidedSession == nil { chips.append(intent) }
        if let region = detail.mountainRegion?.nilIfEmpty {
            chips.append(region.replacingOccurrences(of: "_", with: " ").capitalized)
        }
        if let ftp = detail.cycling?.ftpWatts, detail.cycling?.power != nil { chips.append("FTP \(Int(ftp.rounded())) W") }
        if [.hike, .walk].contains(ActivityFormat.sport(activity)), let top = chart(detail, "altitude")?.max, top >= 300 {
            chips.append("Top \(Int(top.rounded())) m")
        }
        return chips
    }

    private static func platform(_ activity: ActivitySummary) -> String? {
        ["MyWhoosh", "Zwift", "Rouvy", "TrainerRoad"].first { activity.name.localizedCaseInsensitiveContains($0) }
    }

    /// Pain worth a banner under the title rather than a pill further down.
    static func painAlert(_ feedback: ActivityFeedback?) -> (pain: Int, note: String?)? {
        guard let pain = feedback?.painLevel, pain >= 4 else { return nil }
        return (pain, feedback?.note?.nilIfEmpty)
    }

    static func painColor(_ pain: Int) -> Color {
        switch pain {
        case 0: .mobility
        case 1...3: .warning
        default: .danger
        }
    }

    // MARK: Stat block

    struct Headline: Equatable {
        let label: String
        let value: String
        var unit: String?
    }

    struct Gauge: Equatable {
        enum Icon: Equatable { case power, heart, pace, climb, volume }
        struct Band: Equatable {
            let width: Double
            let color: Color
        }
        struct AxisLabel: Equatable {
            /// 0...1 along the track; nil pins it to the right end.
            let at: Double?
            let text: String
        }

        let icon: Icon
        let label: String
        let value: String
        let unit: String
        var valueColor: Color?
        /// Up to two lines, bold part first: ("126", "NP").
        var side: [(bold: String, text: String)] = []
        /// Empty draws a plain track.
        var bands: [Band] = []
        let dot: Double
        var tick: Double?
        var range: ClosedRange<Double>?
        var labels: [AxisLabel] = []

        static func == (lhs: Gauge, rhs: Gauge) -> Bool {
            lhs.label == rhs.label && lhs.value == rhs.value && lhs.unit == rhs.unit && lhs.dot == rhs.dot
                && lhs.tick == rhs.tick && lhs.bands == rhs.bands && lhs.labels == rhs.labels
                && lhs.side.map { $0.bold + "|" + $0.text } == rhs.side.map { $0.bold + "|" + $0.text }
        }
    }

    struct StatBlock: Equatable {
        let headline: [Headline]
        let gauges: [Gauge]
        /// (label, value) pairs.
        let footer: [(String, String)]

        static func == (lhs: StatBlock, rhs: StatBlock) -> Bool {
            lhs.headline == rhs.headline && lhs.gauges == rhs.gauges
                && lhs.footer.map { $0.0 + $0.1 } == rhs.footer.map { $0.0 + $0.1 }
        }
    }

    static func number(_ detail: ActivityDetail, _ key: String) -> Double? {
        detail.stats.first { $0.key == key }?.value?.number.flatMap { $0 > 0 ? $0 : nil }
    }

    /// "30:24" under an hour, "1:39" + "h" above.
    static func headlineTime(_ minutes: Double) -> (String, String?) {
        let total = Int((minutes * 60).rounded())
        if total < 3600 { return (String(format: "%d:%02d", total / 60, total % 60), nil) }
        let rounded = Int((minutes).rounded())
        return (String(format: "%d:%02d", rounded / 60, rounded % 60), "h")
    }

    static func statBlock(_ detail: ActivityDetail, paces: RunningPaces.Paces.Zones? = nil) -> StatBlock {
        let activity = detail.activity
        let sport = ActivityFormat.sport(activity)
        let minutes = number(detail, "moving_time_min") ?? activity.durationMin
        let time = minutes.map { headlineTime($0) }
        let distance = number(detail, "distance_km").flatMap { $0 >= 0.1 ? $0 : nil }
        let distanceHeadline = distance.map { Headline(label: "Distance", value: $0 >= 100 ? "\(Int($0.rounded()))" : $0.formatted(sport == .run ? ActivityFormat.twoDecimals : ActivityFormat.oneDecimal), unit: "km") }
        let timeHeadline = time.map { Headline(label: distance == nil ? "Time" : "Moving time", value: $0.0, unit: $0.1) }
        let hr = heartRateGauge(detail)

        switch sport {
        case .ride:
            let footer: [(String, String)] = [
                number(detail, "avg_speed_kmh").map { ("Speed", "\($0.formatted(ActivityFormat.oneDecimal)) km/h") },
                averageCadence(detail).map { ("Cadence", "\(Int($0.rounded())) rpm") },
                (detail.cycling?.power ?? detail.cycling?.estimatedPower)?.tss.map { ("TSS", "\(Int($0.rounded()))") },
            ].compactMap { $0 }
            return StatBlock(headline: [distanceHeadline, timeHeadline].compactMap { $0 },
                             gauges: [powerGauge(detail), hr].compactMap { $0 }, footer: footer)
        case .run:
            let footer: [(String, String)] = [
                number(detail, "elevation_m").map { ("Climb", "\(Int($0.rounded())) m") },
                number(detail, "avg_watts").map { ("Power", "\(Int($0.rounded())) W") },
            ].compactMap { $0 }
            return StatBlock(headline: [distanceHeadline, timeHeadline].compactMap { $0 },
                             gauges: [paceGauge(detail, paces: paces), hr].compactMap { $0 }, footer: footer)
        case .hike, .walk:
            let footer: [(String, String)] = [
                number(detail, "avg_speed_kmh").map { ("Speed", "\($0.formatted(ActivityFormat.oneDecimal)) km/h") },
                number(detail, "elapsed_time_min").flatMap { elapsed in
                    minutes.flatMap { elapsed - $0 >= 5 ? ("Elapsed", ActivityFormat.compactDuration(elapsed)) : nil }
                },
            ].compactMap { $0 }
            return StatBlock(headline: [distanceHeadline, timeHeadline].compactMap { $0 },
                             gauges: [climbGauge(detail), hr].compactMap { $0 }, footer: footer)
        case .strength:
            let session = detail.strengthDetail?.session
            let volume = session?.totalVolumeKg.flatMap { $0 > 0 ? Headline(label: "Volume", value: ($0 / 1000).formatted(ActivityFormat.twoDecimals), unit: "t") : nil }
            let footer: [(String, String)] = [
                session?.setCount.map { ("Sets", "\($0)") },
                session?.repCount.map { ("Reps", "\($0)") },
                (session?.exerciseCount ?? session.map { $0.exercises.count }).flatMap { $0 > 0 ? ("Lifts", "\($0)") : nil },
            ].compactMap { $0 }
            let timeOnly = time.map { Headline(label: "Time", value: $0.0, unit: $0.1) }
            return StatBlock(headline: [volume, timeOnly].compactMap { $0 },
                             gauges: [volumeGauge(detail), hr].compactMap { $0 }, footer: footer)
        default:
            return StatBlock(headline: [timeHeadline, distanceHeadline].compactMap { $0 }, gauges: [hr].compactMap { $0 }, footer: [])
        }
    }

    /// Average of the non-zero cadence samples (coasting reads as zero).
    static func averageCadence(_ detail: ActivityDetail) -> Double? {
        let values = chart(detail, "cadence")?.values.filter { $0 > 0 } ?? []
        guard values.count > 10 else { return nil }
        return values.reduce(0, +) / Double(values.count)
    }

    /// Average power on the rider's FTP zones (0–150% of FTP), with a tick at NP.
    static func powerGauge(_ detail: ActivityDetail) -> Gauge? {
        let cycling = detail.cycling
        let measured = cycling?.power
        let power = measured ?? cycling?.estimatedPower
        guard let avg = power?.avgWatts ?? number(detail, "avg_watts"), avg > 0 else { return nil }
        guard let ftp = cycling?.ftpWatts ?? detail.powerZones?.ftpWatts, ftp > 0 else {
            return Gauge(icon: .power, label: "Power", value: "\(Int(avg.rounded()))", unit: "W avg", valueColor: Color(hex: 0x6FAEFF), dot: 0)
        }
        let top = 1.5
        let edges = [0, 0.55, 0.75, 0.90, 1.05, 1.20, top]
        let bands = zip(edges, edges.dropFirst()).enumerated().map { index, pair in
            Gauge.Band(width: (pair.1 - pair.0) / top, color: zoneColors[index])
        }
        var side: [(String, String)] = []
        if let np = power?.normalizedWatts { side.append(("\(Int(np.rounded()))", "NP")) }
        side.append(("\(Int((avg / ftp * 100).rounded()))%", "of FTP"))
        return Gauge(
            icon: .power, label: measured == nil && cycling?.estimatedPower != nil ? "Power · estimated" : "Power",
            value: "\(Int(avg.rounded()))", unit: "W avg", valueColor: Color(hex: 0x6FAEFF), side: side, bands: bands,
            dot: clamp(avg / ftp / top), tick: power?.normalizedWatts.map { clamp($0 / ftp / top) },
            labels: [.init(at: 0, text: "0"), .init(at: 0.55 / top, text: "Z2"), .init(at: 1 / top, text: "FTP \(Int(ftp.rounded()))"), .init(at: nil, text: "150%")]
        )
    }

    /// Average heart rate on the activity's own zones, shading average → max. Without zones
    /// (hikes, strength) it sits on a plain 70–200 track.
    static func heartRateGauge(_ detail: ActivityDetail) -> Gauge? {
        guard let avg = number(detail, "avg_hr") ?? detail.activity.avgHr, avg > 0 else { return nil }
        let max = number(detail, "max_hr") ?? detail.activity.maxHr
        let zones = detail.heartRateZones?.available == true ? (detail.heartRateZones?.zones ?? []) : []
        let starts = zones.dropFirst().compactMap(\.lower)
        var side: [(String, String)] = []
        if let max { side.append(("\(Int(max.rounded()))", "max")) }

        guard starts.count >= 4 else {
            let (lo, hi) = (70.0, 200.0)
            if let low = chart(detail, "heartrate")?.min, low > 0 { side.append(("\(Int(low.rounded()))", "low")) }
            let position = { (bpm: Double) in clamp((bpm - lo) / (hi - lo)) }
            return Gauge(icon: .heart, label: "Heart rate", value: "\(Int(avg.rounded()))", unit: "bpm avg", side: side,
                         dot: position(avg), tick: max.map(position), range: max.map { position(avg)...position($0) },
                         labels: [.init(at: 0, text: "70"), .init(at: nil, text: "200")])
        }
        if let z2 = detail.heartRateZones?.zone2Pct { side.append(("\(Int(z2.rounded()))%", "in Z2")) }
        let lo = starts[0] - 40
        let hi = Swift.max(starts[3] + 17, (max ?? 0) + 5)
        let edges = [lo] + starts + [hi]
        let position = { (bpm: Double) in clamp((bpm - lo) / (hi - lo)) }
        let bands = zip(edges, edges.dropFirst()).enumerated().map { index, pair in
            Gauge.Band(width: (pair.1 - pair.0) / (hi - lo), color: zoneColors[index])
        }
        return Gauge(icon: .heart, label: "Heart rate", value: "\(Int(avg.rounded()))", unit: "bpm avg", side: side,
                     bands: bands, dot: position(avg), tick: max.map(position), range: max.map { position(avg)...position($0) },
                     labels: [.init(at: 0, text: "\(Int(lo))"), .init(at: position(starts[0]), text: "Z2 \(Int(starts[0]))"),
                              .init(at: position(starts[2]), text: "Z4 \(Int(starts[2]))"), .init(at: nil, text: "\(Int(hi))")])
    }

    /// Average pace on the training paces from VDOT (slow left, fast right), with a tick at the
    /// best 1 km. Without paces the track is plain, 7:30 → 4:30.
    static func paceGauge(_ detail: ActivityDetail, paces: RunningPaces.Paces.Zones?) -> Gauge? {
        guard case .text(let text)? = detail.stats.first(where: { $0.key == "avg_pace" })?.value,
              let avg = seconds(text) else { return nil }
        let bestKm = detail.bestEfforts?.efforts.first { $0.label == "1K" }.map(\.durationS)
        var side: [(String, String)] = []
        if let bestKm { side.append((paceText(bestKm), "best 1 km")) }

        guard let easy = paces?.easy, let marathon = paces?.marathon?.paceS, let threshold = paces?.threshold?.paceS,
              let interval = paces?.interval?.paceS, let repetition = paces?.repetition?.paceS else {
            let (slow, fast) = (450.0, 270.0)
            let position = { (s: Double) in clamp((slow - s) / (slow - fast)) }
            return Gauge(icon: .pace, label: "Pace", value: text, unit: "/km avg", valueColor: .run, side: side,
                         dot: position(avg), tick: bestKm.map(position),
                         labels: [.init(at: 0, text: "7:30"), .init(at: nil, text: "4:30")])
        }
        let slow = (Swift.max(easy.toS + 40, avg + 20) / 30).rounded(.up) * 30
        let fast = repetition - 14
        let edges = [slow, easy.toS, easy.fromS, (marathon + threshold) / 2, (threshold + interval) / 2, (interval + repetition) / 2, fast]
        let names = ["Recovery", "Easy", "Marathon", "Threshold", "Interval", "Repetition"]
        let position = { (s: Double) in clamp((slow - s) / (slow - fast)) }
        let bands = zip(edges, edges.dropFirst()).enumerated().map { index, pair in
            Gauge.Band(width: (pair.0 - pair.1) / (slow - fast), color: zoneColors[index])
        }
        let zone = edges.indices.dropLast().first { avg <= edges[$0] && avg > edges[$0 + 1] } ?? (avg > slow ? 0 : names.count - 1)
        side.append(("≈ \(names[zone])", "pace"))
        return Gauge(icon: .pace, label: "Pace", value: text, unit: "/km avg", valueColor: .run, side: side, bands: bands,
                     dot: position(avg), tick: bestKm.map(position),
                     labels: [.init(at: 0, text: paceText(slow)), .init(at: position(easy.toS), text: "Easy \(paceText(easy.toS))"),
                              .init(at: position(threshold), text: "T \(paceText(threshold))"), .init(at: nil, text: paceText(fast))])
    }

    /// Where the day went on the altitude scale: start, the span covered, the top.
    static func climbGauge(_ detail: ActivityDetail) -> Gauge? {
        guard let climb = number(detail, "elevation_m"), climb >= 20,
              let altitude = chart(detail, "altitude"), let low = altitude.min, let high = altitude.max, high - low >= 15 else { return nil }
        let lo = ((low - 50) / 100).rounded(.down) * 100
        let hi = ((high + 20) / 100).rounded(.up) * 100
        let position = { (m: Double) in clamp((m - lo) / (hi - lo)) }
        let start = altitude.values.first ?? low
        var side: [(String, String)] = [("\(Int(low.rounded())) → \(Int(high.rounded()))", "m")]
        if let km = number(detail, "distance_km"), km >= 1 { side.append(("\(Int((climb / km).rounded()))", "m per km")) }
        return Gauge(icon: .climb, label: "Climb", value: "\(Int(climb.rounded()))", unit: "m up", valueColor: Color(hex: 0xA99CFF), side: side,
                     bands: [.init(width: position(low), color: zoneColors[0]), .init(width: position(high) - position(low), color: .other),
                             .init(width: 1 - position(high), color: zoneColors[0])],
                     dot: position(start), tick: position(high),
                     labels: [.init(at: 0, text: "\(Int(lo))"), .init(at: position(start), text: "start \(Int(start.rounded()))"), .init(at: nil, text: "top \(Int(high.rounded())) m")])
    }

    /// This session's volume against the same lifts last time, lift by lift.
    static func volumeGauge(_ detail: ActivityDetail) -> Gauge? {
        let lifts = detail.strengthDetail?.progression?.exercises.values.filter { $0.previous?.volumeKg != nil } ?? []
        let current = lifts.compactMap { $0.current?.volumeKg }.reduce(0, +)
        let previous = lifts.compactMap { $0.previous?.volumeKg }.reduce(0, +)
        guard previous > 0, current > 0 else { return nil }
        let change = Int(((current - previous) / previous * 100).rounded())
        let top = (Swift.max(current, previous) * 1.2 / 1000).rounded(.up) * 1000
        let tonnes = { (kg: Double) in (kg / 1000).formatted(ActivityFormat.twoDecimals) }
        return Gauge(icon: .volume, label: "Volume vs last time", value: change > 0 ? "+\(change)" : "\(change)", unit: "%", valueColor: .strength,
                     side: [("\(tonnes(previous)) t", "last time"), ("same \(lifts.count)", lifts.count == 1 ? "lift" : "lifts")],
                     dot: current / top, tick: previous / top, range: 0...(current / top),
                     labels: [.init(at: 0, text: "0"), .init(at: previous / top, text: "last"), .init(at: nil, text: "\(Int(top / 1000)) t")])
    }

    // MARK: Session read

    struct SessionReadCard {
        let badge: String?
        let tone: String?
        let headline: String
        let signals: [ActivityDetail.Analysis.SessionRead.Signal]
        let nextTime: String?
    }

    /// Hidden when it would only repeat the win strip.
    static func sessionRead(_ detail: ActivityDetail) -> SessionReadCard? {
        guard let read = detail.analysis?.sessionRead, let headline = read.verdict?.headline?.nilIfEmpty else { return nil }
        if headline == detail.win?.headline { return nil }
        let signals = (read.signals ?? []).filter { $0.value?.nilIfEmpty != nil }
        return SessionReadCard(badge: read.verdict?.badge, tone: read.verdict?.tone, headline: headline,
                               signals: Array(signals.prefix(4)), nextTime: read.nextTime?.nilIfEmpty)
    }

    // MARK: Charts

    struct Series: Equatable {
        struct Point: Equatable {
            let x: Double
            /// 0...1 so two units share one chart.
            let y: Double
            let raw: Double
        }
        let unit: String
        let points: [Point]
        /// Normalised position of the average, for the dashed line.
        var average: Double?
    }

    struct ChartTab: Equatable {
        let key: String
        let title: String
        let color: Color
        let area: Series?
        let heartRate: Series?
        var averageText: String?
    }

    struct ChartSet: Equatable {
        let title: String
        let tabs: [ChartTab]
        let duration: Double
        let compact: Bool

        /// Round marks (0:00, 10:00, 20:00…) and the end, in minutes.
        var ticks: [Double] {
            let step = [5.0, 10, 15, 20, 30, 60, 90, 120, 180].first { duration / $0 <= 3.5 } ?? 240
            let marks = stride(from: 0, to: duration - step * 0.4, by: step)
            return Array(marks) + [duration]
        }
    }

    /// The tabs a sport gets, in order, from the streams that have something in them.
    static func chartSet(_ detail: ActivityDetail) -> ChartSet? {
        let sport = ActivityFormat.sport(detail.activity)
        let keys: [String] = switch sport {
        case .ride: ["watts", "heartrate", "cadence", "speed"]
        case .run: ["pace", "heartrate", "altitude", "watts"]
        case .hike, .walk: ["altitude", "heartrate", "speed"]
        default: ["heartrate"]
        }
        let hrChart = usable(chart(detail, "heartrate"))
        let heartRate = hrChart.map { normalize($0, band: 0.15...1, smoothing: 2) }
        var tabs: [ChartTab] = []
        for key in keys {
            guard let source = usable(chart(detail, key)) else { continue }
            if key == "heartrate" {
                tabs.append(ChartTab(key: key, title: "Heart rate", color: heartRateColor,
                                     area: normalize(source, band: 0.05...0.95, smoothing: 2, floorAtZero: false), heartRate: nil,
                                     averageText: number(detail, "avg_hr").map { "avg \(Int($0.rounded())) bpm" }))
                continue
            }
            if key == "altitude", let low = source.min, let high = source.max, high - low < 15 { continue }
            let color: Color = key == "altitude" ? .other : (key == "pace" ? .run : sport.color)
            let series: Series = switch key {
            // Faster is up; walk breaks and stops would flatten the rest, so they're clipped.
            case "pace": normalize(source, band: 0...0.8, smoothing: 3, invert: true, clip: paceClip(source))
            case "watts": normalize(source, band: 0...0.8, smoothing: 4, floorAtZero: true, clip: 0...(source.values.sorted().percentile(0.99) ?? 2000))
            case "cadence", "speed": normalize(source, band: 0...0.8, smoothing: 3, floorAtZero: true)
            default: normalize(source, band: 0...0.8, smoothing: 1, floorAtZero: false)
            }
            tabs.append(ChartTab(key: key, title: tabTitle(key), color: color, area: series, heartRate: heartRate, averageText: averageText(detail, key)))
        }
        guard !tabs.isEmpty else { return nil }
        let minutes = number(detail, "moving_time_min") ?? detail.activity.durationMin
        let duration = max(detail.charts.flatMap { $0.points.map(\.t) }.max() ?? 0, minutes ?? 0)
        guard duration > 0 else { return nil }
        let compact = tabs.count == 1 && tabs[0].key == "heartrate"
        let first = tabs[0]
        let title = compact ? "Heart rate" : (heartRate != nil && first.key != "heartrate" ? "\(first.title) & heart rate" : first.title)
        return ChartSet(title: title, tabs: tabs, duration: duration, compact: compact)
    }

    private static func tabTitle(_ key: String) -> String {
        switch key {
        case "watts": "Power"
        case "pace": "Pace"
        case "altitude": "Elevation"
        case "cadence": "Cadence"
        case "speed": "Speed"
        default: key.capitalized
        }
    }

    private static func averageText(_ detail: ActivityDetail, _ key: String) -> String? {
        switch key {
        case "watts":
            let power = detail.cycling?.power ?? detail.cycling?.estimatedPower
            let avg = power?.avgWatts ?? number(detail, "avg_watts")
            return avg.map { a in "avg \(Int(a.rounded())) W" + (power?.normalizedWatts.map { " · NP \(Int($0.rounded())) W" } ?? "") }
        case "pace":
            if case .text(let text)? = detail.stats.first(where: { $0.key == "avg_pace" })?.value { return "avg \(text) /km · faster is up" }
            return nil
        case "altitude":
            return chart(detail, "altitude").flatMap { c in c.min.flatMap { lo in c.max.map { "\(Int(lo.rounded())) → \(Int($0.rounded())) m" } } }
        case "cadence": return averageCadence(detail).map { "avg \(Int($0.rounded())) rpm" }
        case "speed": return number(detail, "avg_speed_kmh").map { "avg \($0.formatted(ActivityFormat.oneDecimal)) km/h" }
        default: return nil
        }
    }

    /// Pace clipped to a sensible running window around the median.
    private static func paceClip(_ chart: ActivityDetail.Chart) -> ClosedRange<Double> {
        let median = chart.values.sorted().percentile(0.5) ?? 6
        return Swift.max(2.5, median - 1.5)...(median + 2.5)
    }

    /// Value text for the scrub pill.
    static func scrubValue(_ key: String, _ raw: Double) -> String {
        switch key {
        case "pace": "\(paceText(raw * 60)) /km"
        case "watts": "\(Int(raw.rounded())) W"
        case "altitude": "\(Int(raw.rounded())) m"
        case "cadence": "\(Int(raw.rounded())) rpm"
        case "speed": "\(raw.formatted(ActivityFormat.oneDecimal)) km/h"
        default: "\(Int(raw.rounded())) bpm"
        }
    }

    /// The sample nearest to `minute`.
    static func nearest(_ series: Series?, at minute: Double) -> Series.Point? {
        guard let points = series?.points, !points.isEmpty else { return nil }
        var low = 0, high = points.count - 1
        while low < high {
            let mid = (low + high) / 2
            if points[mid].x < minute { low = mid + 1 } else { high = mid }
        }
        if low > 0, abs(points[low - 1].x - minute) < abs(points[low].x - minute) { return points[low - 1] }
        return points[low]
    }

    private static func usable(_ chart: ActivityDetail.Chart?) -> ActivityDetail.Chart? {
        guard let chart, (chart.values.max() ?? 0) > 0, chart.values.count >= 2 else { return nil }
        return chart
    }

    static func chart(_ detail: ActivityDetail, _ key: String) -> ActivityDetail.Chart? {
        detail.charts.first { $0.key == key }
    }

    /// Scales a stream into `band` of the 0...1 chart, keeping raw values for the scrub pill.
    static func normalize(_ chart: ActivityDetail.Chart, band: ClosedRange<Double>, smoothing: Int = 0,
                          floorAtZero: Bool = false, invert: Bool = false, clip: ClosedRange<Double>? = nil) -> Series {
        let raw = chart.points.compactMap { point in point.y.map { (t: point.t, y: $0) } }
        let clipped = raw.map { sample in (t: sample.t, y: clip.map { Swift.min(Swift.max(sample.y, $0.lowerBound), $0.upperBound) } ?? sample.y) }
        let smoothed = clipped.indices.map { index in
            let window = clipped[Swift.max(0, index - smoothing)...Swift.min(clipped.count - 1, index + smoothing)]
            return window.map(\.y).reduce(0, +) / Double(window.count)
        }
        let low = floorAtZero ? 0 : (smoothed.min() ?? 0)
        let span = Swift.max((smoothed.max() ?? 1) - low, invert ? 0.01 : 1)
        let scale = { (y: Double) -> Double in
            let fraction = (y - low) / span
            return band.lowerBound + (invert ? 1 - fraction : fraction) * (band.upperBound - band.lowerBound)
        }
        let points = smoothed.indices.map { Series.Point(x: raw[$0].t, y: scale(smoothed[$0]), raw: raw[$0].y) }
        let values = clipped.map(\.y)
        let average = values.isEmpty ? nil : scale(values.reduce(0, +) / Double(values.count))
        return Series(unit: chart.unit ?? chart.label, points: points, average: average)
    }

    // MARK: Zones

    struct ZoneRow: Equatable {
        let name: String
        let range: String
        let minutes: Double
        let pct: Double
        let color: Color
        let highlight: Bool
    }

    /// Zone rows, with a tail of near-empty zones folded into one "Z4+" row.
    static func zoneRows(_ zones: ActivityDetail.Zones?, unit: String) -> [ZoneRow] {
        guard zones?.available == true, let list = zones?.zones, !list.isEmpty else { return [] }
        var rows = list.enumerated().map { index, zone in
            ZoneRow(name: "Z\(index + 1)", range: zone.range ?? "", minutes: zone.minutes ?? 0, pct: zone.pct ?? 0,
                    color: zoneColors[min(index, zoneColors.count - 1)], highlight: index == 1)
        }
        if let cut = rows.indices.first(where: { index in index >= 3 && rows[index...].allSatisfy { $0.pct < 2 } }), rows.count - cut > 1 {
            let tail = rows[cut...]
            let lower = list[cut].lower.map { "\(Int($0.rounded())) \(unit) and up" } ?? ""
            let merged = ZoneRow(name: "Z\(cut + 1)+", range: lower, minutes: tail.map(\.minutes).reduce(0, +),
                                 pct: tail.map(\.pct).reduce(0, +), color: zoneColors[cut], highlight: false)
            rows = Array(rows[..<cut]) + [merged]
        }
        return rows
    }

    // MARK: Ride load and efforts

    struct LoadTile: Equatable {
        let label: String
        let value: String
        var unit: String?
        var muted = false
    }

    static func loadTiles(_ cycling: ActivityDetail.Cycling?) -> (note: String, tiles: [LoadTile])? {
        guard let cycling, let power = cycling.power ?? cycling.estimatedPower else { return nil }
        let note = cycling.power != nil ? "measured power" : "estimated power ±\(Int(power.errorBandPct ?? 15))%"
        var tiles: [LoadTile] = []
        if let np = power.normalizedWatts { tiles.append(.init(label: "NP", value: "\(Int(np.rounded()))", unit: "W")) }
        if let intensity = power.intensityFactor { tiles.append(.init(label: "IF", value: String(format: "%.2f", intensity))) }
        if let tss = power.tss { tiles.append(.init(label: "TSS", value: "\(Int(tss.rounded()))")) }
        if let vi = power.variabilityIndex { tiles.append(.init(label: "VI", value: String(format: "%.2f", vi))) }
        if let work = power.workKj { tiles.append(.init(label: "Work", value: "\(Int(work.rounded()))", unit: "kJ")) }
        if let decoupling = cycling.decoupling {
            if decoupling.available == true, let pct = decoupling.decouplingPct {
                tiles.append(.init(label: "HR drift", value: String(format: "%.1f", pct), unit: "%"))
            } else if let reason = decoupling.reasonLabel {
                tiles.append(.init(label: "HR drift", value: reason.replacingOccurrences(of: "Shorter than ", with: "< ").replacingOccurrences(of: " minutes", with: " min"), muted: true))
            }
        }
        return tiles.isEmpty ? nil : (note, tiles)
    }

    /// "5:24" from min/km, or from seconds per km.
    static func paceText(_ secondsPerKm: Double) -> String {
        let total = Int(secondsPerKm.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    static func seconds(_ pace: String) -> Double? {
        let parts = pace.split(separator: ":").compactMap { Double($0) }
        return parts.count == 2 ? parts[0] * 60 + parts[1] : nil
    }

    // MARK: Lifts

    struct LiftRow: Identifiable {
        let id: String
        let name: String
        let sets: [String]
        let badge: (text: String, tone: String)?
        let hint: (lead: String?, action: String)?
        let series: [Double]
    }

    static func liftRows(_ detail: ActivityDetail) -> [LiftRow] {
        guard let exercises = detail.strengthDetail?.session?.exercises else { return [] }
        let progression = detail.strengthDetail?.progression?.exercises ?? [:]
        let signals = detail.analysis?.sessionRead?.signals ?? []
        return exercises.map { exercise in
            let lift = progression.values.first { $0.exerciseName == exercise.exerciseName }
            let sets = exercise.sets.filter { $0.isWarmup != true }.map { set in
                let load = set.weightKg.flatMap { $0 > 0 ? $0.formatted(ActivityFormat.upToOneDecimal) : nil } ?? "BW"
                return set.reps.map { "\(load)×\($0)" } ?? load
            }
            let series = signals.first { $0.label.hasPrefix(exercise.exerciseName) }?.series?.compactMap { $0 } ?? []
            return LiftRow(id: exercise.id, name: shortName(exercise.exerciseName), sets: sets,
                           badge: lift.flatMap(badge), hint: lift?.nextHint.flatMap(hint), series: series.count >= 3 ? series : [])
        }
    }

    private static func shortName(_ name: String) -> String {
        name.replacingOccurrences(of: " Press", with: "", options: .anchored.union(.backwards))
    }

    /// "↑ e1RM +3.2 kg", "↓ 2 reps", "= same", "PR".
    static func badge(_ lift: ActivityDetail.StrengthDetail.Progression.Lift) -> (text: String, tone: String)? {
        if lift.isPr == true { return ("PR", "pr") }
        guard let direction = lift.direction else { return nil }
        let delta = lift.delta ?? 0
        if direction == "same" { return ("= same", "same") }
        let arrow = direction == "up" ? "↑" : "↓"
        let tone = direction == "up" ? "good" : "warn"
        guard abs(delta) >= 0.05 else { return ("\(arrow) \(direction)", tone) }
        let amount = abs(delta)
        switch lift.metric {
        case "e1rm": return ("\(arrow) e1RM \(delta > 0 ? "+" : "−")\(amount.formatted(ActivityFormat.upToOneDecimal)) kg", tone)
        case "reps": return ("\(arrow) \(Int(amount.rounded())) reps", tone)
        default: return ("\(arrow) \(delta > 0 ? "+" : "−")\(amount.formatted(ActivityFormat.upToOneDecimal)) kg", tone)
        }
    }

    /// "Every set at 62.5 kg × 8 — try 65 kg next time." → lead + action.
    static func hint(_ text: String) -> (lead: String?, action: String)? {
        let parts = text.components(separatedBy: " — ")
        if parts.count == 2 {
            return (parts[0], parts[1].replacingOccurrences(of: " next time", with: "").trimmingCharacters(in: CharacterSet(charactersIn: ". ")))
        }
        return text.nilIfEmpty.map { (nil, $0.trimmingCharacters(in: CharacterSet(charactersIn: ". "))) }
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

    // MARK: Route

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

    /// Strava activities have numeric ids; manual ones don't link anywhere.
    static func stravaURL(_ id: String) -> URL? {
        guard !id.isEmpty, id.allSatisfy(\.isNumber) else { return nil }
        return URL(string: "https://www.strava.com/activities/\(id)")
    }

    private static func clamp(_ value: Double) -> Double { Swift.min(Swift.max(value, 0), 1) }
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
