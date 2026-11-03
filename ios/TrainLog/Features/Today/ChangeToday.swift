import Foundation

/// Pure rules for "Change today": the four quick asks, what each draws on the tape and the
/// sentence the coach gets (unit-tested).
enum ChangeTodayFormat {
    /// Today's session as the sheet sees it.
    struct Session: Equatable, Identifiable {
        let sport: Sport
        let minutes: Int
        let title: String

        var id: String { "\(sport.rawValue).\(minutes).\(title)" }

        var isRest: Bool { sport == .rest }
    }

    enum Ask: String, CaseIterable, Identifiable {
        case rough, short, more, sport

        var id: String { rawValue }

        var title: String {
            switch self {
            case .rough: "Feeling rough"
            case .short: "Short on time"
            case .more: "More time"
            case .sport: "Other sport"
            }
        }

        var symbol: String {
            switch self {
            case .rough: "thermometer.medium"
            case .short: "timer"
            case .more: "plus.circle"
            case .sport: "arrow.left.arrow.right"
            }
        }
    }

    enum Choice: Hashable {
        case easier, shorter, mobility, rest
        /// Short on time: the plan's own short version, shown on the card without the coach.
        case planShort
        /// Short on time: about this many minutes in all.
        case minutes(Int)
        /// More time: this many minutes on top.
        case add(Int)
        case harder
        case sport(Sport)
        /// Rest day: add a session of this sport and length.
        case session(Sport, Int)
    }

    /// The line under each ask's title.
    static func subtitle(_ ask: Ask, hasFallback: Bool) -> String {
        switch ask {
        case .rough: "easier or shorter"
        case .short: hasFallback ? "plan's short version" : "a shorter version"
        case .more: "longer or harder"
        case .sport: "ride, run, walk…"
        }
    }

    static func options(_ ask: Ask, now: Session, hasFallback: Bool = false) -> [Choice] {
        switch ask {
        case .rough: [.easier, .shorter, .mobility, .rest]
        case .short: (hasFallback ? [.planShort] : []) + shortMinutes(now).suffix(hasFallback ? 2 : 3).map { .minutes($0) }
        case .more: [.add(15), .add(30), .add(45), .harder]
        case .sport: [Sport.ride, .run, .walk, .mobility, .strength].filter { $0 != now.sport }.prefix(4).map { .sport($0) }
        }
    }

    /// Three lengths under today's: 10/15/20 for a 25 min session, never 0.
    static func shortMinutes(_ now: Session) -> [Int] {
        let picks = [10, 15, 20, 30, 40].filter { $0 < max(now.minutes, 15) }
        return Array(picks.suffix(3))
    }

    static let restSports: [Sport] = [.ride, .walk, .mobility, .strength]
    static let restMinutes = [20, 30, 45, 60]

    /// The ask that opens preselected: Feeling rough · Easier when readiness says to swap.
    static func initial(suggestsSwap: Bool, now: Session) -> (Ask, Choice)? {
        suggestsSwap && !now.isRest ? (.rough, .easier) : nil
    }

    static func label(_ choice: Choice) -> String {
        switch choice {
        case .easier: "Easier"
        case .shorter: "Shorter"
        case .mobility: "Mobility"
        case .rest: "Rest"
        case .planShort: "Plan's short"
        case .minutes(let m): "\(m) min"
        case .add(let m): "+\(m) min"
        case .harder: "Harder"
        case .sport(let sport): sport == .strength ? "Lift" : sport.label
        case .session(let sport, _): sport == .strength ? "Lift" : sport.label
        }
    }

    /// What the dashed bar shows before the coach answers: the phone's guess, not the plan.
    struct Ghost: Equatable {
        let sport: Sport
        let minutes: Int
        let label: String
    }

    static func ghost(_ choice: Choice?, now: Session) -> Ghost? {
        guard let choice else { return nil }
        let half = max(10, roundFive(Double(now.minutes) * 0.6))
        switch choice {
        case .easier: return Ghost(sport: now.sport, minutes: now.minutes, label: "Same \(now.minutes) min, easier")
        case .shorter: return Ghost(sport: now.sport, minutes: half, label: "~\(half) min")
        case .mobility: return Ghost(sport: .mobility, minutes: 20, label: "Mobility · ~20 min")
        case .rest: return Ghost(sport: .rest, minutes: 0, label: "Rest")
        case .planShort: return Ghost(sport: now.sport, minutes: half, label: "Plan's short version")
        case .minutes(let m): return Ghost(sport: now.sport, minutes: m, label: "~\(m) min")
        case .add(let m): return Ghost(sport: now.sport, minutes: now.minutes + m, label: "~\(now.minutes + m) min")
        case .harder: return Ghost(sport: now.sport, minutes: now.minutes, label: "Same \(now.minutes) min, harder")
        case .sport(let sport):
            let minutes = max(now.minutes, sport == .ride ? 30 : 20)
            return Ghost(sport: sport, minutes: minutes, label: "\(label(choice)) · ~\(minutes) min")
        case .session(let sport, let m): return Ghost(sport: sport, minutes: m, label: "\(label(choice)) · ~\(m) min")
        }
    }

    /// The sentence the coach gets for a pick.
    static func sentence(_ choice: Choice, now: Session) -> String {
        let what = now.title.isEmpty ? "today's session" : now.title
        switch choice {
        case .easier: return "I'm feeling rough today. Keep \(what) at about \(now.minutes) min but make it clearly easier."
        case .shorter: return "I'm feeling rough today. Make \(what) shorter, about \(ghost(choice, now: now)?.minutes ?? now.minutes) min."
        case .mobility: return "I'm feeling rough today. Replace \(what) with easy mobility, about 20 min."
        case .rest: return "I'm feeling rough today. Make today a rest day instead of \(what)."
        case .planShort: return "I'm short on time today. Use the short version of \(what)."
        case .minutes(let m): return "I'm short on time today: only about \(m) min for \(what)."
        case .add(let m): return "I have \(m) min more than planned today. Make \(what) about \(now.minutes + m) min."
        case .harder: return "I feel good today. Keep \(what) at about \(now.minutes) min but make it harder."
        case .sport(let sport):
            let minutes = ghost(choice, now: now)?.minutes ?? now.minutes
            return "I'd rather do \(noun(sport)) today instead of \(what), about \(minutes) min."
        case .session(let sport, let m): return "Today is a rest day, but I'd like to do \(noun(sport)), about \(m) min."
        }
    }

    /// The revision feedback: the pick's sentence, then the free note.
    static func feedback(_ choice: Choice?, note: String, now: Session) -> String {
        let text = note.trimmingCharacters(in: .whitespacesAndNewlines)
        return [choice.map { sentence($0, now: now) }, text.isEmpty ? nil : text]
            .compactMap { $0 }
            .joined(separator: "\n")
    }

    /// "HRV, sleep and sleep debt are off": why the sheet opened on Feeling rough.
    static func readinessLine(_ factors: [PhoneToday.Factor]) -> String {
        let off = factors.filter { $0.tone != "steady" }.sorted { $0.points > $1.points }.map(\.label)
        guard let first = off.first else { return "Recovery is low today." }
        let names = [first] + off.dropFirst().prefix(2).map { $0.prefix(1).lowercased() + $0.dropFirst() }
        let list = names.count == 1 ? names[0] : names.dropLast().joined(separator: ", ") + " and " + names.last!
        return "\(list) \(names.count == 1 ? "is" : "are") off."
    }

    /// The tape's scale: 90 min, stretched in 30 min steps for longer sessions.
    static func scale(_ minutes: Int...) -> Int {
        let top = (minutes.max() ?? 0) + 10
        return max(90, Int((Double(top) / 30).rounded(.up)) * 30)
    }

    /// Where the card keeps what today was before the coach changed it.
    static func trailKey(_ date: String) -> String { "changeToday.was.\(date)" }

    /// "Bodyweight upper, 25 min": the card's trail after a change.
    static func trail(_ session: Session) -> String {
        if session.isRest { return "rest day" }
        let title = PlanFormat.rowTitle(session.title)
        let short = title.components(separatedBy: " + ").first ?? title
        return session.minutes > 0 ? "\(short), \(session.minutes) min" : short
    }

    private static func noun(_ sport: Sport) -> String {
        switch sport {
        case .ride: "a ride"
        case .run: "a run"
        case .walk: "a walk"
        case .mobility: "mobility"
        case .strength: "a lift"
        case .hike: "a hike"
        default: "something else"
        }
    }

    private static func roundFive(_ value: Double) -> Int { Int((value / 5).rounded()) * 5 }
}
