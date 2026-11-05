import Foundation

/// The week card's contract: the first rules of the week brief, with the lift slots and the
/// block's rides drawn as pills and ticks that fill as the week is trained.
enum WeekBriefFormat {
    static let cardRules = 3

    enum Kind: String { case safety, anchor, block, outcome, habit }

    /// One rule on the card. Anchor with slots shows pills, the block shows ride ticks.
    struct Rule: Equatable {
        let kind: Kind
        let kicker: String
        /// Bold lead-in ("Left knee"), then the rest.
        let lead: String?
        let text: String
        var slots: [SlotPill] = []
        var rides: [RideTick] = []
    }

    struct SlotPill: Equatable {
        /// "A", "C".
        let code: String
        /// "Upper Press", or "for D · knee" for a stand-in.
        let name: String
        let swapped: Bool
        let done: Bool
    }

    struct RideTick: Equatable {
        let minutes: Int
        let kind: String
        let done: Bool
    }

    static func path(_ weekStart: String) -> String { "/plans/week-brief?week_start=\(weekStart)" }

    /// The rules shown on the card, in the brief's order.
    static func rules(_ brief: WeekBrief, week: WeeklyPlan, today: String) -> [Rule] {
        brief.lines.prefix(cardRules).map { rule($0, brief: brief, week: week, today: today) }
    }

    static func moreCount(_ brief: WeekBrief) -> Int { max(0, brief.lines.count - cardRules) }

    static func rule(_ line: WeekBrief.Line, brief: WeekBrief, week: WeeklyPlan, today: String) -> Rule {
        let kind = Kind(rawValue: line.priority) ?? .habit
        let (lead, rest) = split(line.text)
        switch kind {
        case .anchor where brief.lifts.mode == "slots" && !brief.lifts.slots.isEmpty && line.text.contains(brief.lifts.slots[0].label):
            return Rule(kind: kind, kicker: "\(lead.map(compact) ?? line.priorityLabel) · anchor", lead: nil, text: "",
                        slots: slots(brief.lifts.slots, week: week, today: today))
        case .block:
            let label = brief.block?.label ?? "Block"
            return Rule(kind: kind, kicker: "\(label) · rides", lead: nil, text: brief.block.map(rideText) ?? line.text,
                        rides: rides(week, today: today))
        case .safety:
            // "Left outside of left knee, probably ITBS" leads with its first clause.
            return Rule(kind: kind, kicker: line.priorityLabel, lead: lead?.components(separatedBy: ", ").first, text: rest)
        default:
            return Rule(kind: kind, kicker: line.priorityLabel, lead: lead, text: rest)
        }
    }

    /// "Lift three times per week" → "Lift 3×".
    static func compact(_ goal: String) -> String {
        var text = goal
        for (word, digit) in [("once", "1×"), ("twice", "2×"), ("two times", "2×"), ("three times", "3×"), ("four times", "4×"), ("five times", "5×")] {
            text = text.replacingOccurrences(of: word, with: digit, options: .caseInsensitive)
        }
        return text.replacingOccurrences(of: " per week", with: "").replacingOccurrences(of: " a week", with: "")
    }

    /// "Left knee: no lower-body lifts" → ("Left knee", "no lower-body lifts").
    static func split(_ text: String) -> (String?, String) {
        guard let colon = text.range(of: ": ") else { return (nil, text) }
        return (String(text[..<colon.lowerBound]), String(text[colon.upperBound...]))
    }

    /// "3× Z2 · 3.5 h · no SS / VO2", "1× SS · 2× Z2 · 2.6 h · lighter".
    static func rideText(_ block: WeekBrief.Block) -> String {
        let mix = block.rideMix
        var parts = [(mix.sweetSpot ?? 0, "SS"), (mix.vo2 ?? 0, "VO2"), (mix.z2 ?? 0, "Z2")]
            .filter { $0.0 > 0 }.map { "\($0.0)× \($0.1)" }
        parts.append("\(hours(block.rideHours)) h")
        if (mix.sweetSpot ?? 0) == 0 && (mix.vo2 ?? 0) == 0 { parts.append("no SS / VO2") }
        if block.lighter { parts.append("lighter") }
        return parts.joined(separator: " · ")
    }

    static func hours(_ value: Double) -> String {
        value == value.rounded() ? String(Int(value)) : String(format: "%.1f", value)
    }

    /// The slot pills, filled when a done lift day ran that workout (each done day counts once).
    static func slots(_ slots: [WeekBrief.Slot], week: WeeklyPlan, today: String) -> [SlotPill] {
        var doneLabels = week.days
            .filter { PlanFormat.sport($0) == .strength && PlanFormat.status($0, today: today) == .done }
            .map { $0.templateLabel ?? $0.title }
        return slots.map { slot in
            let done = doneLabels.firstIndex(of: slot.label).map { doneLabels.remove(at: $0) } != nil
            let swappedArea = slot.reason.map { $0.replacingOccurrences(of: " protected", with: "").lowercased() }
            return SlotPill(code: code(slot.label), name: slot.swappedFrom.map { "for \(code($0)) · \(swappedArea ?? "protected")" } ?? title(slot.label),
                            swapped: slot.swappedFrom != nil, done: done)
        }
    }

    /// "Workout C · Wide Shoulders" → "C".
    static func code(_ label: String) -> String {
        let head = label.components(separatedBy: " · ").first ?? label
        return head.hasPrefix("Workout ") ? String(head.dropFirst("Workout ".count)) : String(head.prefix(1))
    }

    /// "Workout C · Wide Shoulders" → "Wide Shoulders".
    static func title(_ label: String) -> String {
        let parts = label.components(separatedBy: " · ")
        return parts.count > 1 ? parts[1] : label
    }

    /// One tick per planned ride, sized by its minutes and coloured by its type.
    static func rides(_ week: WeeklyPlan, today: String) -> [RideTick] {
        week.days.filter { PlanFormat.sport($0) == .ride }.map { day in
            RideTick(minutes: day.targetDurationMin ?? 45, kind: rideKind(day), done: PlanFormat.status(day, today: today) == .done)
        }
    }

    static func rideKind(_ day: PlanDay) -> String {
        let intent = (day.workoutIntent ?? "").lowercased()
        let title = day.title.lowercased()
        if intent == "interval" || title.contains("vo2") { return "vo2" }
        if intent == "tempo" || title.contains("sweet spot") || title.contains("threshold") { return "sweet_spot" }
        return "z2"
    }

    /// "Base wk 1 of 5" for the sheet's title, or the week's dates without a block.
    static func sheetTitle(_ brief: WeekBrief) -> String {
        brief.block.map { "\($0.label) wk \($0.weekNumber) of \($0.weeksInBlock)" } ?? "This week"
    }
}

#if DEBUG
extension WeekBriefFormat {
    /// `-briefDemo knee|rotation|sick|lighter` draws the week card from a made-up brief.
    static var demoStage: String? { UserDefaults.standard.string(forKey: "briefDemo") }

    static func demo(_ stage: String, weekStart: String) -> WeekBrief {
        typealias Line = WeekBrief.Line
        let anchorText = "Lift three times per week: Workout A · Upper Press, Workout D · Lower + Core, Workout B · Upper Pull"
        let slots = [
            WeekBrief.Slot(slot: "Upper 1", templateId: "strength-a", label: "Workout A · Upper Press", focusArea: "upper"),
            WeekBrief.Slot(slot: "Lower", templateId: "strength-d", label: "Workout D · Lower + Core", focusArea: "lower"),
            WeekBrief.Slot(slot: "Upper 2", templateId: "strength-b", label: "Workout B · Upper Pull", focusArea: "upper"),
        ]
        let habit = Line(priority: "habit", priorityLabel: "Habit", text: "Long ride Sat/Sun", source: "Athlete settings", key: "long_days")
        switch stage {
        case "rotation":
            return WeekBrief(weekStart: weekStart, headline: "", lines: [
                Line(priority: "anchor", priorityLabel: "Anchor", text: "Lift three times per week", source: "Anchor goal", key: "goal:4"), habit,
            ], lifts: .init(mode: "rotation", next: "Workout B · Upper Pull"))
        case "sick":
            return WeekBrief(weekStart: weekStart, headline: "", lines: [
                Line(priority: "safety", priorityLabel: "Safety", text: "Sick Tue 10–Thu 12: no training beyond an easy walk", source: "Sick", key: "sick"),
                Line(priority: "anchor", priorityLabel: "Anchor", text: anchorText, source: "Anchor goal", key: "goal:4"), habit,
            ], lifts: .init(mode: "slots", slots: slots))
        case "lighter":
            return WeekBrief(weekStart: weekStart, headline: "", lines: [
                Line(priority: "anchor", priorityLabel: "Anchor", text: anchorText, source: "Anchor goal", key: "goal:4"),
                Line(priority: "block", priorityLabel: "Block", text: "Rides about 2.6 h: 1× Sweet spot + 2× Z2 (lighter week)", source: "Winter arc", key: "arc"),
                Line(priority: "outcome", priorityLabel: "Outcome", text: "Build climb power: 210 W for 15 min", source: "Goal", key: "goal:6"), habit,
            ], lifts: .init(mode: "slots", slots: slots),
                             block: .init(label: "Sweet-spot build", weekNumber: 3, weeksInBlock: 6, lighter: true, rideHours: 2.6,
                                          rideMix: .init(z2: 2, sweetSpot: 1, vo2: 0)))
        default:
            var knee = slots
            knee[1] = WeekBrief.Slot(slot: "Lower", templateId: "strength-c", label: "Workout C · Wide Shoulders", focusArea: "upper",
                                     swappedFrom: "Workout D · Lower + Core", reason: "Knee protected")
            return WeekBrief(weekStart: weekStart, headline: "", lines: [
                Line(priority: "safety", priorityLabel: "Safety", text: "Left knee: no lower-body lifts, rides easy and flat", source: "Recovery, pain 1/10", key: "injury:2"),
                Line(priority: "anchor", priorityLabel: "Anchor", text: "Lift three times per week: Workout A · Upper Press, Workout C · Wide Shoulders (for Workout D · Lower + Core), Workout B · Upper Pull", source: "Anchor goal", key: "goal:4"),
                Line(priority: "block", priorityLabel: "Block", text: "Rides about 3.5 h: 3× Z2, no sweet spot or VO2", source: "Winter arc: Base wk 1/5", key: "arc"),
                Line(priority: "outcome", priorityLabel: "Outcome", text: "Build climb power: 210 W for 15 min: waits for a quality block (Base has none)", source: "Goal, after the block", key: "goal:6"),
                habit,
            ], lifts: .init(mode: "slots", slots: knee),
                             block: .init(label: "Base", weekNumber: 1, weeksInBlock: 5, lighter: false, rideHours: 3.5, rideMix: .init(z2: 3, sweetSpot: 0, vo2: 0)))
        }
    }
}
#endif
