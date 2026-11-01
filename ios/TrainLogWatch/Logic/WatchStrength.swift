import Foundation
#if canImport(TrainLog)
// Compiled into TrainLogTests as well, where the session types live in the app module.
@testable import TrainLog
#endif

/// Pure rules behind the Watch's strength screens (unit-tested in TrainLogTests).
enum WatchStrength {
    struct Totals: Equatable {
        let setsDone: Int
        let setsTotal: Int
        /// Weight × reps over completed working sets; bodyweight sets add nothing.
        let volumeKg: Double
    }

    static func totals(_ session: StrengthSession) -> Totals {
        let working = session.exercises.flatMap(\.workingSets)
        let done = working.filter(\.isCompleted)
        let volume = done.reduce(0) { sum, set in
            sum + (set.actualWeightKg ?? 0) * Double(set.actualReps ?? 0)
        }
        return Totals(setsDone: done.count, setsTotal: working.count, volumeKg: volume)
    }

    /// Rough time left: every set still to do takes its hold (or ~40 s of lifting) plus its rest,
    /// except the very last one.
    static func minutesLeft(_ session: StrengthSession) -> Int {
        let todo = session.exercises.flatMap(\.sets).filter { !$0.isCompleted }
        guard !todo.isEmpty else { return 0 }
        let seconds = todo.reduce(0) { $0 + ($1.targetSeconds ?? 40) + $1.restSeconds } - (todo.last?.restSeconds ?? 0)
        return max(1, Int((Double(seconds) / 60).rounded()))
    }

    /// "Ex 2/5 · Set 2 of 3" (warm-ups say so).
    static func kicker(_ session: StrengthSession, exercise: StrengthSession.Exercise, set: StrengthSession.WorkoutSet) -> String {
        let position = (session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }.firstIndex { $0.id == exercise.id } ?? 0) + 1
        let count = session.exercises.count
        if set.isWarmup { return "Ex \(position)/\(count) · Warm-up" }
        let index = (exercise.workingSets.firstIndex { $0.id == set.id } ?? 0) + 1
        return "Ex \(position)/\(count) · Set \(index) of \(exercise.workingSets.count)"
    }

    /// The next exercise with sets left after `exercise`, wrapping round; nil when nothing else is left.
    static func nextExercise(after exercise: StrengthSession.Exercise, in session: StrengthSession) -> StrengthSession.Exercise? {
        let ordered = session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }
        guard let index = ordered.firstIndex(where: { $0.id == exercise.id }) else { return nil }
        let rotated = ordered[(index + 1)...] + ordered[..<index]
        return rotated.first { !$0.isDone }
    }

    /// Where `jump(to:)` lands: the exercise's first set not done yet (its first set when all are).
    static func jumpTarget(_ exercise: StrengthSession.Exercise) -> Int {
        exercise.sets.sorted { $0.setOrder < $1.setOrder }.first { !$0.isCompleted }?.setOrder
            ?? exercise.sets.map(\.setOrder).min() ?? 1
    }

    /// "+0.5 vs last", "same as last", "−1 vs last"; nil without a last time.
    static func versusLast(_ value: Double?, last: Double?) -> String? {
        guard let last else { return nil }
        let delta = ((value ?? 0) - last)
        if abs(delta) < 0.05 { return "same as last" }
        let text = StrengthFormat.number(abs(delta))
        return (delta > 0 ? "+" : "−") + text + " vs last"
    }
}
