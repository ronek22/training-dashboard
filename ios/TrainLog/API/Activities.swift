import Foundation

/// One row of `GET /activities` (backend/app/services/activities.py), and the `activity` block of
/// `GET /activities/{id}`. Only the fields the phone shows.
struct ActivitySummary: Decodable, Sendable, Identifiable, Equatable {
    let id: String
    let date: String
    let type: String
    let name: String
    let displayName: String?
    let distanceKm: Double?
    let durationMin: Double?
    let avgHr: Double?
    let maxHr: Double?
    let avgWatts: Double?
    let elevationM: Double?
    let createdAt: String?
    let workoutIntent: String?
    let workoutIntentLabel: String?
    let guidedSession: GuidedSession?
    let recordedStrengthSession: RecordedStrength?
    var feedback: ActivityFeedback?
    var sessionTags: SessionTags?

    struct GuidedSession: Decodable, Sendable, Equatable {
        let title: String?
        let contextLabel: String?
    }

    struct RecordedStrength: Decodable, Sendable, Equatable {
        let id: Int
        let name: String?
    }

    var title: String { displayName ?? name }
}

struct ActivityFeedback: Decodable, Sendable, Equatable {
    let rpe: Int?
    let energy: Int?
    let muscleSoreness: Int?
    let painLevel: Int?
    let note: String?
}

struct SessionTags: Codable, Sendable, Equatable {
    var verdict: String?
}

/// `POST /activities/{id}/feedback`. The server needs all four scales.
struct ActivityFeedbackInput: Encodable, Sendable, Equatable {
    var rpe: Int
    var energy: Int
    var muscleSoreness: Int
    var painLevel: Int
    var note: String?
}

/// `GET /activities/{id}`: the summary plus stats, stream charts, strength sets and analysis.
struct ActivityDetail: Decodable, Sendable {
    let activity: ActivitySummary
    let stats: [Stat]
    let charts: [Chart]
    let feedback: ActivityFeedback?
    let sessionTags: SessionTags?
    let strengthDetail: StrengthDetail?
    let analysis: Analysis?

    struct Stat: Decodable, Sendable {
        let key: String
        let label: String
        let value: StatValue?
        let unit: String?
    }

    /// Numbers mostly, but run pace comes as "5:38".
    enum StatValue: Decodable, Sendable, Equatable {
        case number(Double)
        case text(String)

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let number = try? container.decode(Double.self) {
                self = .number(number)
            } else {
                self = .text(try container.decode(String.self))
            }
        }

        var number: Double? {
            if case .number(let value) = self { value } else { nil }
        }
    }

    struct Chart: Decodable, Sendable {
        let key: String
        let label: String
        let unit: String?
        let points: [Point]

        /// `t` is minutes from the start.
        struct Point: Decodable, Sendable {
            let t: Double
            let y: Double?
        }
    }

    struct StrengthDetail: Decodable, Sendable {
        let session: Session?

        struct Session: Decodable, Sendable {
            let setCount: Int?
            let totalVolumeKg: Double?
            let exercises: [Exercise]
        }

        struct Exercise: Decodable, Sendable, Identifiable {
            let id: String
            let exerciseName: String
            let workSetCount: Int?
            let sets: [LiftSet]

            struct LiftSet: Decodable, Sendable {
                let reps: Int?
                let weightKg: Double?
                let isWarmup: Bool?
            }
        }
    }

    struct Analysis: Decodable, Sendable {
        let status: String?
        let headline: String?
        let summary: String?
        let sessionRead: SessionRead?

        struct SessionRead: Decodable, Sendable {
            let verdict: Verdict?
            let wins: [Win]?

            struct Verdict: Decodable, Sendable {
                let tone: String?
                let headline: String?
            }

            struct Win: Decodable, Sendable {
                let detail: String?
            }
        }
    }
}
