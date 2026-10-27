import Foundation

/// `GET /phone/today` (backend/app/services/phone_today.py).
struct PhoneToday: Decodable, Sendable {
    let date: String
    let streakDays: Int
    let readiness: Readiness
    let vitals: Vitals
    let checkinDone: Bool
    let sick: Sick?
    let today: Session?
    let tomorrow: Session?
    let week: [WeekDay]
    let weekMinutes: WeekMinutes

    struct Readiness: Decodable, Sendable {
        let level: String
        let label: String
        let advice: String?
        let suggestsSwap: Bool
    }

    struct Vitals: Decodable, Sendable {
        let restingHr: Double?
        let sleepH: Double?
        let pain: Int?
    }

    struct Sick: Decodable, Sendable {
        let label: String?
        let day: Int?
    }

    struct Session: Decodable, Sendable {
        let title: String?
        let sessionType: String?
        let intentLabel: String?
        let durationMin: Int?
        let distanceKm: Double?
        let details: String?
        let status: String?
        let sport: Sport?
        let fallback: String?
        let strength: Strength?

        var isDone: Bool { ["matched", "linked", "rest_day_changed"].contains(status ?? "") }
    }

    struct Strength: Decodable, Sendable {
        let templateId: Int
        let exercises: [Exercise]
        let lastDone: String?
    }

    struct Exercise: Decodable, Sendable {
        let name: String
        let sets: Int
        let reps: Int?
        let weightKg: Double?
    }

    struct WeekDay: Decodable, Sendable, Identifiable {
        let date: String
        let label: String
        let title: String?
        let sport: Sport
        let status: String
        let doneSports: [Sport]

        var id: String { date }
    }

    struct WeekMinutes: Decodable, Sendable {
        let done: Int
        let planned: Int
        let bySport: [SportMinutes]
    }

    struct SportMinutes: Decodable, Sendable {
        let sport: Sport
        let minutes: Int
    }
}
