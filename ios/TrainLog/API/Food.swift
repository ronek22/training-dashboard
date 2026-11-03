import Foundation

/// `GET /nutrition/food?date=` (backend/app/services/food_log.py), only the fields the phone shows.
struct FoodDay: Decodable, Sendable {
    let date: String
    let entries: [FoodEntry]
    let totals: Macros
    let target: Target?
    let proteinTargetG: Double?
    /// The 7 days ending on `date`, judged against their targets (drives the week strip dots).
    var week: [WeekDay]? = nil

    struct WeekDay: Decodable, Sendable, Equatable {
        let date: String
        let logged: Bool
        let finished: Bool
        let targetKcal: Double?
        let under: Bool
    }

    struct Target: Decodable, Sendable {
        let kcal: Double
        let dayKind: String?
        let carbsG: Double?
    }
}

struct Macros: Codable, Sendable, Equatable {
    var kcal: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double

    static let zero = Macros(kcal: 0, proteinG: 0, carbsG: 0, fatG: 0)
}

struct FoodEntry: Decodable, Sendable, Identifiable {
    let id: Int
    let date: String
    let meal: String
    let source: String
    let rawText: String?
    let createdAt: String?
    let items: [FoodItem]
    let totals: Macros
}

/// One food row, as the server stores it and as Claude estimates it.
struct FoodItem: Codable, Sendable, Equatable, Identifiable {
    var id = UUID()
    var name: String
    var grams: Double?
    var kcal: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    var confidence: String?
    var portions: Double?

    enum CodingKeys: String, CodingKey {
        case name, grams, kcal, proteinG, carbsG, fatG, confidence, portions
    }

    init(name: String, grams: Double? = nil, kcal: Double, proteinG: Double, carbsG: Double = 0, fatG: Double = 0,
         confidence: String? = nil, portions: Double? = nil) {
        self.name = name
        self.grams = grams
        self.kcal = kcal
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.confidence = confidence
        self.portions = portions
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        grams = try c.decodeIfPresent(Double.self, forKey: .grams)
        kcal = try c.decodeIfPresent(Double.self, forKey: .kcal) ?? 0
        proteinG = try c.decodeIfPresent(Double.self, forKey: .proteinG) ?? 0
        carbsG = try c.decodeIfPresent(Double.self, forKey: .carbsG) ?? 0
        fatG = try c.decodeIfPresent(Double.self, forKey: .fatG) ?? 0
        confidence = try c.decodeIfPresent(String.self, forKey: .confidence)
        portions = try c.decodeIfPresent(Double.self, forKey: .portions)
    }
}

/// `POST /nutrition/food/entries`.
struct FoodEntryInput: Encodable, Sendable {
    let date: String
    let meal: String
    let source: String
    let rawText: String?
    let items: [FoodItem]
}

/// `GET /nutrition/dinners?week_start=`: the planned main meal per day.
struct DinnerWeek: Decodable, Sendable {
    let days: [Day]

    struct Day: Decodable, Sendable {
        let date: String
        let dish: String?
        let kcal: Double?
        let proteinG: Double?
        let logged: Bool
    }
}

/// `GET /nutrition/dinners/{day}/log-items`.
struct DinnerLogItems: Decodable, Sendable {
    let dish: String?
    let items: [FoodItem]
}

/// `POST /phone/meal-estimate` body: a description, a photo, or both.
struct MealEstimateRequest: Encodable, Sendable {
    struct Photo: Encodable, Sendable {
        let mediaType: String
        let data: String
    }

    let text: String
    let image: Photo?
}

/// `POST /phone/meal-estimate` and `GET /phone/meal-estimate/{id}` (relayed to the coach helper).
struct MealEstimateJob: Decodable, Sendable {
    let jobId: String
    let status: String
    let message: String?
    let estimate: Estimate?

    struct Estimate: Decodable, Sendable {
        let items: [FoodItem]
        let note: String?
    }
}

/// `GET /phone/food/quick?date=&hour=` (backend/app/services/phone_food.py): what the top of Food offers.
struct FoodQuick: Decodable, Sendable {
    let date: String
    let slot: String
    let again: [Again]
    let gap: Gap?
    let fuel: Fuel?

    /// A meal to log again: yesterday's for this time of day, a repeat from the last 30 days, or a saved food.
    struct Again: Decodable, Sendable, Identifiable {
        let key: String
        let kind: String
        let meal: String
        let date: String?
        let count: Int
        let title: String
        let items: [FoodItem]
        let totals: Macros

        var id: String { key }
    }

    /// Evening picks from the athlete's own log that close what's still missing.
    struct Gap: Decodable, Sendable {
        /// "both", "protein" (kcal is nearly there) or "refuel" (after a long ride).
        let focus: String
        let meal: String
        let left: Left
        let picks: [Pick]

        struct Left: Decodable, Sendable {
            let kcal: Double
            let proteinG: Double
        }
    }

    struct Pick: Decodable, Sendable, Identifiable {
        let key: String
        let title: String
        let source: String
        let lastDate: String?
        let count: Int
        let portions: Double
        let items: [FoodItem]
        let totals: Macros

        var id: String { key }
    }

    /// Today's planned ride fuel, until the ride is recorded.
    struct Fuel: Decodable, Sendable {
        let title: String
        let durationMin: Int
        let totalCarbsG: Double
        let bottles: Int
        let carbsGPerH: Rate
        let blocks: [[Int]]
        let stops: [Stop]

        struct Rate: Decodable, Sendable {
            let target: Double
        }

        struct Stop: Decodable, Sendable {
            let min: Int
            let carbsG: Double
        }
    }
}
