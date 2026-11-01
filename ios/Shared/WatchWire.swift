import Foundation

/// What the Watch and the iPhone send each other over WatchConnectivity. The Watch never talks to
/// the server itself: it asks the phone (`TrainLog/Watch/WatchRelay.swift`), which already knows the
/// server address, the offline cache and the write queue.
enum WatchWire {
    /// One HTTP call the phone makes for the Watch.
    struct Envelope: Codable, Sendable, Equatable {
        enum Kind: String, Codable, Sendable {
            /// Needs the server's answer now (loading today, starting a session).
            case request
            /// Fire and forget: the phone appends it to its write queue, which replays it in order.
            case write
        }

        let kind: Kind
        let method: String
        let path: String
        var body: Data?
    }

    struct Reply: Codable, Sendable, Equatable {
        /// HTTP status; nil when the server couldn't be reached.
        var status: Int?
        var data: Data?
        /// The phone answered from its cache because the server was unreachable.
        var fromCache = false
    }

    /// Live numbers the Watch sends to the iPhone's mirrored workout session.
    struct Live: Codable, Sendable, Equatable {
        var heartRate: Double?
        var activeKcal: Double?
        /// A rehab routine running on the Watch, for the phone to follow along.
        var rehab: Rehab?
    }

    /// Where the Watch's rehab routine is. The Watch runs it (timers, ticks, the completion); the
    /// phone draws the same step with its demo and sends `Command`s back.
    struct Rehab: Codable, Sendable, Equatable {
        /// The routine (`GuidedSession` JSON) as the Watch loaded it. Sent at the start and when the
        /// phone asks: the phone's own copy loses exercises as they're ticked, so the steps wouldn't
        /// line up. Nil in the updates in between.
        var session: Data?
        var startedAt: Date
        var index: Int
        /// When the current timed step ends; nil on rep steps and while paused.
        var endsAt: Date?
        var pausedLeft: Int?
        var finished = false
        /// Left on the Watch without saving.
        var discarded = false
    }

    /// The phone steering the Watch's rehab routine.
    struct Command: Codable, Sendable, Equatable {
        enum Action: String, Codable, Sendable {
            case next, back, pause
            /// Send everything again, routine included (the phone just attached).
            case sync
        }

        let action: Action
    }
}
