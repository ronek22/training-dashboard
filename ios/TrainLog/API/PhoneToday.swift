import Foundation

/// `GET /phone/today` (backend/app/services/phone_today.py).
struct PhoneToday: Decodable, Sendable {
    let date: String
    let streakDays: Int
    let readiness: Readiness
    let vitals: Vitals
    var checkinDone: Bool
    var sick: Sick?
    var today: Session?
    let tomorrow: Session?
    let week: [WeekDay]
    let weekMinutes: WeekMinutes
    /// Today's rehab ticks; nil without a routine due today (and from an older server).
    var rehab: Rehab?
    /// Today's logged protein against the target; nil without a weigh-in (and from an older server).
    var protein: Protein?
    /// Today's kcal against the Food target, for the evening food row; nil without a target.
    var food: Food?
    /// Sleep need and debt for tonight's lights out; nil with too few nights (and from an older server).
    var sleepNeed: SleepNeed?

    struct Food: Decodable, Sendable, Equatable {
        let eatenKcal: Double
        let targetKcal: Double
    }

    struct SleepNeed: Decodable, Sendable, Equatable {
        let needH: Double
        let debtH: Double
    }

    struct Protein: Decodable, Sendable, Equatable {
        let eatenG: Double
        let targetG: Int
        let hit: Bool
    }

    struct Rehab: Decodable, Sendable {
        let title: String
        let done: Int
        let total: Int
        let durationMin: Int
    }

    struct Readiness: Decodable, Sendable {
        let level: String
        let label: String
        let advice: String?
        let suggestsSwap: Bool
        var factors: [Factor]?
    }

    /// One readiness signal; tone is steady, caution or risk, points how much it pulls the read down.
    struct Factor: Decodable, Sendable, Identifiable {
        let key: String
        let label: String
        let tone: String
        let points: Int
        var id: String { key }
    }

    struct Vitals: Decodable, Sendable {
        let restingHr: Double?
        let sleepH: Double?
        let pain: Int?
        /// HRV, resting HR and sleep against their typical range.
        var ranges: [VitalRange]?
    }

    /// The latest reading and the middle 80% of the month before (nil with too little history).
    struct VitalRange: Decodable, Sendable, Identifiable {
        let key: String
        let value: Double
        let date: String
        var low: Double?
        var high: Double?
        var id: String { key }
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
        /// Why this session is in the plan, for the morning brief.
        var purpose: String?
        var status: String?
        let sport: Sport?
        let fallback: String?
        let strength: Strength?

        var isDone: Bool { ["matched", "linked", "rest_day_changed"].contains(status ?? "") }
    }

    struct Strength: Decodable, Sendable {
        /// Nil on a bodyweight day: no saved workout, the exercises start as a one-time session.
        let templateId: Int?
        var name: String?
        let exercises: [Exercise]
        let lastDone: String?
    }

    struct Exercise: Decodable, Sendable {
        let name: String
        let sets: Int
        let reps: Int?
        let weightKg: Double?
        var restSeconds: Int?
        var notes: String?
        /// A hold: seconds per set instead of reps.
        var seconds: Int?
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
