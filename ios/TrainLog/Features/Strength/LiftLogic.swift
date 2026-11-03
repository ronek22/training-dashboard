import Foundation

/// Lift history, plate maths and the warm-up ramp for the session screen (unit-tested).
/// Frames in docs/design/artboards/iOSLiftHistory.dc.html.
enum LiftLogic {
    // MARK: Barbell lifts

    /// Lifts loaded on a bar: these get plates and, first in a session, the warm-up ramp.
    static func isBarbell(_ name: String) -> Bool {
        let name = name.lowercased()
        let other = ["dumbbell", "kettlebell", "cable", "machine", "smith", "goblet", "band"]
        guard !other.contains(where: name.contains) else { return false }
        let bar = ["barbell", "back squat", "front squat", "deadlift", "bench press", "overhead press", "military press", "hip thrust"]
        return bar.contains(where: name.contains)
    }

    // MARK: Plates

    enum PlateFit: Equatable {
        /// Nothing on the bar.
        case bar
        /// Per side, heaviest first.
        case plates([Double])
        /// The plates can't make it: the nearest totals either side (nil past what you own).
        case off(lower: Double?, upper: Double?)
        case belowBar
    }

    /// Per-side totals (in hundredths of a kg) the plates can make, each with the fewest plates.
    /// A plate size needs a pair, so each side gets half of what's owned.
    static func sides(_ kit: GymKit) -> [Int: [Double]] {
        var best: [Int: [Double]] = [0: []]
        let pairs = (kit.plates ?? []).filter { $0.kg > 0 && $0.count >= 2 }.sorted { $0.kg > $1.kg }
        for plate in pairs {
            let unit = Int((plate.kg * 100).rounded())
            for _ in 0..<(plate.count / 2) {
                var next = best
                for (total, list) in best {
                    let candidate = list + [plate.kg]
                    if let existing = next[total + unit], existing.count <= candidate.count { continue }
                    next[total + unit] = candidate
                }
                best = next
            }
        }
        return best
    }

    /// Every total the bar can be loaded to, lightest first.
    static func totals(_ kit: GymKit) -> [Double] {
        sides(kit).keys.sorted().map { kit.bar + Double($0) * 2 / 100 }
    }

    static func fit(_ total: Double, kit: GymKit) -> PlateFit {
        guard total >= kit.bar - 0.001 else { return .belowBar }
        let options = sides(kit)
        let side = Int(((total - kit.bar) / 2 * 100).rounded())
        if abs(kit.bar + Double(side) * 2 / 100 - total) < 0.001, let plates = options[side] {
            return plates.isEmpty ? .bar : .plates(plates)
        }
        let all = totals(kit)
        return .off(lower: all.last { $0 < total }, upper: all.first { $0 > total })
    }

    // MARK: Warm-up ramp

    struct RampStep: Equatable, Identifiable {
        let index: Int
        let weight: Double
        let reps: Int
        let plates: [Double]
        var id: Int { index }
        var isBar: Bool { plates.isEmpty }
    }

    /// The working weight a ramp is worth it for.
    static let rampFrom = 40.0

    /// Bar × 10, then about 50 % × 5, 70 % × 3 and 85 % × 2 on loads the plates can make, dropping
    /// any step that repeats the one before or reaches the working weight.
    static func ramp(to working: Double, kit: GymKit) -> [RampStep] {
        guard working >= max(rampFrom, kit.bar + 10) else { return [] }
        let all = totals(kit)
        let options = sides(kit)
        var steps = [RampStep(index: 0, weight: kit.bar, reps: 10, plates: [])]
        for (share, reps) in [(0.5, 5), (0.7, 3), (0.85, 2)] {
            let target = working * share
            // Nearest load; a tie goes up.
            guard let weight = all.min(by: { abs($0 - target) < abs($1 - target) || (abs($0 - target) == abs($1 - target) && $0 > $1) }),
                  weight > steps[steps.count - 1].weight, weight < working
            else { continue }
            let side = Int(((weight - kit.bar) / 2 * 100).rounded())
            steps.append(RampStep(index: steps.count, weight: weight, reps: reps, plates: options[side] ?? []))
        }
        return steps.count > 1 ? steps : []
    }

    // MARK: History

    enum Metric: Equatable {
        case load, reps, seconds
    }

    /// What a lift's history is measured by: load when any recent session had one, then holds, then reps.
    static func metric(of history: LiftHistory) -> Metric {
        if history.sessions.contains(where: { $0.topLoadKg != nil }) { return .load }
        if history.sessions.contains(where: { $0.bestSeconds != nil }) { return .seconds }
        return .reps
    }

    static func value(of session: LiftHistory.Session, _ metric: Metric) -> Double? {
        switch metric {
        case .load: session.topLoadKg
        case .reps: session.bestReps.map(Double.init)
        case .seconds: session.bestSeconds.map(Double.init)
        }
    }

    /// Today's target in the same measure, for the ghost point at the end.
    static func target(of set: StrengthSession.WorkoutSet?, _ metric: Metric) -> Double? {
        guard let set else { return nil }
        switch metric {
        case .load: return set.targetWeightKg
        case .reps: return set.targetWeightKg == nil ? Double(set.targetReps) : nil
        case .seconds: return set.targetSeconds.map(Double.init)
        }
    }

    /// The sessions oldest first, as plotted.
    static func plotted(_ history: LiftHistory) -> [LiftHistory.Session] {
        let metric = metric(of: history)
        return history.sessions.reversed().filter { value(of: $0, metric) != nil }
    }

    /// "77.5 × 6", "BW × 10", "+5 × 6" or "50 s": the session's top set.
    static func top(of session: LiftHistory.Session, _ metric: Metric) -> String {
        switch metric {
        case .load:
            let load = session.topLoadKg ?? 0
            let reps = session.sets.filter { $0.weightKg == load }.compactMap(\.reps).max() ?? 0
            return "\(StrengthFormat.number(load)) × \(reps)"
        case .reps:
            return "BW × \(session.bestReps ?? 0)"
        case .seconds:
            return StrengthFormat.hold(session.bestSeconds ?? 0)
        }
    }

    /// The line under the lift name: the bold part and the rest ("3 sets · Oct 15").
    static func lastLine(_ history: LiftHistory) -> (top: String, rest: String)? {
        guard let last = history.sessions.first else { return nil }
        let metric = metric(of: history)
        let count = last.sets.count
        let noun = metric == .seconds ? (count == 1 ? "hold" : "holds") : (count == 1 ? "set" : "sets")
        return (top(of: last, metric), "\(count) \(noun) · \(shortDate(last.date))")
    }

    /// "3 × 6" under each date: sets × the top set's reps (or "3 holds").
    static func setsLabel(_ session: LiftHistory.Session, _ metric: Metric) -> String {
        let count = session.sets.count
        switch metric {
        case .seconds: return "\(count) \(count == 1 ? "hold" : "holds")"
        case .reps: return "\(count) × \(session.bestReps ?? 0)"
        case .load:
            let load = session.topLoadKg ?? 0
            let reps = session.sets.filter { $0.weightKg == load }.compactMap(\.reps).max() ?? 0
            return "\(count) × \(reps)"
        }
    }

    /// A session's sets on one line: "77.5 kg × 6 · 6 · 6" when the weight held, each set otherwise.
    static func setsLine(_ session: LiftHistory.Session) -> String {
        let sets = session.sets
        if let seconds = sets.first?.seconds, seconds > 0 {
            return sets.map { StrengthFormat.hold($0.seconds ?? 0) }.joined(separator: " · ")
        }
        let weights = Set(sets.map(\.weightKg))
        let reps = sets.map { String($0.reps ?? 0) }
        if weights.count == 1 {
            let weight = sets.first?.weightKg
            return "\(weight.map { "\(StrengthFormat.number($0)) kg" } ?? "BW") × \(reps.joined(separator: " · "))"
        }
        return sets.map { StrengthFormat.load(weight: $0.weightKg, reps: $0.reps ?? 0) }.joined(separator: " · ")
    }

    /// How the session felt, by the most common tap (later sets win a tie).
    static func feel(_ session: LiftHistory.Session) -> String? {
        let efforts = session.sets.compactMap { SetEffort(backend: $0.effort) }
        let counts = Dictionary(efforts.map { ($0, 1) }, uniquingKeysWith: +)
        return efforts.reversed().max { (counts[$0] ?? 0) < (counts[$1] ?? 0) }?.label
    }

    /// The footer: best set ever, and how today's target compares.
    static func bestLine(_ history: LiftHistory, target: Double?) -> (best: String, tail: String)? {
        guard let best = history.best else { return nil }
        let date = shortDate(best.date)
        if let seconds = best.seconds, best.weightKg == nil {
            return ("\(StrengthFormat.hold(seconds))", "on \(date)")
        }
        guard let weight = best.weightKg, weight > 0 else {
            return ("\(best.reps ?? 0) reps", "on \(date)")
        }
        let label = "\(StrengthFormat.number(weight)) kg × \(best.reps ?? 0)"
        guard metric(of: history) == .load, let target else { return (label, "on \(date)") }
        if target > weight { return (label, "on \(date) · today would be a new best") }
        if target == weight { return (label, "on \(date) · today matches it") }
        return (label, "on \(date) · \(StrengthFormat.number(weight - target)) kg above today")
    }

    /// Plate weights to the hundredth: "1.25", "33.75", "20".
    static func kg(_ value: Double) -> String {
        let text = String(format: "%.2f", value)
        return text.replacingOccurrences(of: #"\.?0+$"#, with: "", options: .regularExpression)
    }

    static func shortDate(_ iso: String) -> String {
        let input = DateFormatter()
        input.locale = Locale(identifier: "en_US_POSIX")
        input.dateFormat = "yyyy-MM-dd"
        guard let date = input.date(from: String(iso.prefix(10))) else { return iso }
        let output = DateFormatter()
        output.locale = Locale(identifier: "en_US_POSIX")
        output.dateFormat = "MMM d"
        return output.string(from: date)
    }

    static func historyPath(for names: [String]) -> String? {
        let unique = names.reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        guard !unique.isEmpty else { return nil }
        var components = URLComponents()
        components.queryItems = unique.map { URLQueryItem(name: "name", value: $0) }
        guard let query = components.percentEncodedQuery else { return nil }
        return "/strength/workouts/exercise-history?" + query.replacingOccurrences(of: "+", with: "%2B")
    }
}
