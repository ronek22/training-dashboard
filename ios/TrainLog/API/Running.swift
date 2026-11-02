import Foundation

/// `GET /running/fitness` (backend/app/services/running_fitness.py): what the run card, the pace
/// guide, the after-run sheet and an activity's running form use.
struct RunningFitness: Decodable, Sendable {
    var available: Bool?
    /// Running form: your usual values and the good ranges.
    var form: Form?
    var summary: Summary?
    var vdot: Vdot?
    var paces: Paces?
    var returnToRun: ReturnToRun?
    /// The last runs, oldest first, with how each felt (nil when not tapped).
    var felt: [FeltRun]?

    struct Summary: Decodable, Sendable {
        let lastRun: LastRun?
    }

    struct LastRun: Decodable, Sendable {
        let date: String
        let daysAgo: Int
    }

    struct Vdot: Decodable, Sendable {
        let current: Double
        let basis: String
        let stale: Bool
        let peak: Peak?
        let projected: Double
        let projectionWeeks: Int
        let shareOfPeakPct: Int?
    }

    struct Peak: Decodable, Sendable {
        let date: String
        let vdot: Double
    }

    struct Paces: Decodable, Sendable {
        let vdot: Double
        let zones: Zones
        let qualityAllowed: Bool
        let hrCapBpm: Int?
        /// Seconds added to the easy band after two hard-feeling runs in a row (older servers omit it).
        var easedS: Int?
        /// The easy band at the peak VDOT.
        var peakEasy: Band?
    }

    struct Zones: Decodable, Sendable {
        let easy: Band
        let marathon: Single
        let threshold: Single
        let interval: Single
        let repetition: Single
    }

    struct Band: Decodable, Sendable, Equatable {
        let fromS: Int
        let toS: Int
    }

    struct Single: Decodable, Sendable {
        let paceS: Int
    }

    struct ReturnToRun: Decodable, Sendable {
        let active: Bool
        var stage: Int?
        var stageName: String?
        var stages: Int?
        var stageNames: [String]?
        var minutes: Int?
        var blocks: [Block]?
        /// False on run/walk stages: no pace target, the easy range is only a hint.
        var paceTarget: Bool?
        var symptom: String?
    }

    struct Block: Decodable, Sendable, Equatable {
        let kind: String
        let minutes: Int

        var isJog: Bool { kind == "jog" }
    }

    struct Form: Decodable, Sendable {
        let baseline: Values?
        let ranges: [String: Range]?

        struct Values: Decodable, Sendable {
            let cadenceSpm: Double?
            let stanceTimeMs: Double?
            let verticalOscillationCm: Double?
            let verticalRatioPct: Double?
            let stepLengthM: Double?
            let avgPowerW: Double?
        }

        struct Range: Decodable, Sendable {
            let good: [Double]
            var note: String?
        }
    }

    struct FeltRun: Decodable, Sendable, Identifiable, Equatable {
        let activityId: String
        let date: String
        let name: String
        let distanceKm: Double
        let durationMin: Double
        let paceS: Int?
        let avgHr: Double?
        var felt: RunFeel?

        var id: String { activityId }
    }
}

/// How a run felt, tapped after it syncs (`PUT /activities/{id}/felt`).
enum RunFeel: String, Codable, Sendable, CaseIterable {
    case easy, ok, hard

    var label: String {
        switch self {
        case .easy: "Easy"
        case .ok: "OK"
        case .hard: "Hard"
        }
    }
}

struct RunFeelInput: Encodable, Sendable {
    let felt: RunFeel
}

/// `PUT /activities/{id}/symptoms`: pain during the run, 0–10.
struct RunSymptomInput: Encodable, Sendable {
    let during: Int
}
