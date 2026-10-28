import ActivityKit
import Foundation

/// The strength workout on the Lock Screen and in the Dynamic Island: the rest timer between sets
/// and what's up next, so the phone can stay locked. Started and updated by `StrengthActivity`.
struct StrengthActivityAttributes: ActivityAttributes {
    let sessionId: Int
    let workout: String
    let startedAt: Date

    struct ContentState: Codable, Hashable, Sendable {
        /// The set up next (after a set is logged, the one the rest leads into).
        var exercise: String
        var setLabel: String
        var load: String
        var exerciseNumber: Int
        var exerciseCount: Int
        var setsDone: Int
        var setsTotal: Int
        var restStart: Date?
        var restEnd: Date?
        var allSetsDone: Bool

        var restRange: ClosedRange<Date>? {
            guard let restStart, let restEnd, restEnd > restStart else { return nil }
            return restStart...restEnd
        }
    }
}
