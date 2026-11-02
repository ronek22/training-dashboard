import Foundation

/// `GET /strength/workouts/sessions/{id}/summary` (backend/app/services/strength_session_summary.py):
/// the recap after a lift. Built locally from the session when the server can't be reached, then
/// without last time, bests or next targets.
struct StrengthSummary: Decodable, Sendable, Equatable {
    let sessionId: Int
    let name: String
    let date: String
    var durationMinutes: Int?
    let volumeKg: Double
    let setCount: Int
    let repCount: Int
    var previous: Previous?
    var bestCount = 0
    var goingUp = 0
    var holding = 0
    let exercises: [Exercise]
    /// False for the local stand-in shown while offline.
    var fromServer = true

    /// The last time this workout was done.
    struct Previous: Decodable, Sendable, Equatable {
        let date: String
        let volumeKg: Double
        let sets: Int
    }

    struct Exercise: Decodable, Sendable, Equatable, Identifiable {
        var id: String { exerciseName }
        let exerciseName: String
        let setCount: Int
        var reps: Int?
        let volumeKg: Double
        let topSet: TopSet
        /// Total time held, for a timed lift.
        var seconds: Int?
        var last: Last?
        /// Beaten today: heaviest, e1rm, volume, reps (most impressive first).
        var bests: [String] = []
        var firstTime = false
        var next: Next?
    }

    struct TopSet: Decodable, Sendable, Equatable {
        var weightKg: Double?
        var reps: Int?
        var seconds: Int?
    }

    struct Last: Decodable, Sendable, Equatable {
        let date: String
        let volumeKg: Double
        var topWeightKg: Double?
        var bestReps: Int?
    }

    /// Next session's target after the progression guard.
    struct Next: Decodable, Sendable, Equatable {
        var targetWeightKg: Double?
        var targetReps: Int?
        var hint: String?
        /// Why a load rise was held: effort, big_jump, one_change, life_load, phase, mountain_reentry.
        var held: String?
        /// up, down, hold or reps.
        var change: String?
    }

    private enum CodingKeys: String, CodingKey {
        case sessionId, name, date, durationMinutes, volumeKg, setCount, repCount, previous, bestCount, goingUp, holding, exercises
    }
}

extension StrengthSummary.Exercise {
    private enum CodingKeys: String, CodingKey {
        case exerciseName, setCount, reps, volumeKg, topSet, seconds, last, bests, firstTime, next
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        exerciseName = try container.decode(String.self, forKey: .exerciseName)
        setCount = try container.decode(Int.self, forKey: .setCount)
        reps = try container.decodeIfPresent(Int.self, forKey: .reps)
        volumeKg = try container.decodeIfPresent(Double.self, forKey: .volumeKg) ?? 0
        topSet = try container.decodeIfPresent(StrengthSummary.TopSet.self, forKey: .topSet) ?? .init()
        seconds = try container.decodeIfPresent(Int.self, forKey: .seconds)
        last = try container.decodeIfPresent(StrengthSummary.Last.self, forKey: .last)
        bests = try container.decodeIfPresent([String].self, forKey: .bests) ?? []
        firstTime = try container.decodeIfPresent(Bool.self, forKey: .firstTime) ?? false
        next = try container.decodeIfPresent(StrengthSummary.Next.self, forKey: .next)
    }

    init(exerciseName: String, setCount: Int, reps: Int?, volumeKg: Double, topSet: StrengthSummary.TopSet, seconds: Int?) {
        self.exerciseName = exerciseName
        self.setCount = setCount
        self.reps = reps
        self.volumeKg = volumeKg
        self.topSet = topSet
        self.seconds = seconds
    }
}
