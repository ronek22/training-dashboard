import Foundation

/// `GET /strength/workouts/exercise-history?name=…` (backend/app/services/exercise_history.py):
/// the last few sessions of one lift, newest first, and the best set ever.
struct LiftHistory: Codable, Sendable, Equatable {
    let exerciseName: String
    let sessionCount: Int
    let sessions: [Session]
    let best: Best?

    struct Session: Codable, Sendable, Equatable {
        let date: String
        let sets: [HistorySet]
        let topLoadKg: Double?
        let bestReps: Int?
        let bestSeconds: Int?
    }

    struct HistorySet: Codable, Sendable, Equatable {
        let reps: Int?
        let weightKg: Double?
        let seconds: Int?
        let effort: String?
    }

    struct Best: Codable, Sendable, Equatable {
        let date: String
        let weightKg: Double?
        let reps: Int?
        let seconds: Int?
    }
}

/// The bar and plates from the Athlete page (`GET /settings/athlete-profile`), for the plate maths.
struct GymKit: Codable, Sendable, Equatable {
    var barWeightKg: Double?
    var plates: [Plate]?

    struct Plate: Codable, Sendable, Equatable {
        let kg: Double
        let count: Int
    }

    /// The backend's own defaults, used until the profile has loaded.
    static let standard = GymKit(
        barWeightKg: 20,
        plates: [25, 20, 15, 10, 5, 2.5, 1.25].map { Plate(kg: $0, count: 2) }
    )

    var bar: Double { barWeightKg ?? 20 }
}

extension LiftHistory: Identifiable {
    var id: String { exerciseName }
}
