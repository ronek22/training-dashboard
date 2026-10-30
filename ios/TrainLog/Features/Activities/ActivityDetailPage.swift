import CoreLocation
import SwiftUI

/// The D2 page from `GET /activities/{id}` (docs/design/artboards/iOSActivityDetailV3.dc.html):
/// header text and visual, the metric grid and each section's numbers. Pure, so it can be tested.
extension ActivityDetailFormat {
    // MARK: Header

    struct Fact: Equatable {
        let value: String
        let label: String
        var color: Color = .ink
    }

    struct Header: Equatable {
        var kicker: String
        var kickerColor: Color
        /// The kicker is a place: white with a location glyph.
        var isPlace = false
        let title: String
        var big: (value: String, unit: String, metric: Metric)?
        var dateLine: String
        var facts: [Fact] = []

        static func == (lhs: Header, rhs: Header) -> Bool {
            lhs.kicker == rhs.kicker && lhs.title == rhs.title && lhs.dateLine == rhs.dateLine && lhs.facts == rhs.facts
                && lhs.big?.value == rhs.big?.value && lhs.big?.unit == rhs.big?.unit && lhs.isPlace == rhs.isPlace
        }
    }

    static func tint(_ sport: Sport) -> Color {
        switch sport {
        case .ride: Color(hex: 0x6FAEFF)
        case .run: Metric.pace.color
        case .strength: Metric.volume.color
        case .mobility, .walk: .mobility
        default: Metric.power.color
        }
    }

    /// From the list row alone (loading state), then refined once the detail lands.
    static func header(_ activity: ActivitySummary, detail: ActivityDetail? = nil, place: String? = nil) -> Header {
        let sport = ActivityFormat.sport(activity)
        let indoor = detail.map(isIndoorRide) ?? (activity.type == "VirtualRide")
        let manual = detail.map { !hasStreams($0) && stravaURL(activity.id) == nil } ?? false
        var header = Header(kicker: kicker(activity, detail: detail, indoor: indoor, manual: manual), kickerColor: tint(sport),
                            title: activity.title, dateLine: dateLine(activity, detail: detail, indoor: indoor))
        if let place = (detail?.mountainRegion.map(regionName) ?? place)?.nilIfEmpty, detail.flatMap(route) != nil {
            header.kicker = place
            header.kickerColor = .ink
            header.isPlace = true
        }
        let km = detail.flatMap { number($0, "distance_km") } ?? activity.distanceKm
        if sport == .strength {
            if let kg = detail?.strengthDetail?.session?.totalVolumeKg ?? nil, kg > 0 {
                header.big = ((kg / 1000).formatted(ActivityFormat.twoDecimals), "t", .volume)
            }
        } else if [.ride, .run, .hike, .walk].contains(sport), let km, km >= 0.1 {
            header.big = (km.formatted(indoor || manual ? ActivityFormat.oneDecimal : ActivityFormat.twoDecimals), "km", .distance)
        } else {
            if let minutes = detail.flatMap({ number($0, "moving_time_min") }) ?? activity.durationMin {
                header.big = minutes >= 60 ? (String(format: "%d:%02d", Int(minutes) / 60, Int(minutes.rounded()) % 60), "h", .time)
                                           : (ActivityFormat.clock(minutes), "min", .time)
            }
        }
        if let detail { header.facts = facts(detail, sport: sport, indoor: indoor) }
        return header
    }

    static func regionName(_ key: String) -> String {
        key.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private static func kicker(_ activity: ActivitySummary, detail: ActivityDetail?, indoor: Bool, manual: Bool) -> String {
        let sport = ActivityFormat.sport(activity)
        if manual { return "\(ActivityFormat.typeLabel(activity)) · logged by hand" }
        switch sport {
        case .ride where indoor:
            return ["Indoor ride", platform(activity)].compactMap { $0 }.joined(separator: " · ")
        case .strength:
            // "Workout A · Upper Chest" already says what it was for.
            if let focus = activity.title.components(separatedBy: " · ").dropFirst().first?.nilIfEmpty {
                return "Strength · " + capitalized(focus.lowercased())
            }
            let exercises = detail?.strengthDetail?.session?.exercises.map { ($0.exerciseName, $0.workSetCount ?? $0.sets.count) } ?? []
            let top = MuscleSummary(exercises).counts.first.map { $0.muscle.label.lowercased() }
            return ["Strength", top.map { $0.prefix(1).uppercased() + $0.dropFirst() }].compactMap { $0 }.joined(separator: " · ")
        case .ride, .run, .hike, .walk:
            return [ActivityFormat.typeLabel(activity), activity.workoutIntentLabel].compactMap { $0 }.joined(separator: " · ")
        default:
            return [ActivityFormat.typeLabel(activity), stravaURL(activity.id) == nil ? nil : "Strava"].compactMap { $0 }.joined(separator: " · ")
        }
    }

    /// "Wed 9 Sep · 20:49–22:28 · logged in TrainLog", "Thu 29 Oct · FTP 215 W".
    private static func dateLine(_ activity: ActivitySummary, detail: ActivityDetail?, indoor: Bool) -> String {
        var parts = [ActivityFormat.longDay(activity.date)]
        if let recorded = activity.recordedStrengthSession {
            if let start = recorded.startedAt.flatMap(clockTime), let end = recorded.completedAt.flatMap(clockTime) { parts.append("\(start)–\(end)") }
            parts.append("logged in TrainLog")
        } else if let detail {
            if indoor, detail.cycling?.power != nil, let ftp = detail.cycling?.ftpWatts { parts.append("FTP \(Int(ftp.rounded())) W") }
            else if detail.runDynamics != nil { parts.append("HealthFit") }
        }
        return parts.joined(separator: " · ")
    }

    /// "2026-10-26T20:49:33+01:00" → "20:49".
    static func clockTime(_ iso: String) -> String? {
        guard let t = iso.split(separator: "T").last, t.count >= 5 else { return nil }
        return String(t.prefix(5))
    }

    private static func facts(_ detail: ActivityDetail, sport: Sport, indoor: Bool) -> [Fact] {
        let climb = number(detail, "elevation_m").flatMap { $0 >= 10 ? Int($0.rounded()) : nil }
        switch sport {
        case .run:
            return [detail.activity.workoutIntentLabel.map { Fact(value: $0, label: "Intent") },
                    climb.map { Fact(value: "+\($0) m", label: "Climb", color: Metric.elevation.color) }].compactMap { $0 }
        case .ride where !indoor:
            return [Fact(value: "Outdoor", label: "Ride"), climb.map { Fact(value: "+\($0) m", label: "Climb", color: Metric.elevation.color) }].compactMap { $0 }
        case .hike, .walk:
            let top = chart(detail, "altitude")?.max.flatMap { $0 >= 300 ? Int($0.rounded()) : nil }
            return [climb.map { Fact(value: "+\($0) m", label: "Ascent", color: Metric.elevation.color) }, top.map { Fact(value: "\($0) m", label: "Top") }].compactMap { $0 }
        default:
            return []
        }
    }

    // MARK: Header visual

    enum Visual {
        case route([CLLocationCoordinate2D], fractions: [Double], legend: (low: String, high: String))
        case trace(Trace)
        case muscles(MuscleSummary)
        case none
    }

    static func visual(_ detail: ActivityDetail) -> Visual {
        let sport = ActivityFormat.sport(detail.activity)
        if sport == .strength {
            let exercises = detail.strengthDetail?.session?.exercises.map { ($0.exerciseName, $0.workSetCount ?? $0.sets.count) } ?? []
            let summary = MuscleSummary(exercises)
            return summary.counts.isEmpty ? (trace(detail).map(Visual.trace) ?? .none) : .muscles(summary)
        }
        if let coordinates = route(detail) {
            let key: String? = switch sport {
            case .run: "pace"
            case .ride: "speed"
            case .hike, .walk: "altitude"
            default: nil
            }
            let legend = key == "altitude" ? ("Lower", "Higher") : ("Slower", "Faster")
            let fractions = key.flatMap { routeFractions(detail, key: $0, coordinates: coordinates) } ?? Array(repeating: 0.5, count: coordinates.count)
            return .route(coordinates, fractions: fractions, legend: legend)
        }
        return trace(detail).map(Visual.trace) ?? .none
    }

    /// Each route point's place on the colour scale (0 slow/low … 1 fast/high), from the stream at
    /// the same share of the distance, clamped to the 10th–90th percentile.
    static func routeFractions(_ detail: ActivityDetail, key: String, coordinates: [CLLocationCoordinate2D]) -> [Double]? {
        guard let stream = usable(detail, key) else { return nil }
        let samples = stream.points.compactMap { point -> (x: Double, y: Double)? in
            guard let y = point.y, let x = point.x else { return nil }
            return (x, y)
        }
        guard samples.count >= 2, let end = samples.last?.x, end > 0 else { return nil }
        let smoothed = smooth(samples.map(\.y), window: 2)
        var distances = [0.0]
        for index in 1..<coordinates.count {
            let a = CLLocation(latitude: coordinates[index - 1].latitude, longitude: coordinates[index - 1].longitude)
            let b = CLLocation(latitude: coordinates[index].latitude, longitude: coordinates[index].longitude)
            distances.append(distances[index - 1] + a.distance(from: b))
        }
        let total = Swift.max(distances.last ?? 1, 1)
        var cursor = 0
        let values = distances.map { distance -> Double in
            let km = distance / total * end
            while cursor < samples.count - 1, samples[cursor + 1].x <= km { cursor += 1 }
            return smoothed[cursor]
        }
        let sorted = smoothed.sorted()
        guard let p10 = sorted.percentile(0.1), let p90 = sorted.percentile(0.9), p90 > p10 else { return values.map { _ in 0.5 } }
        // Pace is minutes per km: smaller is faster, so it runs the other way.
        return values.map { key == "pace" ? clamp((p90 - $0) / (p90 - p10)) : clamp(($0 - p10) / (p90 - p10)) }
    }

    struct Trace: Equatable {
        struct Point: Equatable {
            let x: Double
            let y: Double
            let zone: Int
        }
        let points: [Point]
        /// Heart rate behind a power trace, 0...1 on its own scale.
        var heartRate: [Point] = []
        var guide: (y: Double, label: String)?
        var average: (y: Double, label: String)?

        static func == (lhs: Trace, rhs: Trace) -> Bool {
            lhs.points == rhs.points && lhs.heartRate == rhs.heartRate && lhs.guide?.label == rhs.guide?.label && lhs.average?.label == rhs.average?.label
        }
    }

    /// Indoor rides draw watts on the FTP zones; everything else heart rate on its zones.
    static func trace(_ detail: ActivityDetail) -> Trace? {
        let ftp = detail.cycling?.ftpWatts ?? detail.powerZones?.ftpWatts
        if ActivityFormat.sport(detail.activity) == .ride, detail.cycling?.power != nil, let ftp, ftp > 0, let watts = usable(detail, "watts") {
            let lowers = [0.55, 0.75, 0.90, 1.05, 1.20, 1.50].map { $0 * ftp }
            let avg = detail.cycling?.power?.avgWatts ?? number(detail, "avg_watts")
            var trace = traceLine(watts, lowers: lowers, window: 4, average: avg, unit: "W", guideLabel: "Zone 2 · \(Int(lowers[0].rounded())) W")
            if let hr = usable(detail, "heartrate") {
                let values = smooth(hr.values, window: 4)
                let (lo, hi) = (values.min() ?? 0, values.max() ?? 1)
                let span = Swift.max(hi - lo, 1)
                let duration = Swift.max(hr.points.last?.t ?? 1, 0.01)
                trace?.heartRate = zip(hr.points.filter { $0.y != nil }, values).map { point, value in
                    Trace.Point(x: point.t / duration, y: 0.45 + (value - lo) / span * 0.5, zone: 0)
                }
            }
            return trace
        }
        guard let hr = usable(detail, "heartrate") else { return nil }
        let lowers = (detail.heartRateZones?.available == true ? detail.heartRateZones?.zones ?? [] : []).dropFirst().compactMap(\.lower)
        return traceLine(hr, lowers: lowers.isEmpty ? [130, 150, 165, 180] : lowers, window: 1,
                         average: number(detail, "avg_hr"), unit: "bpm", guideLabel: lowers.first.map { "Zone 2 · \(Int($0)) bpm" })
    }

    private static func traceLine(_ stream: ActivityDetail.Chart, lowers: [Double], window: Int, average: Double?, unit: String, guideLabel: String?) -> Trace? {
        let raw = stream.points.filter { $0.y != nil }
        guard raw.count >= 2 else { return nil }
        let values = smooth(raw.compactMap(\.y), window: window)
        let sorted = values.sorted()
        let lo = sorted.percentile(0.02) ?? 0
        let hi = sorted.last ?? 1
        let span = Swift.max(hi - lo, 1)
        let (bottom, top) = (lo - span * 0.12, hi + span * 0.1)
        let scale = { (v: Double) in clamp((v - bottom) / (top - bottom)) }
        let duration = Swift.max(raw.last?.t ?? 1, 0.01)
        let points = zip(raw, values).map { point, value in
            Trace.Point(x: point.t / duration, y: scale(value), zone: zoneIndex(value, lowers: lowers))
        }
        var trace = Trace(points: points)
        if let guide = lowers.first, guide < top, guide > bottom, let guideLabel { trace.guide = (scale(guide), guideLabel) }
        if let average { trace.average = (scale(average), "avg \(Int(average.rounded())) \(unit)") }
        return trace
    }

    /// 0 for Zone 1; `lowers` are the lower bounds of Zone 2 upwards.
    static func zoneIndex(_ value: Double, lowers: [Double]) -> Int {
        lowers.lastIndex { value >= $0 }.map { $0 + 1 } ?? 0
    }

    // MARK: Metric grid

    struct Cell: Equatable {
        let label: String
        let parts: [(value: String, unit: String)]
        let metric: Metric
        var status: (tone: StatusTone, text: String)?
        var info = false

        static func == (lhs: Cell, rhs: Cell) -> Bool {
            lhs.label == rhs.label && lhs.parts.map { $0.value + $0.unit } == rhs.parts.map { $0.value + $0.unit }
                && lhs.status?.text == rhs.status?.text && lhs.status?.tone == rhs.status?.tone
        }
    }

    /// "43m 36s", "1h 30m", "52m".
    static func durationParts(_ minutes: Double) -> [(value: String, unit: String)] {
        let seconds = Int((minutes * 60).rounded())
        if seconds >= 3600 {
            let total = Int(minutes.rounded())
            return [("\(total / 60)", "h"), ("\(total % 60)", "m")]
        }
        if seconds % 60 == 0 { return [("\(seconds / 60)", "m")] }
        return [("\(seconds / 60)", "m"), ("\(seconds % 60)", "s")]
    }

    static func signal(_ detail: ActivityDetail, _ key: String) -> ActivityDetail.Analysis.SessionRead.Signal? {
        detail.analysis?.sessionRead?.signals?.first { ($0.key ?? "") == key }
    }

    static func capitalized(_ text: String) -> String { text.prefix(1).uppercased() + text.dropFirst() }

    static func grid(_ detail: ActivityDetail) -> [Cell] {
        let activity = detail.activity
        let sport = ActivityFormat.sport(activity)
        let indoor = isIndoorRide(detail)
        let minutes = number(detail, "moving_time_min") ?? activity.durationMin
        let elapsed = number(detail, "elapsed_time_min")
        let stops = elapsed.flatMap { e in minutes.flatMap { e - $0 >= 5 ? (StatusTone.info, withStops(e)) : nil } }
        let time = minutes.map { Cell(label: sport == .strength || sport == .mobility || sport == .other ? "Time" : "Moving time", parts: durationParts($0), metric: .time, status: stops) }
        let hr = heartRateCell(detail, sport: sport)
        let manual = !hasStreams(detail) && stravaURL(activity.id) == nil

        if manual {
            var cells: [Cell] = []
            if var time { time.status = (.info, "Logged by hand"); cells.append(time) }
            if let pace = avgPaceText(detail) { cells.append(Cell(label: "Avg pace", parts: [(pace, "/km")], metric: .pace, status: (.info, "From time and distance"))) }
            return cells + [hr].compactMap { $0 }
        }

        switch sport {
        case .run:
            var pace: Cell?
            if let text = avgPaceText(detail) {
                let read = signal(detail, "pace_at_hr")
                pace = Cell(label: "Avg pace", parts: [(text, "/km")], metric: .pace,
                            status: read.flatMap { s in s.detail.map { (StatusTone(s.tone), paceAtHeartRate($0)) } })
            }
            var runTime = time
            if let intent = activity.workoutIntentLabel { runTime?.status = (.info, "\(intent) run planned") }
            let power = number(detail, "avg_watts").map { Cell(label: "Avg power", parts: [("\(Int($0.rounded()))", "W")], metric: .power, status: (.info, "Running power")) }
            let climb = number(detail, "elevation_m").flatMap { $0 >= 10 ? Cell(label: "Climb", parts: [("\(Int($0.rounded()))", "m")], metric: .elevation) : nil }
            return (power != nil ? [power, pace, runTime, hr] : [runTime, pace, climb, hr]).compactMap { $0 }
        case .ride:
            let speedValue = number(detail, "avg_speed_kmh")
            var speedStatus: (StatusTone, String)?
            if indoor {
                speedStatus = (.info, ["Virtual", world(activity.name)].compactMap { $0 }.joined(separator: ", "))
            } else if let max = number(detail, "max_speed_kmh") ?? chart(detail, "speed")?.max {
                speedStatus = (.info, "Max \(Int(max.rounded())) km/h")
            }
            let speed = speedValue.map { Cell(label: "Avg speed", parts: [($0.formatted(ActivityFormat.oneDecimal), "km/h")], metric: .speed, status: speedStatus) }
            var rideTime = time
            if let execution = detail.workoutExecution, let planned = execution.blocks?.compactMap(\.durationMin).reduce(0, +), planned > 0 {
                let easy = ["recovery", "easy", "endurance"].contains(activity.workoutIntent ?? "")
                rideTime?.status = (.info, "Planned \(Int(planned.rounded())) min" + (easy ? " easy" : ""))
            }
            return [rideTime, speed, powerCell(detail), hr].compactMap { $0 }
        case .hike, .walk:
            let top = chart(detail, "altitude")?.max
            let ascent = number(detail, "elevation_m").map { Cell(label: "Ascent", parts: [("\(Int($0.rounded()))", "m")], metric: .elevation, status: top.map { (.info, "Top \(Int($0.rounded())) m") }) }
            let speed = number(detail, "avg_speed_kmh").map { avg in
                Cell(label: "Avg speed", parts: [(avg.formatted(ActivityFormat.oneDecimal), "km/h")], metric: .speed,
                     status: number(detail, "max_speed_kmh").map { (.info, "Max \($0.formatted(ActivityFormat.oneDecimal)) km/h") })
            }
            return [time, ascent, speed, hr].compactMap { $0 }
        case .strength:
            let session = detail.strengthDetail?.session
            var strengthTime = time
            if let recorded = activity.recordedStrengthSession, let start = recorded.startedAt.flatMap(clockTime), let end = recorded.completedAt.flatMap(clockTime) {
                strengthTime?.status = (.info, "\(start)–\(end)")
            }
            let lifts = session?.exerciseCount ?? session?.exercises.count ?? 0
            let sets = session?.setCount.map { sets in
                Cell(label: "Sets · reps", parts: [("\(sets)", ""), ("·", ""), ("\(session?.repCount ?? 0)", "")], metric: .plain,
                     status: lifts > 0 ? (.info, "\(lifts) \(lifts == 1 ? "lift" : "lifts")") : nil)
            }
            return [strengthTime, volumeChange(detail), sets, hr].compactMap { $0 }
        default:
            let max = number(detail, "max_hr") ?? activity.maxHr
            let maxCell = max.map { m in
                Cell(label: "Max heart rate", parts: [("\(Int(m.rounded()))", "bpm")], metric: .heartRate,
                     status: (.info, "Stayed under \(Int((m / 10).rounded(.down) * 10 + 10))"))
            }
            let cells = [hr, maxCell].compactMap { $0 }
            return cells.isEmpty ? [time].compactMap { $0 } : cells
        }
    }

    /// "2h 47m with stops".
    static func withStops(_ minutes: Double) -> String {
        let text = ActivityFormat.compactDuration(minutes)
        return (text.hasSuffix("m") ? text : text + "m") + " with stops"
    }

    /// "17 s/km slower than 5 similar runs" → "17 s/km slower at this HR".
    static func paceAtHeartRate(_ detail: String) -> String {
        guard let head = detail.components(separatedBy: " than ").first, head != detail else { return capitalized(detail) }
        return capitalized(head) + " at this HR"
    }

    /// "Watopia" from "Zwift - California Dreamin' in Watopia".
    static func world(_ name: String) -> String? {
        guard let range = name.range(of: " in ", options: .backwards) else { return nil }
        let place = name[range.upperBound...].trimmingCharacters(in: .whitespaces)
        return place.isEmpty || place.contains(" ") ? nil : place
    }

    private static func heartRateCell(_ detail: ActivityDetail, sport: Sport) -> Cell? {
        guard let avg = number(detail, "avg_hr") ?? detail.activity.avgHr else { return nil }
        var status: (StatusTone, String)?
        if let cap = signal(detail, "hr_cap"), let text = cap.detail {
            status = (StatusTone(cap.tone), capitalized(text.replacingOccurrences(of: " bpm", with: "")))
        } else if let zones = detail.heartRateZones, zones.available == true, let list = zones.zones, !list.isEmpty {
            let pcts = list.map { $0.pct ?? 0 }
            let top = pcts.indices.max { pcts[$0] < pcts[$1] } ?? 0
            let pct = Int(pcts[top].rounded())
            status = (top <= 1 ? .good : .info, pct >= 97 ? "Zone \(top + 1) throughout" : "\(pct)% in Zone \(top + 1)")
        } else if [.strength, .mobility, .other].contains(sport), let hr = chart(detail, "heartrate"), let low = hr.values.filter({ $0 > 0 }).min(), let high = hr.max {
            status = (.info, "\(Int(low.rounded()))–\(Int(high.rounded())) range")
        } else if let max = number(detail, "max_hr") {
            var text = "Max \(Int(max.rounded()))"
            if let kcal = number(detail, "calories") { text += " · \(Int(kcal.rounded())) kcal" }
            status = (.info, text)
        }
        if [.hike, .walk].contains(sport), let max = number(detail, "max_hr") {
            var text = "Max \(Int(max.rounded()))"
            if let kcal = number(detail, "calories") { text += " · \(Int(kcal.rounded())) kcal" }
            status = (.info, text)
        }
        return Cell(label: "Avg heart rate", parts: [("\(Int(avg.rounded()))", "bpm")], metric: .heartRate, status: status)
    }

    private static func powerCell(_ detail: ActivityDetail) -> Cell? {
        let cycling = detail.cycling
        if let power = cycling?.power, let np = power.normalizedWatts ?? number(detail, "normalized_power") {
            var status: (StatusTone, String)?
            if let execution = detail.workoutExecution, let label = execution.verdictLabel {
                let ratio = execution.ratio.map { " · \(Int(($0 * 100).rounded()))%" } ?? ""
                status = (execution.verdict == "on_target" ? .good : .warn, label + ratio)
            } else if let avg = power.avgWatts {
                status = (.info, "Avg \(Int(avg.rounded())) W")
            }
            return Cell(label: "Normalized power", parts: [("\(Int(np.rounded()))", "W")], metric: .power, status: status, info: true)
        }
        if let estimate = cycling?.estimatedPower, let np = estimate.normalizedWatts {
            let band = Int(estimate.errorBandPct ?? 15)
            return Cell(label: "Est. normalized power", parts: [("~\(Int(np.rounded()))", "W")], metric: .power,
                        status: (.info, (estimate.avgWatts.map { "Avg ~\(Int($0.rounded())) W · " } ?? "") + "±\(band)%"))
        }
        return number(detail, "avg_watts").map { Cell(label: "Avg power", parts: [("\(Int($0.rounded()))", "W")], metric: .power) }
    }

    /// This session's volume against the same lifts last time.
    static func volumeChange(_ detail: ActivityDetail) -> Cell? {
        let lifts = detail.strengthDetail?.progression?.exercises.values.filter { $0.previous?.volumeKg != nil } ?? []
        let current = lifts.compactMap { $0.current?.volumeKg }.reduce(0, +)
        let previous = lifts.compactMap { $0.previous?.volumeKg }.reduce(0, +)
        guard previous > 0, current > 0 else { return nil }
        let change = Int(((current - previous) / previous * 100).rounded())
        return Cell(label: "Vs last time", parts: [(change > 0 ? "+\(change)" : "\(change)", "%")], metric: .volume,
                    status: (change >= 0 ? .good : .warn, "\((previous / 1000).formatted(ActivityFormat.twoDecimals)) t · same \(lifts.count) \(lifts.count == 1 ? "lift" : "lifts")"))
    }

    // MARK: Session read

    struct Read {
        let badge: String?
        let tone: StatusTone
        let headline: String
        var explanation: String?
        var lines: [(tone: StatusTone, text: String, series: [Double])]
        var nextTime: String?
    }

    static func sessionRead(_ detail: ActivityDetail) -> Read? {
        guard let read = detail.analysis?.sessionRead, let headline = read.verdict?.headline?.nilIfEmpty else { return nil }
        let explanation = detail.workoutExecution?.explanation?.nilIfEmpty
            ?? read.wins?.first { $0.headline == headline }?.detail?.nilIfEmpty
            ?? (detail.win?.headline == headline ? detail.win?.detail?.nilIfEmpty : nil)
        var lines: [(StatusTone, String, [Double])] = []
        if let execution = detail.workoutExecution, let block = execution.blocks?.first(where: { $0.targetWatts != nil }),
           let target = block.targetWatts, let np = detail.cycling?.power?.normalizedWatts {
            let zone = execution.inZonePct.map { " · \(Int($0.rounded()))% in zone" } ?? ""
            lines.append((execution.verdict == "on_target" ? .good : .warn, "\(Int(np.rounded())) W vs \(Int(target.rounded())) W target\(zone)", []))
        }
        for signal in read.signals ?? [] {
            guard let value = signal.value?.nilIfEmpty, !["weekly_goal", "power_best", "lifts_moving"].contains(signal.key ?? "") else { continue }
            var label = signal.label
            if label.hasSuffix(" e1RM") { label = shortLift(String(label.dropLast(5))) + " e1RM" } else if (signal.key ?? "").hasPrefix("lift_") { label = shortLift(label) }
            let text = signal.detail.map { "\(label): \(value) · \($0)" } ?? "\(label): \(value)"
            let series = (signal.series ?? []).compactMap { $0 }
            lines.append((StatusTone(signal.tone), text, series.count >= 3 ? series : []))
        }
        return Read(badge: read.verdict?.badge?.nilIfEmpty, tone: StatusTone(read.verdict?.tone), headline: headline,
                    explanation: explanation, lines: Array(lines.prefix(3)),
                    nextTime: read.nextTime?.nilIfEmpty.map { $0.components(separatedBy: ": ").last ?? $0 })
    }

    /// "Barbell Incline Bench Press" → "Incline bench".
    static func shortLift(_ name: String) -> String {
        let trimmed = name.replacingOccurrences(of: "^(Barbell|Dumbbell|Cable|Machine) ", with: "", options: .regularExpression)
            .replacingOccurrences(of: " Press$", with: "", options: .regularExpression)
        return capitalized(trimmed.lowercased())
    }

    // MARK: Splits

    struct SplitRow: Equatable {
        let km: Int
        let pace: String
        let share: Double
        let fastest: Bool
        let heartRate: Int?
        let cadence: Int?
        let power: Int?
    }

    /// Bars run 46–100% from the slowest to the fastest kilometre.
    static func splits(_ detail: ActivityDetail) -> [SplitRow] {
        let splits = detail.runDynamics?.splits.filter { $0.seconds > 0 } ?? []
        guard splits.count >= 2 else { return [] }
        let slowest = splits.map(\.seconds).max() ?? 1
        let fastest = splits.map(\.seconds).min() ?? 1
        return splits.map { split in
            let share = slowest == fastest ? 1 : 0.46 + (slowest - split.seconds) / (slowest - fastest) * 0.54
            return SplitRow(km: split.km, pace: paceText(split.seconds), share: share, fastest: split.seconds == fastest,
                            heartRate: split.heartRate.map { Int($0.rounded()) }, cadence: split.cadenceSpm.map { Int($0.rounded()) },
                            power: split.powerW.map { Int($0.rounded()) })
        }
    }

    static func splitLines(_ rows: [SplitRow]) -> [(tone: StatusTone, text: String)] {
        guard rows.count >= 3 else { return [] }
        var lines: [(StatusTone, String)] = []
        let times = rows.map { Self.seconds($0.pace) ?? 0 }
        if let slowestLast = times.suffix(2).max(), slowestLast < times.dropLast(2).min() ?? 0 {
            lines.append((.good, "Negative split: the last two km were your fastest"))
        } else if let first = times.first, let last = times.last, last > first + 15 {
            lines.append((.warn, "Faded: the last km was \(Int(last - first)) s slower than the first"))
        }
        let hr = rows.compactMap(\.heartRate)
        if hr.count == rows.count, let first = hr.first, let last = hr.last {
            if zip(hr, hr.dropFirst()).allSatisfy({ $0 < $1 }) {
                lines.append((.warn, "Heart rate rose every km, \(first) → \(last) bpm"))
            } else {
                lines.append((.info, "Heart rate \(first) → \(last) bpm"))
            }
        }
        return lines
    }

    // MARK: Running form

    struct FormCell: Equatable {
        let label: String
        let value: String
        let unit: String
        let metric: Metric
        /// 0 low, 1 good / usual, 2 high.
        let step: Int
        /// Against a good range (teal/amber) rather than your usual (grey).
        let ranged: Bool
        let word: String
        let usual: String?

        var good: Bool { ranged && step == 1 }
    }

    static func form(_ detail: ActivityDetail, fitness: RunningFitness.Form?) -> [FormCell] {
        guard let run = detail.runDynamics else { return [] }
        let usual = fitness?.baseline
        let ranges = fitness?.ranges ?? [:]
        func range(_ key: String) -> [Double]? {
            let camel = key.split(separator: "_").enumerated().map { $0 == 0 ? String($1) : $1.capitalized }.joined()
            return (ranges[camel] ?? ranges[key])?.good
        }
        func cell(_ label: String, _ value: Double?, key: String, unit: String, metric: Metric, decimals: Int, usual base: Double?, words: (String, String, String)) -> FormCell? {
            guard let value else { return nil }
            let format = { (v: Double) in decimals == 0 ? "\(Int(v.rounded()))" : String(format: "%.\(decimals)f", v) }
            if let good = range(key), good.count == 2 {
                let step = value < good[0] ? 0 : (value > good[1] ? 2 : 1)
                return FormCell(label: label, value: format(value), unit: unit, metric: metric, step: step, ranged: true,
                                word: [words.0, words.1, words.2][step], usual: base.map(format))
            }
            let step = base.map { value < $0 * 0.98 ? 0 : (value > $0 * 1.02 ? 2 : 1) } ?? 1
            return FormCell(label: label, value: format(value), unit: unit, metric: metric, step: step, ranged: false,
                            word: [words.0, words.1, words.2][step], usual: base.map(format))
        }
        return [
            cell("Cadence", run.cadenceSpm, key: "cadence_spm", unit: "spm", metric: .cadence, decimals: 0, usual: usual?.cadenceSpm, words: ("Low", "Good", "High")),
            cell("Ground contact", run.stanceTimeMs, key: "stance_time_ms", unit: "ms", metric: .time, decimals: 0, usual: usual?.stanceTimeMs, words: ("Short", "Good", "Long")),
            cell("Step length", run.stepLengthM, key: "step_length_m", unit: "m", metric: .distance, decimals: 2, usual: usual?.stepLengthM, words: ("Shorter", "Usual", "Longer")),
            cell("Vert. oscillation", run.verticalOscillationCm, key: "vertical_oscillation_cm", unit: "cm", metric: .elevation, decimals: 1, usual: usual?.verticalOscillationCm, words: ("Low", "Good", "High")),
            cell("Vert. ratio", run.verticalRatioPct, key: "vertical_ratio_pct", unit: "%", metric: .pace, decimals: 1, usual: usual?.verticalRatioPct, words: ("Low", "Good", "High")),
            cell("Power", run.avgPowerW, key: "avg_power_w", unit: "W", metric: .power, decimals: 0, usual: usual?.avgPowerW, words: ("Lower", "Typical", "Higher")),
        ].compactMap { $0 }
    }

    /// One sentence: what's out of range (and whether that's usual for you), then what's good.
    static func formSummary(_ cells: [FormCell]) -> (tone: StatusTone, text: String)? {
        let out = cells.filter { $0.ranged && !$0.good }
        let good = cells.filter(\.good)
        guard !cells.isEmpty else { return nil }
        if out.isEmpty { return (.good, "Every ranged number is in its good range.") }
        var phrases = out.filter { !$0.label.hasPrefix("Vert.") }.map { "\($0.label.lowercased()) is \($0.word.lowercased())" }
        // Oscillation and ratio both high are one thing: bounce.
        let bounce = out.filter { $0.label.hasPrefix("Vert.") }
        if bounce.contains(where: { $0.step == 2 }) { phrases.append("you bounce a little more than ideal") }
        else if !bounce.isEmpty { phrases += bounce.map { "\($0.label.lowercased().replacingOccurrences(of: "vert.", with: "vertical")) is \($0.word.lowercased())" } }
        let usual = out.allSatisfy { cell in
            guard let usual = cell.usual.flatMap(Double.init), let value = Double(cell.value), usual > 0 else { return false }
            return abs(value - usual) / usual < 0.06
        }
        var text = capitalized(phrases.joined(separator: " and "))
        if usual { text += phrases.count == 1 ? ", usual for you" : (phrases.count == 2 ? ", both usual for you" : ", all usual for you") }
        text += "."
        if !good.isEmpty { text += " \(capitalized(good.map { $0.label.lowercased() }.joined(separator: " and "))) \(good.count == 1 ? "is" : "are") good." }
        return (.warn, text)
    }

    // MARK: Comparisons and bests

    static func compared(_ detail: ActivityDetail) -> [Cell] {
        guard let cycling = detail.cycling else { return [] }
        let load = cycling.hrLoad.map { value in
            Cell(label: "Heart-rate load", parts: [("\(Int(value.rounded()))", "")], metric: .heartRate,
                 status: signal(detail, "load")?.detail.map { (($0.hasPrefix("0.") ? StatusTone.good : .info), $0) })
        }
        if let power = cycling.power {
            let best20 = cycling.powerEfforts?.first { $0.durationS == 1200 }
            let best = best20.flatMap { effort in
                effort.watts.map { Cell(label: "Best 20 min", parts: [("\(Int($0.rounded()))", "W")], metric: .power,
                                        status: effort.pctOfBest.map { (.info, "\(Int($0.rounded()))% of your best") }) }
            }
            let intensity = power.intensityFactor.map { factor in
                Cell(label: "Intensity", parts: [(String(format: "%.2f", factor), "IF")], metric: .plain,
                     status: (.info, [power.tss.map { "TSS \(Int($0.rounded()))" }, power.variabilityIndex.map { String(format: "VI %.2f", $0) }].compactMap { $0 }.joined(separator: " · ")))
            }
            let cadence = averageCadence(detail).map { rpm in
                Cell(label: "Cadence", parts: [("\(Int(rpm.rounded()))", "rpm")], metric: .cadence,
                     status: power.workKj.map { (.info, "Work \(Int($0.rounded())) kJ") })
            }
            return [best, load, intensity, cadence].compactMap { $0 }
        }
        let estimate = cycling.estimatedPower
        let tss = estimate?.tss.map { Cell(label: "Est. TSS", parts: [("~\(Int($0.rounded()))", "")], metric: .plain,
                                          status: estimate?.intensityFactor.map { (.info, String(format: "IF ~%.2f", $0)) }) }
        let max = number(detail, "max_hr").map { m -> Cell in
            let zones = detail.heartRateZones?.zones ?? []
            let touched = zones.lastIndex { ($0.pct ?? 0) > 0 }
            return Cell(label: "Max heart rate", parts: [("\(Int(m.rounded()))", "bpm")], metric: .heartRate,
                        status: touched.map { (.info, "Zone \($0 + 1) touched") })
        }
        let climb = number(detail, "elevation_m").map { m -> Cell in
            let perKm = number(detail, "distance_km").map { m / $0 } ?? 0
            return Cell(label: "Climb", parts: [("\(Int(m.rounded()))", "m")], metric: .elevation,
                        status: (.info, perKm < 5 ? "Flat · \(perKm.formatted(ActivityFormat.upToOneDecimal)) m per km" : "\(Int(perKm.rounded())) m per km"))
        }
        return [tss, load, max, climb].compactMap { $0 }
    }

    struct BestRow: Equatable {
        let label: String
        let watts: Int
        let share: Double
        let best: Int?
        let record: Bool
    }

    static func powerBests(_ detail: ActivityDetail) -> [BestRow] {
        (detail.cycling?.powerEfforts ?? []).compactMap { effort in
            guard let watts = effort.watts else { return nil }
            let label = effort.label.replacingOccurrences(of: " sec", with: " s")
            let share = effort.isRecord == true ? 1 : (effort.pctOfBest ?? 0) / 100
            return BestRow(label: label, watts: Int(watts.rounded()), share: Swift.min(share, 1),
                           best: effort.bestWatts.map { Int($0.rounded()) }, record: effort.isRecord == true)
        }
    }

    struct EffortRow: Equatable {
        let label: String
        let pace: String
        let time: String
        let heartRate: Int?
    }

    /// 400 m, 1 km, 1 mile and 5 km when the run has them; otherwise the first four.
    static func bestEfforts(_ detail: ActivityDetail) -> [EffortRow] {
        let all = detail.bestEfforts?.efforts ?? []
        let preferred = all.filter { ["400m", "1K", "1 mile", "5K", "10K"].contains($0.label) }
        return (preferred.count >= 3 ? preferred : all).compactMap { effort in
            guard let pace = effort.metricValue else { return nil }
            let label = effort.label.replacingOccurrences(of: "K", with: " km").replacingOccurrences(of: "([0-9])m$", with: "$1 m", options: .regularExpression)
            return EffortRow(label: label, pace: paceText(pace * 60), time: ActivityFormat.clock(effort.durationS / 60),
                             heartRate: effort.avgHr.map { Int($0.rounded()) })
        }
        .prefix(4).map { $0 }
    }

    // MARK: How it felt

    struct Feel: Equatable {
        let label: String
        let value: Int
        let scale: Int
        let word: String
        let color: Color
    }

    private static let bodyParts = ["knee", "back", "hip", "ankle", "foot", "heel", "shin", "calf", "hamstring", "shoulder", "neck", "elbow", "wrist", "achilles", "itb", "groin"]

    static func feel(_ feedback: ActivityFeedback?) -> [Feel] {
        guard let feedback else { return [] }
        var cells: [Feel] = []
        if let rpe = feedback.rpe {
            let (word, color): (String, Color) = switch rpe {
            case ...2: ("Very easy", .volt)
            case 3: ("Easy", .volt)
            case 4...6: ("Moderate", warn)
            default: ("Hard", Color(hex: 0xFF8B3D))
            }
            cells.append(Feel(label: "Effort", value: rpe, scale: 10, word: word, color: color))
        }
        if let energy = feedback.energy {
            let word = ["Drained", "Low", "OK", "Good", "Great"][Swift.min(Swift.max(energy, 1), 5) - 1]
            cells.append(Feel(label: "Energy", value: energy, scale: 5, word: word, color: energy >= 4 ? .mobility : (energy == 3 ? Color.inkSoft : warn)))
        }
        if let soreness = feedback.muscleSoreness {
            let word = ["None", "Light", "Some", "Sore", "Very sore"][Swift.min(Swift.max(soreness, 1), 5) - 1]
            cells.append(Feel(label: "Soreness", value: soreness, scale: 5, word: word, color: soreness <= 1 ? .mobility : (soreness <= 3 ? warn : bad)))
        }
        if let pain = feedback.painLevel {
            let note = feedback.note?.lowercased() ?? ""
            let part = bodyParts.first { note.contains($0) }.map { $0 == "itb" ? "ITB" : capitalized($0) }
            let word = pain == 0 ? "Pain-free" : (part ?? (pain >= 4 ? "High" : "Mild"))
            cells.append(Feel(label: "Pain", value: pain, scale: 10, word: word, color: painColor(pain)))
        }
        return cells
    }

    /// Win row, unless the session read already says it.
    static func win(_ detail: ActivityDetail) -> ActivityDetail.Win? {
        guard let win = detail.win, let headline = win.headline?.nilIfEmpty else { return nil }
        if detail.analysis?.sessionRead?.verdict?.headline == headline { return nil }
        return win
    }
}
