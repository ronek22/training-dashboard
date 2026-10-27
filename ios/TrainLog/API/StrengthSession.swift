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

/// `GET /strength/workouts/templates/{id}`: only the per-lift progression hint is used.
struct StrengthTemplate: Decodable, Sendable {
    let id: Int
    let name: String
    let exercises: [Exercise]

    struct Exercise: Decodable, Sendable {
        let exerciseName: String
        let next: Next?
    }

    struct Next: Decodable, Sendable {
        let hint: String?
        let basedOnDate: String?
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
