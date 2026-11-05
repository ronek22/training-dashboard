import Foundation

/// `GET /plans/week-brief?week_start=` (backend/app/services/week_brief.py `build_week_brief`):
/// the week's rules in their fixed order (safety, anchor, block, outcome, habit), each with its
/// source, plus the weekly lift slots and the arc block's target.
struct WeekBrief: Decodable, Sendable, Equatable {
    let weekStart: String
    let headline: String
    let lines: [Line]
    let lifts: Lifts
    var block: Block? = nil
    var protectedAreas: [String] = []

    struct Line: Decodable, Sendable, Equatable {
        /// safety, anchor, block, outcome or habit.
        let priority: String
        let priorityLabel: String
        let text: String
        let source: String
        let key: String
    }

    struct Lifts: Decodable, Sendable, Equatable {
        /// "slots" for the fixed weekly lifts, "rotation" for the rotating pointer.
        let mode: String
        var slots: [Slot] = []
        var next: String? = nil
    }

    struct Slot: Decodable, Sendable, Equatable {
        /// "Upper 1", "Lower", "Upper 2".
        let slot: String
        let templateId: String
        /// "Workout C · Wide Shoulders".
        let label: String
        let focusArea: String
        /// The lower-body workout this one stands in for while a leg is protected.
        var swappedFrom: String? = nil
        var reason: String? = nil
    }

    struct Block: Decodable, Sendable, Equatable {
        let label: String
        let weekNumber: Int
        let weeksInBlock: Int
        let lighter: Bool
        let rideHours: Double
        let rideMix: WinterArc.RideMix
    }
}
