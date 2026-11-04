import Foundation

/// `GET /plans/winter-arc` (backend/app/services/winter_arc.py `build_winter_arc`). Only the
/// blocks: the phone works out where any week sits from their dates.
struct WinterArc: Decodable, Sendable {
    let blocks: [Block]

    struct Block: Decodable, Sendable, Equatable {
        let startDate: String
        let endDate: String
        let weeks: Int
        let focusLabel: String
        let label: String?
        let weeklyHours: Double
        let rideMix: RideMix
        var lighterEvery: Int? = nil
        /// Mondays of the lighter weeks.
        let lighterWeeks: [String]

        var name: String {
            if let label, !label.isEmpty { return label }
            return focusLabel
        }
    }

    struct RideMix: Decodable, Sendable, Equatable {
        var z2: Int? = nil
        var sweetSpot: Int? = nil
        var vo2: Int? = nil
    }
}

/// One row of `GET /strength/workouts/stall-blocks?status=active`
/// (backend/app/services/stall_blocks.py): a plateau fix applied to one lift for a few weeks.
struct StallBlock: Decodable, Sendable, Equatable {
    let exerciseName: String
    let label: String
    let text: String?
    /// "block" for a multi-week block, "today" for a one-session micro-deload.
    let scope: String
    let startedOn: String
    let endsOn: String
    let week: Int
    let weeks: Int
    /// The weeks are up; keep or revert it at the next session.
    let due: Bool
}
