import Foundation

/// `GET /checkins/today` and `POST /checkins` (backend/app/services/checkins.py).
struct CheckinResponse: Decodable, Sendable {
    let checkin: DailyCheckin?
}

struct DailyCheckin: Decodable, Sendable, Equatable {
    let date: String
    let energy: Int
    let muscleSoreness: Int
    let stress: Int
    let sleepQuality: Int
    let painLevel: Int?
    let note: String?
}

struct CheckinInput: Encodable, Sendable, Equatable {
    let date: String
    let energy: Int
    let muscleSoreness: Int
    let stress: Int
    let sleepQuality: Int
    let painLevel: Int
    let note: String?
}

/// `GET /sick-mode`; the phone only needs whether it's on.
struct SickModeResponse: Decodable, Sendable {
    let sickMode: State

    struct State: Decodable, Sendable {
        let active: Bool
    }
}

struct SickModeInput: Encodable, Sendable {
    var severity = "above_neck"
}

/// `POST /metrics`.
struct MetricInput: Encodable, Sendable, Equatable {
    let date: String
    let metric: String
    let value: Double
    let unit: String?
}

/// `GET /metrics/{name}`, newest first.
struct MetricPoint: Decodable, Sendable {
    let date: String
    let value: Double
}

/// `GET /life-load?start=&end=` (backend/app/services/life_load.py); only the day's tags are used.
struct LifeLoadResponse: Decodable, Sendable {
    let days: [Day]

    struct Day: Decodable, Sendable {
        let date: String
        let tags: [String]
        let note: String?
    }
}

/// `PUT /life-load/{day}`: replaces the day's tags, an empty list clears it.
struct LifeLoadInput: Encodable, Sendable, Equatable {
    let tags: [String]
    let note: String?
}

/// `GET /strength/muscle-gain`, only its `weight` block (backend/app/services/muscle_gain.py `_weight`).
struct MuscleGainWeight: Decodable, Sendable {
    let weight: WeightTrend
}

/// The body-weight trend: 7-day trailing average over 6 weeks, judged against a gentle lean gain.
struct WeightTrend: Decodable, Sendable, Equatable {
    let available: Bool
    /// gentle_gain, fast_gain, flat, losing, or unavailable.
    let status: String
    var minWeighIns: Int?
    var weighIns: [Point]?
    var smoothed: [Point]?
    var endKg: Double?
    var kgPerWeek: Double?

    struct Point: Decodable, Sendable, Equatable {
        let date: String
        let kg: Double
    }
}

#if DEBUG
extension WeightTrend {
    /// Live on 3 Nov for `trend`; the other states are made up.
    static func demo(_ stage: String) -> WeightTrend {
        let live: [(String, Double)] = [("2026-10-12", 79.0), ("2026-10-18", 78.65), ("2026-10-25", 80.5), ("2026-10-29", 80.25),
                                        ("2026-10-30", 79.83), ("2026-11-01", 79.67), ("2026-11-02", 79.75)]
        let points = live.map { Point(date: $0.0, kg: $0.1) }
        switch stage {
        case "sparse":
            return WeightTrend(available: false, status: "unavailable", minWeighIns: 4, weighIns: Array(points.prefix(2)))
        case "flat":
            return WeightTrend(available: true, status: "flat", smoothed: points.map { Point(date: $0.date, kg: 79.6 - Double($0.date.suffix(2))! * 0.004) },
                               endKg: 79.5, kgPerWeek: -0.1)
        case "fast":
            return WeightTrend(available: true, status: "fast_gain", smoothed: points.enumerated().map { Point(date: $1.date, kg: 78 + Double($0) * 0.4) },
                               endKg: 80.4, kgPerWeek: 0.6)
        default:
            return WeightTrend(available: true, status: "gentle_gain", minWeighIns: 4, weighIns: points, smoothed: points,
                               endKg: 79.75, kgPerWeek: 0.25)
        }
    }
}
#endif
