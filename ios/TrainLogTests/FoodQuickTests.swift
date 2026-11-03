import Foundation
import Testing
@testable import TrainLog

struct FoodQuickTests {
    // Trimmed from GET /phone/food/quick on 3 Nov.
    private let sample = """
    {"date": "2026-11-08", "slot": "dinner",
     "again": [{"key": "yesterday-55", "kind": "yesterday", "meal": "dinner", "date": "2026-11-07", "count": 1,
                "title": "Chleb, szynka wieprzowa", "totals": {"kcal": 268, "protein_g": 14, "carbs_g": 40, "fat_g": 4},
                "items": [{"id": 9, "name": "chleb", "grams": 80, "kcal": 218, "protein_g": 6, "carbs_g": 40, "fat_g": 2, "confidence": null, "portions": null},
                          {"id": 10, "name": "szynka wieprzowa", "grams": 40, "kcal": 50, "protein_g": 8, "carbs_g": 0.5, "fat_g": 2}]}],
     "gap": {"focus": "protein", "meal": "dinner", "left": {"kcal": -590, "protein_g": 33}, "planned_dinner": null,
             "picks": [{"key": "item-120", "title": "Tuńczyk w sosie własnym", "source": "log", "last_date": "2026-10-14", "count": 1,
                        "portions": 2, "totals": {"kcal": 160, "protein_g": 36, "carbs_g": 0, "fat_g": 1.6},
                        "items": [{"name": "tuńczyk w sosie własnym", "grams": 240, "kcal": 160, "protein_g": 36, "carbs_g": 0, "fat_g": 1.6}]}]},
     "fuel": {"intent": "tempo", "duration_min": 70, "carbs_g_per_h": {"low": 60, "high": 90, "target": 60}, "total_carbs_g": 70,
              "bottles": 1, "hot_bottles": 1, "bottle_ml": 600, "summary": "", "tip": "", "title": "Sweet spot 3 × 10 min (knee-gated)",
              "blocks": [[12, 22], [27, 37], [42, 52]], "stops": [{"min": 15, "carbs_g": 25}, {"min": 35, "carbs_g": 25}]}}
    """

    @Test func decodesQuick() throws {
        let quick = try APIClient.decoder.decode(FoodQuick.self, from: Data(sample.utf8))
        #expect(quick.again.first?.items.count == 2)
        #expect(quick.gap?.left.proteinG == 33)
        #expect(quick.gap?.picks.first?.lastDate == "2026-10-14")
        #expect(quick.fuel?.carbsGPerH.target == 60)
        #expect(quick.fuel?.blocks.count == 3)
        #expect(quick.fuel?.stops.last?.carbsG == 25)
    }

    @Test func decodesQuietDay() throws {
        let quick = try APIClient.decoder.decode(FoodQuick.self, from: Data(#"{"date": "2026-11-03", "slot": "lunch", "again": [], "gap": null, "fuel": null}"#.utf8))
        #expect(quick.again.isEmpty && quick.gap == nil && quick.fuel == nil)
    }

    private func pick(_ title: String, portions: Double, grams: Double?, items: Int = 1) -> FoodQuick.Pick {
        let item = FoodItem(name: title, grams: grams, kcal: 100, proteinG: 10)
        return FoodQuick.Pick(key: "k", title: title, source: "log", lastDate: nil, count: 1, portions: portions,
                              items: Array(repeating: item, count: items), totals: .zero)
    }

    @Test func pickTitleShowsThePortion() {
        #expect(FoodFormat.pickTitle(pick("Skyr", portions: 1, grams: 150)) == "Skyr")
        #expect(FoodFormat.pickTitle(pick("Szynka", portions: 4, grams: 160)) == "Szynka · 160 g")
        #expect(FoodFormat.pickTitle(pick("Kurczak z ryżem", portions: 0.5, grams: nil)) == "Kurczak z ryżem · ½ portion")
        #expect(FoodFormat.pickTitle(pick("Obiad", portions: 1.5, grams: 200, items: 2)) == "Obiad · 1½ portions")
        #expect(FoodFormat.pickTitle(pick("Obiad", portions: 2, grams: nil, items: 2)) == "Obiad · 2 portions")
    }

    @Test func pickNoteSaysWhenOrCarbs() throws {
        let now = try #require(FoodFormat.parse("2026-11-03"))
        var recent = pick("Pierś", portions: 1, grams: 150)
        recent = FoodQuick.Pick(key: "k", title: "Pierś", source: "log", lastDate: "2026-10-31", count: 1, portions: 1,
                                items: recent.items, totals: Macros(kcal: 460, proteinG: 42, carbsG: 18, fatG: 24))
        #expect(FoodFormat.pickNote(recent, focus: "both", today: now) == "Sat")
        #expect(FoodFormat.pickNote(recent, focus: "refuel", today: now) == "18 g carbs")
        let old = FoodQuick.Pick(key: "k", title: "Kurczak", source: "log", lastDate: "2026-10-14", count: 4, portions: 1,
                                 items: [], totals: .zero)
        #expect(FoodFormat.pickNote(old, focus: "both", today: now) == "14 Oct")
    }

    @Test func ghostSitsAfterEatenAndDinner() throws {
        let plain = try #require(FoodFormat.ghostRange(eaten: 1000, planned: nil, ghost: 500, target: 2000))
        #expect(plain.lowerBound == 0.5 && plain.upperBound == 0.75)
        let withDinner = try #require(FoodFormat.ghostRange(eaten: 1000, planned: 400, ghost: 1000, target: 2000))
        #expect(abs(withDinner.lowerBound - 0.73) < 0.0001)
        #expect(withDinner.upperBound == 1)
        #expect(FoodFormat.ghostRange(eaten: 2100, planned: nil, ghost: 300, target: 2000) == nil)
        #expect(FoodFormat.ghostRange(eaten: 100, planned: nil, ghost: 0, target: 2000) == nil)
    }

    @Test func labels() {
        let card = FoodQuick.Again(key: "k", kind: "yesterday", meal: "lunch", date: nil, count: 1, title: "", items: [], totals: .zero)
        #expect(FoodFormat.againSource(card) == "Yesterday · dinner")
        let favourite = FoodQuick.Again(key: "k", kind: "favourite", meal: "lunch", date: nil, count: 4, title: "", items: [], totals: .zero)
        #expect(FoodFormat.againSource(favourite) == "4× in 30 days")
        #expect(FoodFormat.fuelTitle("Sweet spot 3 × 10 min (knee-gated)") == "Sweet spot 3 × 10 min")
        #expect(FoodFormat.gapKicker("protein") == "Close the gap · protein")
    }

    @MainActor
    @Test func demoStagesNeverNeedTheServer() {
        let evening = FoodModel.demo("evening")
        #expect(evening.pick?.title == "Pierś z kurczaka w cieście")
        evening.selectedPick = "entry-38"
        #expect(evening.pick?.portions == 0.5)
        #expect(FoodModel.demo("tapped").relogged?.entryId == 1)
        #expect(FoodModel.demo("ride").quick?.fuel?.durationMin == 70)
    }
}
