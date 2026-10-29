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
