import Foundation

/// `GET /strength/workouts/templates/{id}` as the builder needs it: everything a template stores.
struct TemplateDetail: Decodable, Sendable, Equatable {
    let id: Int
    let name: String
    var notes: String?
    let exercises: [Exercise]

    struct Exercise: Decodable, Sendable, Equatable {
        let exerciseName: String
        let setCount: Int
        let targetReps: Int
        var targetWeightKg: Double?
        var restSeconds: Int?
        var notes: String?
    }
}

/// Body of `POST /templates` and `PUT /templates/{id}` (`StrengthTemplateInput`).
struct TemplateInput: Encodable, Sendable, Equatable {
    let name: String
    let notes: String?
    let exercises: [Exercise]

    struct Exercise: Encodable, Sendable, Equatable {
        let exerciseName: String
        let setCount: Int
        let targetReps: Int
        let targetWeightKg: Double?
        let restSeconds: Int
        let notes: String?
        /// A hold: each set is timed (one-time sessions only).
        var targetSeconds: Int? = nil
    }
}

extension TemplateInput {
    /// A bodyweight day's exercises as a one-time session.
    init(bodyweight name: String, exercises: [PhoneToday.Exercise]) {
        self.init(name: name, notes: nil, exercises: exercises.map {
            .init(exerciseName: $0.name, setCount: $0.sets, targetReps: $0.seconds == nil ? $0.reps ?? 10 : 1,
                  targetWeightKg: $0.weightKg, restSeconds: $0.restSeconds ?? 60, notes: $0.notes, targetSeconds: $0.seconds)
        })
    }
}

/// `GET /strength/workouts/exercise-suggestions`: the lifts you've done, with last session's sets.
struct ExerciseSuggestion: Decodable, Sendable, Equatable, Identifiable {
    let exerciseName: String
    let normalizedName: String
    var lastPerformedAt: String?
    var sessionCount: Int?
    var suggestedSetCount: Int?
    var suggestedReps: Int?
    var suggestedWeightKg: Double?
    var lastSets: [LastSet]?
    /// Working weight of each of the last six sessions, oldest first.
    var recentSessions: [RecentSession]?

    var id: String { normalizedName }

    struct LastSet: Decodable, Sendable, Equatable {
        var reps: Int?
        var weightKg: Double?
        var isWarmup: Bool?
        var effort: String?
    }

    struct RecentSession: Decodable, Sendable, Equatable {
        let date: String
        let weightKg: Double
    }
}

extension PhoneToday.Strength {
    /// `POST /sessions/one-time` body for a day without a saved workout (a bodyweight day).
    var oneTime: TemplateInput? {
        guard templateId == nil, !exercises.isEmpty else { return nil }
        return TemplateInput(bodyweight: name ?? "Bodyweight", exercises: exercises)
    }
}

extension PlanDay {
    var oneTime: TemplateInput? {
        guard let liftExercises, !liftExercises.isEmpty else { return nil }
        return TemplateInput(bodyweight: title, exercises: liftExercises)
    }
}
