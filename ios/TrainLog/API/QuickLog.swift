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

/// `POST /activities` for a session that never reached Strava (backend/app/models/activities.py).
struct ActivityInput: Encodable, Sendable, Equatable {
    let id: String
    let date: String
    let type: String
    let name: String?
    let durationMin: Double
    let distanceKm: Double?
    let notes: String?
}

/// `POST /notes`: a coach note, the same table the MCP `add_coach_note` writes.
struct NoteInput: Encodable, Sendable, Equatable {
    let date: String
    let category: String
    let content: String
}
