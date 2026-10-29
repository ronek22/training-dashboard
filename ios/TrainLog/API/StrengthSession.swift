import Foundation

/// `GET /strength/workouts/sessions/{id}` (backend/app/services/strength_workouts.py `_serialize_session`).
/// Codable so the live session survives an app restart or a dropped connection.
struct StrengthSession: Codable, Sendable, Equatable {
    let id: Int
    let templateId: Int?
    let templateName: String
    var status: String
    let startedAt: String
    var completedAt: String?
    var currentExerciseOrder: Int
    var currentSetOrder: Int
    var exercises: [Exercise]

    struct Exercise: Codable, Sendable, Equatable, Identifiable {
        let id: Int
        let exerciseOrder: Int
        let exerciseName: String
        let notes: String?
        var sets: [WorkoutSet]

        var workingSets: [WorkoutSet] { sets.filter { !$0.isWarmup } }
        var isDone: Bool { !sets.isEmpty && sets.allSatisfy(\.isCompleted) }
    }

    struct WorkoutSet: Codable, Sendable, Equatable, Identifiable {
        let id: Int
        let setOrder: Int
        let targetReps: Int
        let targetWeightKg: Double?
        let restSeconds: Int
        var actualReps: Int?
        var actualWeightKg: Double?
        var status: String
        var setType: String?
        var effort: String?

        var isCompleted: Bool { status == "completed" }
        var isWarmup: Bool { setType == "warmup" }
    }

    var isActive: Bool { status == "active" }
}

/// `GET /strength/workouts/templates/{id}`: the session brief and the per-lift progression hint.
struct StrengthTemplate: Decodable, Sendable, Equatable {
    let id: Int
    let name: String
    var estimatedDurationMinutes: Int?
    let exercises: [Exercise]

    struct Exercise: Decodable, Sendable, Equatable {
        let exerciseName: String
        var setCount: Int?
        var targetReps: Int?
        var targetWeightKg: Double?
        var notes: String?
        let next: Next?
    }

    /// Progressed target for today (`_next_steps`), after the progression guard.
    struct Next: Decodable, Sendable, Equatable {
        var targetWeightKg: Double?
        var targetReps: Int?
        let hint: String?
        let basedOnDate: String?
        /// Why a load rise was held: effort, big_jump, one_change, life_load, phase, mountain_reentry.
        var held: String?
        var last: Last?
    }

    /// Last session's heaviest working set of the lift.
    struct Last: Decodable, Sendable, Equatable {
        let date: String
        let weightKg: Double?
        let reps: Int
        var setCount: Int?
    }
}

/// Backend effort values (`StrengthSetEffortRequest`) behind the Easy · Good · Hard taps.
enum SetEffort: String, CaseIterable, Sendable {
    case easy, solid, grinding

    var label: String {
        switch self {
        case .easy: "Easy"
        case .solid: "Good"
        case .grinding: "Hard"
        }
    }

    init?(backend: String?) {
        guard let backend else { return nil }
        if backend == "form" { self = .grinding } else { self.init(rawValue: backend) }
    }
}
