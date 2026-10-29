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
