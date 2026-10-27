import Foundation
import Testing
import UIKit
@testable import TrainLog

struct FoodTests {
    private let sample = """
    {
      "date": "2026-10-27", "profile": {"goal": "maintain"}, "profile_ready": true, "weight": {"kg": 87.0},
      "entries": [
        {"id": 31, "date": "2026-10-27", "meal": "breakfast", "source": "text", "raw_text": "owsianka",
         "created_at": "2026-10-27 06:40:12",
         "items": [{"id": 1, "name": "Oats", "grams": 80, "kcal": 300, "protein_g": 10, "carbs_g": 50, "fat_g": 6, "confidence": "high", "portions": null},
                   {"id": 2, "name": "Whey", "grams": null, "kcal": 120, "protein_g": 24, "carbs_g": 3, "fat_g": 1, "confidence": null, "portions": null}],
         "totals": {"kcal": 420, "protein_g": 34, "carbs_g": 53, "fat_g": 7}},
        {"id": 32, "date": "2026-10-27", "meal": "lunch", "source": "photo", "raw_text": null, "created_at": "2026-10-27 12:10:00",
         "items": [{"id": 3, "name": "Chicken rice bowl", "grams": 450, "kcal": 812, "protein_g": 71, "carbs_g": 90, "fat_g": 15}],
         "totals": {"kcal": 812, "protein_g": 71, "carbs_g": 90, "fat_g": 15}}
      ],
      "totals": {"kcal": 1232, "protein_g": 105, "carbs_g": 143, "fat_g": 22},
      "target": {"resting": 1754, "daily_life": 614, "training": 407, "training_planned": false, "surplus": 0, "kcal": 2775, "day_kind": "rest", "carbs_g": 240},
      "protein_target_g": 130,
      "week": []
    }
    """

    @Test func decodesFoodDay() throws {
        let day = try APIClient.decoder.decode(FoodDay.self, from: Data(sample.utf8))
        #expect(day.entries.count == 2)
        #expect(day.entries[0].items[1].grams == nil)
        #expect(day.entries[1].items[0].proteinG == 71)
        #expect(day.target?.kcal == 2775)
        #expect(day.target?.carbsG == 240)
        #expect(day.proteinTargetG == 130)
    }

    @Test func decodesFinishedEstimateJob() throws {
        let json = """
        {"job_id": "abc", "status": "succeeded", "message": "Ready.",
         "estimate": {"items": [{"name": "Ryż", "grams": 200, "kcal": 260, "protein_g": 5, "carbs_g": 56, "fat_g": 1, "confidence": "low"}], "note": "Porcja na oko."}}
        """
        let job = try APIClient.decoder.decode(MealEstimateJob.self, from: Data(json.utf8))
        #expect(job.estimate?.items.first?.carbsG == 56)
        #expect(job.estimate?.note == "Porcja na oko.")
    }

    @Test func encodesEntryInSnakeCase() throws {
        let entry = FoodEntryInput(date: "2026-10-27", meal: "lunch", source: "photo", rawText: nil,
                                   items: [FoodItem(name: "Rice", grams: 200, kcal: 260, proteinG: 5)])
        let object = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(entry)) as? [String: Any]
        let item = (object?["items"] as? [[String: Any]])?.first
        #expect(item?["protein_g"] as? Double == 5)
        #expect(item?["id"] == nil)
        #expect(object?["meal"] as? String == "lunch")
    }

    @Test func formatsEntries() throws {
        let day = try APIClient.decoder.decode(FoodDay.self, from: Data(sample.utf8))
        #expect(FoodFormat.entryTitle(day.entries[0]) == "Oats +1")
        let warsaw = try #require(TimeZone(identifier: "Europe/Warsaw"))
        #expect(FoodFormat.entryMeta(day.entries[0], timeZone: warsaw) == "Breakfast · 07:40")
        #expect(FoodFormat.entryMeta(day.entries[1], timeZone: warsaw) == "Dinner · 13:10 · from photo")
        #expect(FoodFormat.kcal(1856.5) == "1,857")
        #expect(FoodFormat.dayKicker("2026-10-27", kind: "rest") == "Tuesday · rest day")
    }

    @Test func rescalesItemsByGrams() {
        let rice = FoodItem(name: "Rice", grams: 200, kcal: 260, proteinG: 5, carbsG: 56, fatG: 1)
        let bigger = FoodFormat.rescale(rice, grams: 300)
        #expect(bigger.kcal == 390)
        #expect(bigger.proteinG == 7.5)
        #expect(FoodFormat.rescale(FoodItem(name: "Soup", kcal: 200, proteinG: 8), grams: 400).kcal == 200)
    }

    @Test func picksMealByHour() {
        let calendar = Calendar.current
        let at = { (hour: Int) in calendar.date(bySettingHour: hour, minute: 0, second: 0, of: .now)! }
        #expect(FoodFormat.defaultMeal(at: at(7)) == "breakfast")
        #expect(FoodFormat.defaultMeal(at: at(13)) == "lunch")
        #expect(FoodFormat.defaultMeal(at: at(19)) == "dinner")
        #expect(FoodFormat.defaultMeal(at: at(22)) == "snack")
    }

    @Test func downscalesPhotos() throws {
        let big = UIGraphicsImageRenderer(size: CGSize(width: 4000, height: 3000)).image { context in
            UIColor.orange.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 4000, height: 3000))
        }
        let data = try #require(MealPhoto.jpeg(big))
        let image = try #require(UIImage(data: data))
        #expect(max(image.size.width, image.size.height) == 1280)
    }

    @MainActor
    @Test func estimateNeedsPhotoOrText() {
        let model = MealEstimateModel(photo: nil)
        #expect(!model.canEstimate)
        model.text = "  "
        #expect(!model.canEstimate)
        model.text = "2 eggs"
        #expect(model.canEstimate)
        model.items = [FoodItem(name: "Eggs", kcal: 140, proteinG: 12), FoodItem(name: " ", kcal: 0, proteinG: 0)]
        let entry = model.entry(date: "2026-10-27")
        #expect(entry.source == "text")
        #expect(entry.items.count == 1)
        #expect(entry.rawText == "2 eggs")
    }

    @Test func explainsHelperErrors() {
        #expect(MealEstimateModel.message(for: APIError.status(503)).contains("coach-helper-start"))
    }
}
