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
    }
}
