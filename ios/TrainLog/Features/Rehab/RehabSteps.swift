import Foundation

// Shared with the Watch app (project.yml), so Foundation only.

/// One screen of the session: a set (one side of it for per-side work) or a rest.
struct RehabStep: Equatable, Sendable {
    enum Kind: Sendable { case exercise, rest }

    struct Completes: Hashable, Sendable {
        let issueId: Int
        let index: Int
    }

    let kind: Kind
    let name: String
    var side: String?
    var cue: String?
    var reps: Int?
    var seconds: Int?
    var range: String?
    var dose: String?
    let set: Int
    let sets: Int
    /// The exercise's place in the session, 1-based.
    let position: Int
    let count: Int
    /// On an exercise's last step: the routine exercise to tick once it's passed.
    var completes: Completes?
}

/// Pure step building and formatting (unit-tested).
enum RehabFormat {
    /// Every set of one exercise (left then right for per-side work), a rest between sets, then
    /// the next exercise. Same order as the web's `buildStraightSetSteps`.
    static func steps(_ session: GuidedSession) -> [RehabStep] {
        let count = session.exercises.count
        return session.exercises.enumerated().flatMap { position, exercise -> [RehabStep] in
            let sets = max(1, exercise.sets ?? 1)
            var steps: [RehabStep] = []
            for set in 1...sets {
                for side in exercise.perSide ? ["Left side", "Right side"] : [nil] {
                    steps.append(RehabStep(
                        kind: .exercise, name: exercise.name, side: side, cue: exercise.cue,
                        reps: exercise.reps, seconds: exercise.seconds, range: exercise.range, dose: exercise.dose,
                        set: set, sets: sets, position: position + 1, count: count
                    ))
                }
                if set < sets, session.restSeconds > 0 {
                    steps.append(RehabStep(
                        kind: .rest, name: "Rest", cue: "Set \(set + 1) of \(sets) next: \(exercise.name).",
                        seconds: session.restSeconds, set: set, sets: sets, position: position + 1, count: count
                    ))
                }
            }
            if let issueId = exercise.issueId, let index = exercise.index {
                steps[steps.count - 1].completes = .init(issueId: issueId, index: index)
            }
            return steps
        }
    }

    /// "×12", "×8–10", "0:30", or the written dose when it had no numbers.
    static func dose(_ step: RehabStep) -> String {
        if let reps = step.reps { return "×" + (step.range ?? String(reps)) }
        if let seconds = step.seconds { return StrengthFormat.clock(seconds) }
        return step.dose ?? "As written"
    }

    /// "Set 2 of 5 · 0:30" while it's the same exercise, else "Glute bridge ×12"; sides added.
    static func upNext(_ next: RehabStep, after step: RehabStep) -> String {
        let side = next.side.map { " · \($0.lowercased())" } ?? ""
        if next.position == step.position {
            return (next.set == step.set ? "Same set" : "Set \(next.set) of \(next.sets)") + side + " · " + dose(next)
        }
        return "\(next.name)\(side) \(dose(next))"
    }

    /// "Exercise 2 of 8 · Set 1 of 3", or "Rest".
    static func kicker(_ step: RehabStep) -> String {
        if step.kind == .rest { return "Rest" }
        let exercise = "Exercise \(step.position) of \(step.count)"
        return step.sets > 1 ? "\(exercise) · Set \(step.set) of \(step.sets)" : exercise
    }
}
