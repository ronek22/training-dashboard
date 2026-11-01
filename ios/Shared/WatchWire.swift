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
            /// Not a server call: what the phone has open (`Live` with its pending workout, rehab
            /// step or strength session). Works before the mirrored workout links, so the ready
            /// screen and Start don't wait for it.
            case leading
            /// Not a server call: a button pressed on the Watch (`path` is the `Command`).
            case command
            /// Not a server call: a step of linking up, for the phone's link log (`path` is the text).
            case event
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

    /// What the Watch and the phone send each other over the mirrored workout session, both ways.
    /// Every field is optional; each message carries only what changed.
    struct Live: Codable, Sendable, Equatable {
        /// From the Watch, at most every 3 s.
        var heartRate: Double?
        var activeKcal: Double?
        /// The rehab routine, from whichever device runs it (the one it was started on).
        var rehab: Rehab?
        /// The strength session after a change on the sending device.
        var strength: Strength?
        /// A button pressed on the other device.
        var command: Command?
        /// A workout open on the phone and not started yet: both devices show Start.
        var pending: Pending?
    }

    /// What the phone has open before Start, for the Watch's ready screen.
    struct Pending: Codable, Sendable, Equatable {
        enum Kind: String, Codable, Sendable { case strength, rehab }

        let kind: Kind
        let title: String
        /// "5 exercises · ~45 min".
        var detail: String?
    }

    /// Where a rehab routine is. The device it was started on runs it (timers, ticks, the
    /// completion); the other draws the same step and sends `Command`s back.
    struct Rehab: Codable, Sendable, Equatable {
        /// The routine (`GuidedSession` JSON) as the leading device loaded it. Sent at the start and
        /// when asked: the other device's own copy loses exercises as they're ticked, so the steps
        /// wouldn't line up. Nil in the updates in between.
        var session: Data?
        var startedAt: Date
        var index: Int
        /// When the current timed step ends; nil on rep steps and while paused.
        var endsAt: Date?
        var pausedLeft: Int?
        var finished = false
        /// Left without saving.
        var discarded = false
    }

    /// The strength session as the sending device has it now. The receiver merges it set by set
    /// (`StrengthLogic.merge`), so a copy that crossed a newer tap never undoes it.
    struct Strength: Codable, Sendable, Equatable {
        /// `StrengthSession` JSON.
        var session: Data
        /// The set the sender just logged, so the receiver starts the same rest (no effort question there).
        var loggedSetId: Int?
        var restEndsAt: Date?
    }

    enum Command: String, Codable, Sendable {
        /// Start pressed on the Watch's ready screen: the phone starts the workout for both.
        case start
        case next, back, pause
        /// Send everything again, routine included (the other device just attached).
        case sync
        /// The workout ended on the other device, which already told the server. Before Start,
        /// `discard` means the phone closed the workout without starting it.
        case finish, discard
    }
}
