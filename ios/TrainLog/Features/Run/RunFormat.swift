import SwiftUI

/// Pure logic for the run card, pace guide and after-run sheet (unit-tested).
enum RunFormat {
    /// "6:04" from 364 seconds per km.
    static func pace(_ seconds: Int) -> String {
        "\(seconds / 60):" + String(format: "%02d", seconds % 60)
    }

    static func band(_ band: RunningFitness.Band) -> String {
        "\(pace(band.fromS))–\(pace(band.toS))"
    }

    /// Where a run's average pace sits against the easy band.
    enum Verdict: Equatable {
        case inside, faster, slower
    }

    static func verdict(_ pace: Int, band: RunningFitness.Band) -> Verdict {
        if pace < band.fromS { return .faster }
        if pace > band.toS { return .slower }
        return .inside
    }

    static func verdictText(_ verdict: Verdict) -> String {
        switch verdict {
        case .inside: "Inside your easy band"
        case .faster: "Faster than your easy band"
        case .slower: "Slower than easy, which is fine"
        }
    }

    /// The tape's span: the band in the middle with some room either side, on whole 10 s marks.
    static func tapeRange(_ band: RunningFitness.Band, room: Int = 12) -> ClosedRange<Int> {
        let low = (band.fromS - room) / 10 * 10
        let high = (band.toS + room + 9) / 10 * 10
        return low...high
    }

    /// The run waiting for a felt tap: the newest run, from today or yesterday, not answered here
    /// or on the server, and not dismissed.
    static func pendingFeel(_ runs: [RunningFitness.FeltRun], today: String, answered: Set<String>, dismissed: Set<String>) -> RunningFitness.FeltRun? {
        guard let last = runs.last, last.felt == nil,
              !answered.contains(last.activityId), !dismissed.contains(last.activityId),
              let day = TodayFormat.parse(last.date), let now = TodayFormat.parse(today) else { return nil }
        let age = now.timeIntervalSince(day)
        return age >= 0 && age < 2 * 86_400 ? last : nil
    }

    /// What this tap does to the next easy run, mirroring the server: the last two answers hard
    /// ease the band by 10 s/km; anything else puts it back at the VDOT band.
    static func nextBand(after feel: RunFeel, previous: [RunFeel], current: RunningFitness.Band, easedNow: Int) -> (band: RunningFitness.Band, eased: Int) {
        let base = RunningFitness.Band(fromS: current.fromS - easedNow, toS: current.toS - easedNow)
        let eased = feel == .hard && previous.last == .hard ? 10 : 0
        return (RunningFitness.Band(fromS: base.fromS + eased, toS: base.toS + eased), eased)
    }

    static func nextHeadline(_ feel: RunFeel, verdict: Verdict) -> String {
        switch (feel, verdict) {
        case (.easy, .inside), (.ok, .inside): "Easy, in the band"
        case (.hard, .inside): "In the band, felt hard"
        case (_, .faster): "A bit quick today"
        case (.hard, _): "Felt hard"
        default: "Nice and easy"
        }
    }

    static func nextLine(_ feel: RunFeel, verdict: Verdict) -> String {
        switch (feel, verdict) {
        case (.hard, .inside): "Pace was right, so it's likely sleep, heat or the day. Next one stays easy."
        case (_, .faster): "Next time hold it back to the band, even if it feels slow."
        case (.hard, _): "Take the next one gently; walk breaks are fine."
        default: "That's the whole job."
        }
    }

    /// The Return-to-run step bar's short labels: "1:2", "5:1", "20′", "40′", and "Full" for normal running.
    static func stageShort(_ name: String) -> String {
        if let ratio = name.split(separator: " ").last, ratio.contains(":") { return String(ratio) }
        let digits = name.split(whereSeparator: { !$0.isNumber })
        return digits.last.map { "\($0)′" } ?? "Full"
    }

    /// "5:1" and "4 rounds, after a 5 min walk" for run/walk; "20 min" and "after a 5 min walk" for continuous.
    static func stageHeadline(_ blocks: [RunningFitness.Block]) -> (big: String, line: String) {
        let jogs = blocks.filter(\.isJog)
        let warmup = blocks.first.flatMap { $0.isJog ? nil : $0.minutes }
        let walks = blocks.dropFirst().filter { !$0.isJog }
        let after = warmup.map { "after a \($0) min walk" } ?? ""
        guard let jog = jogs.first else { return ("", "") }
        if let walk = walks.first {
            return ("\(jog.minutes):\(walk.minutes)", "\(jogs.count) rounds, \(after)")
        }
        return ("\(jog.minutes) min", after.prefix(1).uppercased() + after.dropFirst())
    }

    /// The pace zones, slowest first, each with its colour, what a session looks like and when it opens.
    struct Zone: Identifiable {
        let name: String
        let color: Color
        let pace: String
        let use: String
        /// Nil when it's on today; otherwise when it opens.
        let opens: String?
        var id: String { name }
    }

    static func zones(_ paces: RunningFitness.Paces) -> [Zone] {
        let soon: String? = paces.qualityAllowed ? nil : "in 2 weeks"
        let later: String? = paces.qualityAllowed ? nil : "later"
        let zones = paces.zones
        return [
            Zone(name: "Easy", color: .run, pace: band(zones.easy), use: "Most runs, long runs, recovery", opens: nil),
            Zone(name: "Marathon", color: .paceMarathon, pace: pace(zones.marathon.paceS), use: "Steady part of a long run", opens: soon),
            Zone(name: "Threshold", color: .paceThreshold, pace: pace(zones.threshold.paceS), use: "20 min tempo, or 5–6 × 1 km", opens: soon),
            Zone(name: "Interval", color: .paceInterval, pace: pace(zones.interval.paceS), use: "3–5 min reps, equal jog back", opens: later),
            Zone(name: "Repetition", color: .paceRepetition, pace: pace(zones.repetition.paceS), use: "200–400 m reps for form", opens: later),
        ]
    }

    /// "Aug 21" for the felt row.
    static func shortDate(_ iso: String) -> String {
        guard let date = TodayFormat.parse(iso) else { return iso }
        return date.formatted(.dateTime.month(.abbreviated).day().locale(Locale(identifier: "en_US")))
    }

    static func feelColor(_ feel: RunFeel?) -> Color {
        switch feel {
        case .easy: .mobility
        case .ok: Color(hex: 0x5B6375)
        case .hard: .run
        case nil: .clear
        }
    }
}

extension Color {
    /// The pace guide's zone colours: one per pace, kept apart from the sport colours.
    static let paceMarathon = Color(hex: 0xFFC53D)
    static let paceThreshold = Color(hex: 0xFF5A5F)
    static let paceInterval = Color(hex: 0xE04DFF)
    static let paceRepetition = Color(hex: 0x7C9CFF)
}
