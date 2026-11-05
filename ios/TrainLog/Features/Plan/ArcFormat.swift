import Foundation

/// Where a Plan week sits in the winter arc and in a running stall block: the text and segments
/// of the strip under the Plan header (docs/design/artboards/iOSBlockPosition.dc.html).
enum ArcFormat {
    struct Segment: Equatable {
        enum State: Equatable { case past, current, future }
        let lighter: Bool
        let state: State
    }

    struct Strip: Equatable {
        /// The block name, drawn in ink ("Base"); empty when there's no current block.
        let lead: String
        /// "week 3 of 6", "Winter arc starts Mon 16 Nov"…
        let detail: String
        /// What comes next, right-aligned: "Lighter week next".
        let next: String?
        /// One array per block, one segment per week. Empty with no arc.
        let tape: [[Segment]]

        var isPlaceholder: Bool { tape.isEmpty }
    }

    struct StallLine: Equatable {
        let lift: String
        let detail: String
        let filled: Int
        let total: Int
    }

    /// Placeholder segments drawn dashed while there's no arc (about a Nov–Feb arc's length).
    static let placeholderWeeks = 17

    /// nil once the arc is over: the strip hides.
    static func strip(_ blocks: [WinterArc.Block], weekStart: String) -> Strip? {
        guard let first = blocks.first, let last = blocks.last else {
            return Strip(lead: "", detail: "No winter arc yet · set one up on the Mac", next: nil, tape: [])
        }
        guard weekStart <= last.endDate else { return nil }
        let tape = blocks.map { block in
            (0..<block.weeks).map { offset in
                let monday = PlanFormat.addingDays(offset * 7, to: block.startDate)
                return Segment(lighter: block.lighterWeeks.contains(monday),
                               state: monday < weekStart ? .past : monday == weekStart ? .current : .future)
            }
        }
        if weekStart < first.startDate {
            return Strip(lead: "", detail: "Winter arc starts \(ActivityFormat.longDay(first.startDate))",
                         next: "\(first.name) · \(first.weeks) wk", tape: tape)
        }
        guard let index = blockIndex(blocks, weekStart) else {
            // Between two blocks: name the one that comes next.
            let upcoming = blocks.first { $0.startDate > weekStart } ?? last
            return Strip(lead: "", detail: "\(upcoming.name) starts \(ActivityFormat.longDay(upcoming.startDate))",
                         next: "\(upcoming.weeks) wk", tape: tape)
        }
        let block = blocks[index]
        let number = days(from: block.startDate, to: weekStart) / 7 + 1
        let lighter = block.lighterWeeks.contains(weekStart)
        return Strip(lead: block.name, detail: "week \(number) of \(block.weeks)" + (lighter ? " · lighter" : ""),
                     next: next(blocks, block: block, number: number, lighter: lighter, weekStart: weekStart), tape: tape)
    }

    private static func next(_ blocks: [WinterArc.Block], block: WinterArc.Block, number: Int, lighter: Bool, weekStart: String) -> String? {
        let following = PlanFormat.addingDays(7, to: weekStart)
        guard let last = blocks.last, following <= last.endDate else { return "Last week of the arc" }
        guard let index = blockIndex(blocks, following) else { return "Break next" }
        let upcoming = blocks[index]
        if upcoming != block { return "\(upcoming.name) next" }
        if block.lighterWeeks.contains(following) { return "Lighter week next" }
        if lighter { return "Back to \(hours(block.weeklyHours)) h next" }
        let left = block.weeks - number
        return "\(left) week\(left == 1 ? "" : "s") left"
    }

    /// The stall block line for a week, when the block covers it (or is due, on this week).
    static func stall(_ block: StallBlock?, weekStart: String, today: String) -> StallLine? {
        guard let block, block.scope == "block", block.weeks > 0 else { return nil }
        let weekEnd = PlanFormat.addingDays(6, to: weekStart)
        let isCurrent = weekStart == PlanFormat.weekStart(of: today)
        let overlaps = weekStart <= block.endsOn && weekEnd >= block.startedOn
        guard overlaps || (block.due && isCurrent) else { return nil }
        let lift = ActivityDetailFormat.shortLift(block.exerciseName)
        if block.due && isCurrent {
            return StallLine(lift: lift, detail: "\(block.weeks) weeks done · finish it next lift", filled: block.weeks, total: block.weeks)
        }
        let reference = isCurrent ? today : weekEnd
        let number = min(block.weeks, max(1, days(from: block.startedOn, to: reference) / 7 + 1))
        return StallLine(lift: lift, detail: "\(block.label.lowercased()) · week \(number) of \(block.weeks)",
                         filled: number, total: block.weeks)
    }

    // MARK: Sheet

    struct BlockRow: Equatable {
        let title: String
        let mix: String
        let lighter: String?
        let range: String
        let isCurrent: Bool
        let isPast: Bool
    }

    static func rows(_ blocks: [WinterArc.Block], weekStart: String) -> [BlockRow] {
        blocks.map { block in
            let isCurrent = block.startDate <= weekStart && weekStart <= block.endDate
            let number = days(from: block.startDate, to: weekStart) / 7 + 1
            return BlockRow(title: isCurrent ? "\(block.name) · week \(number) of \(block.weeks)" : block.name,
                            mix: "\(mix(block.rideMix)) · \(hours(block.weeklyHours)) h a week",
                            lighter: (block.lighterEvery ?? 0) > 0 ? "Lighter every \(ordinal(block.lighterEvery ?? 0)) week" : nil,
                            range: range(block.startDate, block.endDate),
                            isCurrent: isCurrent, isPast: block.endDate < weekStart)
        }
    }

    /// "Oct 19 – Feb 28 · 19 weeks".
    static func span(_ blocks: [WinterArc.Block]) -> String? {
        guard let first = blocks.first, let last = blocks.last else { return nil }
        let weeks = blocks.reduce(0) { $0 + $1.weeks }
        return "\(range(first.startDate, last.endDate)) · \(weeks) weeks"
    }

    /// "3 Z2 rides", "2 Z2 + 2 sweet spot".
    static func mix(_ mix: WinterArc.RideMix) -> String {
        let parts = [(mix.z2 ?? 0, "Z2"), (mix.sweetSpot ?? 0, "sweet spot"), (mix.vo2 ?? 0, "VO2")].filter { $0.0 > 0 }
        if parts.count == 1, let only = parts.first { return "\(only.0) \(only.1) ride\(only.0 == 1 ? "" : "s")" }
        return parts.map { "\($0.0) \($0.1)" }.joined(separator: " + ")
    }

    static func stallDetail(_ block: StallBlock) -> String {
        block.due ? "\(block.weeks) weeks done · keep it or go back at the next lift" : "Week \(block.week) of \(block.weeks)"
    }

    /// "Oct 19 – Nov 29".
    static func range(_ start: String, _ end: String) -> String {
        "\(monthDay(start)) – \(monthDay(end))"
    }

    // MARK: Tape

    static let segmentGap: CGFloat = 2
    static let blockGap: CGFloat = 6

    /// Each block's width when `counts` weeks share `width`: every week segment is equally wide.
    static func blockWidths(_ counts: [Int], width: CGFloat) -> [CGFloat] {
        let weeks = counts.reduce(0, +)
        guard weeks > 0 else { return [] }
        let gaps = segmentGap * CGFloat(weeks - counts.count) + blockGap * CGFloat(counts.count - 1)
        let segment = max(0, (width - gaps) / CGFloat(weeks))
        return counts.map { segment * CGFloat($0) + segmentGap * CGFloat($0 - 1) }
    }

    // MARK: Helpers

    private static func blockIndex(_ blocks: [WinterArc.Block], _ weekStart: String) -> Int? {
        blocks.firstIndex { $0.startDate <= weekStart && weekStart <= $0.endDate }
    }

    static func days(from start: String, to end: String) -> Int {
        guard let from = FoodFormat.parse(start), let to = FoodFormat.parse(end) else { return 0 }
        return ActivityFormat.mondayCalendar.dateComponents([.day], from: from, to: to).day ?? 0
    }

    static func hours(_ value: Double) -> String {
        value == value.rounded() ? "\(Int(value))" : String(format: "%.1f", value)
    }

    private static func ordinal(_ n: Int) -> String {
        switch n { case 1: "1st"; case 2: "2nd"; case 3: "3rd"; default: "\(n)th" }
    }

    private static func monthDay(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return iso }
        let month = date.formatted(Date.FormatStyle().month(.abbreviated).locale(Locale(identifier: "en_GB")))
        return "\(month) \(ActivityFormat.mondayCalendar.component(.day, from: date))"
    }
}

#if DEBUG
extension ArcFormat {
    /// `-arcDemo active|lighter|last|upcoming|stall|due|none`: a made-up arc (Base · Sweet-spot build ·
    /// VO2 touch, like the web's Nov–Feb template) and stall block around today, for screenshots.
    static func demo(_ stage: String, today: String) -> (blocks: [WinterArc.Block], stall: StallBlock?) {
        let monday = PlanFormat.weekStart(of: today)
        let offset = ["lighter": -21, "last": -35, "upcoming": 14][stage] ?? -14
        let start = PlanFormat.addingDays(offset, to: monday)
        let blocks = ["due", "none"].contains(stage) ? [] : demoArc(from: start)
        let uprightStart = PlanFormat.addingDays(-21, to: monday)
        let stall: StallBlock? = switch stage {
        case "none", "upcoming", "lighter", "last": nil
        case "stall":
            StallBlock(exerciseName: "Barbell Bench Press", label: "Rep scheme", text: "Switch to 4 × 6 at 70 kg for 3 weeks.",
                       scope: "block", startedOn: PlanFormat.addingDays(-7, to: monday), endsOn: PlanFormat.addingDays(14, to: monday),
                       week: 2, weeks: 3, due: false)
        default:
            StallBlock(exerciseName: "Dumbbell Upright Row", label: "Rep scheme",
                       text: "Switch to 3 × 12–15 at 18 kg for 3 weeks, last set close to failure.",
                       scope: "block", startedOn: uprightStart, endsOn: monday, week: 3, weeks: 3, due: true)
        }
        return (blocks, stall)
    }

    private static func demoArc(from start: String) -> [WinterArc.Block] {
        let shapes: [(String, Int, Double, WinterArc.RideMix, Int)] = [
            ("Base", 6, 3, .init(z2: 3), 4),
            ("Sweet-spot build", 6, 3.5, .init(z2: 2, sweetSpot: 2), 3),
            ("VO2 touch", 7, 3.5, .init(z2: 2, sweetSpot: 1, vo2: 1), 3),
        ]
        var monday = start
        return shapes.map { name, weeks, hours, mix, every in
            let lighter = (1...weeks).filter { $0 % every == 0 }.map { PlanFormat.addingDays(($0 - 1) * 7, to: monday) }
            let block = WinterArc.Block(startDate: monday, endDate: PlanFormat.addingDays(weeks * 7 - 1, to: monday), weeks: weeks,
                                        focusLabel: name, label: name, weeklyHours: hours, rideMix: mix, lighterEvery: every,
                                        lighterWeeks: lighter)
            monday = PlanFormat.addingDays(weeks * 7, to: monday)
            return block
        }
    }
}
#endif
