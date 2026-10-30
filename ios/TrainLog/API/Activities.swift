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
        var startedAt: String?
        var completedAt: String?
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

/// `GET /activities/{id}`: the summary plus stats, stream charts, zones, efforts, strength sets and
/// analysis. Everything past `activity` is optional: manual activities have none of it.
struct ActivityDetail: Decodable, Sendable {
    let activity: ActivitySummary
    let stats: [Stat]
    let charts: [Chart]
    let feedback: ActivityFeedback?
    let sessionTags: SessionTags?
    let strengthDetail: StrengthDetail?
    var analysis: Analysis?
    var heartRateZones: Zones?
    var powerZones: Zones?
    var cycling: Cycling?
    var bestEfforts: BestEfforts?
    var route: Route?
    var win: Win?
    var mountainRegion: String?
    /// Form averages and per-km splits from the run's HealthFit FIT file; nil without one.
    var runDynamics: RunDynamics?
    /// How a planned bike workout was ridden (indoor rides from the workout library).
    var workoutExecution: WorkoutExecution?

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

        /// `t` is minutes from the start, `x` km along the route.
        struct Point: Decodable, Sendable {
            let t: Double
            var x: Double?
            let y: Double?
        }
    }

    /// Heart-rate or power zones. Bounds are bpm or watts; the top zone has no upper bound.
    struct Zones: Decodable, Sendable {
        let available: Bool?
        let ftpWatts: Double?
        let zone2Pct: Double?
        let zones: [Zone]?

        struct Zone: Decodable, Sendable {
            let key: String
            let label: String
            let minutes: Double?
            let pct: Double?
            let bpmRange: String?
            let wattRange: String?
            let lowerBpm: Double?
            let upperBpm: Double?
            let lowerWatts: Double?
            let upperWatts: Double?

            var lower: Double? { lowerBpm ?? lowerWatts }
            var upper: Double? { upperBpm ?? upperWatts }
            var range: String? { bpmRange ?? wattRange }
        }
    }

    struct Cycling: Decodable, Sendable {
        let environment: String?
        let ftpWatts: Double?
        var hrLoad: Double?
        let powerSource: String?
        let power: Power?
        let estimatedPower: Power?
        let powerEfforts: [PowerEffort]?
        let decoupling: Decoupling?

        struct Power: Decodable, Sendable {
            let avgWatts: Double?
            let normalizedWatts: Double?
            let intensityFactor: Double?
            let tss: Double?
            let variabilityIndex: Double?
            let workKj: Double?
            let errorBandPct: Double?
        }

        struct PowerEffort: Decodable, Sendable {
            let durationS: Double
            let label: String
            let watts: Double?
            let pctOfBest: Double?
            let bestWatts: Double?
            let isRecord: Bool?
        }

        struct Decoupling: Decodable, Sendable {
            let available: Bool?
            let decouplingPct: Double?
            let reasonLabel: String?
        }
    }

    struct BestEfforts: Decodable, Sendable {
        let efforts: [Effort]

        struct Effort: Decodable, Sendable {
            let label: String
            let durationS: Double
            let metricValue: Double?
            let metricUnit: String?
            let avgHr: Double?
        }
    }

    struct Route: Decodable, Sendable {
        let polyline: String?
    }

    struct RunDynamics: Decodable, Sendable {
        let cadenceSpm: Double?
        let stanceTimeMs: Double?
        let verticalOscillationCm: Double?
        let verticalRatioPct: Double?
        let stepLengthM: Double?
        let avgPowerW: Double?
        let splits: [Split]

        /// One completed kilometre.
        struct Split: Decodable, Sendable {
            let km: Int
            let seconds: Double
            let heartRate: Double?
            let cadenceSpm: Double?
            let powerW: Double?
            var stanceTimeMs: Double?
            var verticalOscillationCm: Double?
            var verticalRatioPct: Double?
            var stepLengthM: Double?
        }
    }

    struct WorkoutExecution: Decodable, Sendable {
        let workoutName: String?
        let status: String?
        let verdict: String?
        let verdictLabel: String?
        let ratio: Double?
        let inZonePct: Double?
        var explanation: String?
        let drift: Drift?
        let blocks: [Block]?

        struct Drift: Decodable, Sendable {
            let firstHr: Double?
            let secondHr: Double?
            let firstWatts: Double?
            let secondWatts: Double?
            let decouplingPct: Double?
        }

        struct Block: Decodable, Sendable {
            let durationMin: Double?
            var targetWatts: Double?
            var avgWatts: Double?
        }
    }

    struct Win: Decodable, Sendable {
        let kind: String?
        let headline: String?
        let detail: String?
    }

    struct StrengthDetail: Decodable, Sendable {
        let session: Session?
        var progression: Progression?

        struct Session: Decodable, Sendable {
            let setCount: Int?
            var repCount: Int?
            var exerciseCount: Int?
            let totalVolumeKg: Double?
            var totalDurationSeconds: Double?
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

        /// Each lift against its most recent earlier session, keyed by a slug of the name.
        struct Progression: Decodable, Sendable {
            let exercises: [String: Lift]

            struct Lift: Decodable, Sendable {
                let exerciseName: String
                let metric: String?
                let delta: Double?
                let direction: String?
                let isPr: Bool?
                let nextHint: String?
                let current: Snapshot?
                let previous: Snapshot?

                struct Snapshot: Decodable, Sendable {
                    let volumeKg: Double?
                    let date: String?
                    var sets: [SetSnapshot]?
                }

                struct SetSnapshot: Decodable, Sendable, Equatable {
                    let reps: Int?
                    let weightKg: Double?
                }
            }
        }
    }

    struct Analysis: Decodable, Sendable {
        /// False for activity types the coach can't analyse (physio, yoga…).
        var available: Bool?
        let status: String?
        let headline: String?
        let summary: String?
        var keyObservations: [String]?
        let sessionRead: SessionRead?

        struct SessionRead: Decodable, Sendable {
            let verdict: Verdict?
            let wins: [Win]?
            var signals: [Signal]?
            var nextTime: String?

            struct Verdict: Decodable, Sendable {
                let tone: String?
                var badge: String?
                let headline: String?
            }

            struct Win: Decodable, Sendable {
                var headline: String?
                let detail: String?
            }

            struct Signal: Decodable, Sendable {
                var key: String?
                let label: String
                let value: String?
                let detail: String?
                let tone: String?
                let series: [Double?]?
            }
        }
    }
}

/// `GET /running/fitness`: only running form, your usual values and the good ranges.
struct RunningFitness: Decodable, Sendable {
    let form: Form?

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
}
