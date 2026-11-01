import Foundation

// Shared with the Watch app (project.yml), so Foundation only.

/// Pure session rules, mirroring backend `complete_set` (unit-tested).
enum StrengthLogic {
    static func current(in session: StrengthSession) -> (exercise: StrengthSession.Exercise, set: StrengthSession.WorkoutSet)? {
        guard let exercise = session.exercises.first(where: { $0.exerciseOrder == session.currentExerciseOrder }),
              let set = exercise.sets.first(where: { $0.setOrder == session.currentSetOrder }) ?? exercise.sets.first
        else { return nil }
        return (exercise, set)
    }

    /// Marks a set done and moves to the next pending set, preferring the same exercise.
    static func complete(
        _ session: StrengthSession, setId: Int, reps: Int, weightKg: Double?, effort: SetEffort?, seconds: Int? = nil
    ) -> StrengthSession {
        var session = session
        guard let exerciseIndex = session.exercises.firstIndex(where: { $0.sets.contains { $0.id == setId } }),
              let setIndex = session.exercises[exerciseIndex].sets.firstIndex(where: { $0.id == setId })
        else { return session }
        session.exercises[exerciseIndex].sets[setIndex].actualReps = reps
        session.exercises[exerciseIndex].sets[setIndex].actualWeightKg = weightKg
        session.exercises[exerciseIndex].sets[setIndex].status = "completed"
        session.exercises[exerciseIndex].sets[setIndex].effort = effort?.rawValue
        session.exercises[exerciseIndex].sets[setIndex].actualSeconds = seconds

        let same = session.exercises[exerciseIndex]
        let candidates = [same] + session.exercises.filter { $0.id != same.id }.sorted { $0.exerciseOrder < $1.exerciseOrder }
        for exercise in candidates {
            if let next = exercise.sets.sorted(by: { $0.setOrder < $1.setOrder }).first(where: { !$0.isCompleted }) {
                session.currentExerciseOrder = exercise.exerciseOrder
                session.currentSetOrder = next.setOrder
                break
            }
        }
        return session
    }

    /// Another device's copy of the session (the Watch's, the phone's, or the server's via the
    /// phone), folded into this one. A set done here stays done even if the copy predates it, so a
    /// copy that crossed a newer tap never undoes it; everything else (progressed targets, added
    /// sets, efforts, the end) comes from the copy. The position follows whichever has more sets done.
    static func merge(_ local: StrengthSession, with incoming: StrengthSession) -> StrengthSession {
        guard local.id == incoming.id else { return incoming }
        var merged = incoming
        if !local.isActive, incoming.isActive {
            merged.status = local.status
            merged.completedAt = local.completedAt
        }
        let localSets = Dictionary(local.exercises.flatMap(\.sets).map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        for exerciseIndex in merged.exercises.indices {
            for setIndex in merged.exercises[exerciseIndex].sets.indices {
                let set = merged.exercises[exerciseIndex].sets[setIndex]
                guard let mine = localSets[set.id] else { continue }
                if mine.isCompleted, !set.isCompleted {
                    merged.exercises[exerciseIndex].sets[setIndex] = mine
                } else if set.isCompleted, set.effort == nil, mine.effort != nil {
                    merged.exercises[exerciseIndex].sets[setIndex].effort = mine.effort
                }
            }
        }
        let done = { (session: StrengthSession) in session.exercises.flatMap(\.sets).filter(\.isCompleted).count }
        if done(local) > done(incoming) {
            merged.currentExerciseOrder = local.currentExerciseOrder
            merged.currentSetOrder = local.currentSetOrder
        }
        return merged
    }

    /// A weight changed on an earlier set of the same lift carries to the next one.
    static func carriedWeight(for set: StrengthSession.WorkoutSet, in exercise: StrengthSession.Exercise) -> Double? {
        guard !set.isWarmup else { return set.targetWeightKg }
        let previous = exercise.workingSets.last { $0.isCompleted && $0.setOrder < set.setOrder }
        return previous?.actualWeightKg ?? set.targetWeightKg
    }

    /// 0.5 kg steps; stepping down from 0 goes back to bodyweight (nil).
    static func step(_ weight: Double?, by steps: Int) -> Double? {
        guard let weight else { return steps > 0 ? Double(steps) * 0.5 : nil }
        let next = ((weight + Double(steps) * 0.5) * 2).rounded() / 2
        return next <= 0 ? nil : min(1000, next)
    }

    /// "Set 2" counting working sets only; warm-ups are labelled as such.
    static func label(for set: StrengthSession.WorkoutSet, in exercise: StrengthSession.Exercise) -> String {
        if set.isWarmup { return "Warm-up" }
        let index = exercise.workingSets.firstIndex { $0.id == set.id } ?? 0
        return "Set \(index + 1)"
    }

    /// Completed share of each exercise's working sets, for the segmented progress bar.
    static func progress(of exercise: StrengthSession.Exercise) -> Double {
        let working = exercise.workingSets
        guard !working.isEmpty else { return exercise.isDone ? 1 : 0 }
        return Double(working.filter(\.isCompleted).count) / Double(working.count)
    }
}

enum StrengthFormat {
    static func number(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(format: "%.1f", value)
    }

    static func weight(_ kg: Double?) -> String {
        guard let kg else { return "BW" }
        return number(kg)
    }

    static func load(weight: Double?, reps: Int, seconds: Int? = nil) -> String {
        if let seconds {
            return weight.map { "\(number($0)) kg · \(hold(seconds))" } ?? hold(seconds)
        }
        return weight.map { "\(number($0)) kg × \(reps)" } ?? "BW × \(reps)"
    }

    /// "40 s" for short holds, "1:30" from a minute up.
    static func hold(_ seconds: Int) -> String {
        seconds < 60 ? "\(seconds) s" : clock(seconds)
    }

    static func clock(_ seconds: Int) -> String {
        let seconds = max(0, seconds)
        let hours = seconds / 3600
        let minutes = seconds % 3600 / 60
        let rest = seconds % 60
        return hours > 0
            ? String(format: "%d:%02d:%02d", hours, minutes, rest)
            : String(format: "%d:%02d", minutes, rest)
    }

    static func parseMoment(_ iso: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: iso) { return date }
        // Backend timestamps without an offset are local time.
        let local = DateFormatter()
        local.locale = Locale(identifier: "en_US_POSIX")
        local.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return local.date(from: iso)
    }
}
