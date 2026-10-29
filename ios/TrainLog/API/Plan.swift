import Foundation

/// One week of `GET /plans/weekly` (backend/app/services/plans.py `serialize_weekly_plan`).
/// Only the fields the phone shows; planning itself stays on the web.
struct WeeklyPlan: Decodable, Sendable, Identifiable {
    let weekStart: String
    let title: String?
    let focus: String?
    let days: [PlanDay]

    var id: String { weekStart }
}

struct PlanDay: Decodable, Sendable, Identifiable {
    let sessionId: String?
    let date: String
    let label: String?
    let sessionType: String
    let workoutIntent: String?
    let workoutIntentLabel: String?
    let templateLabel: String?
    let title: String
    let details: String?
    let check: String?
    let steps: [String]?
    let cues: [String]?
    let fallback: String?
    let targetDurationMin: Int?
    let targetDistanceKm: Double?
    let cyclingWorkoutName: String?
    let comparison: Comparison?
    let rehab: [RehabRoutine]?

    var id: String { date }

    struct Comparison: Decodable, Sendable {
        let status: String
        let label: String?
        let completedActivities: [Completed]?

        struct Completed: Decodable, Sendable {
            let id: String
            let durationMin: Double?
        }
    }
}

struct RehabRoutine: Decodable, Sendable, Identifiable {
    let issueId: Int
    let routineId: Int
    let title: String
    let exercises: [Exercise]
    var ticked: [Int]

    var id: Int { routineId }

    struct Exercise: Decodable, Sendable {
        let name: String?
        let dose: String?
        let how: String?
    }
}

/// `POST /plans/weekly/swap`: exchanges two days of one week, or moves a session onto an empty day.
struct PlanSwap: Encodable, Sendable {
    let fromDate: String
    let toDate: String
}

/// `PUT /recovery/issues/{id}/ticks`.
struct RehabTick: Encodable, Sendable {
    let day: String
    let index: Int
    let done: Bool
}

/// A row of `GET /strength/workouts/templates`: starts a planned lift by name, and lists the
/// workouts in Workout Studio.
struct StrengthTemplateSummary: Decodable, Sendable, Identifiable, Equatable {
    let id: Int
    let name: String
    var exerciseCount: Int?
    var setCount: Int?
    var estimatedDurationMinutes: Int?
    /// Start of the last finished session from this template (ISO with offset); nil when never done.
    var lastDoneAt: String?
    var exercises: [Exercise]?

    struct Exercise: Decodable, Sendable, Equatable {
        let exerciseName: String
    }
}
