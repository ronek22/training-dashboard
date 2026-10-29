import Foundation
import Testing
@testable import TrainLog

struct SessionBriefTests {
    private let sample = """
    {
      "id": 5, "name": "Workout D · Lower + Core", "notes": null, "exercise_count": 4, "set_count": 12,
      "estimated_duration_minutes": 34,
      "exercises": [
        {"id": 21, "exercise_order": 1, "exercise_name": "Back Squat", "set_count": 3, "target_reps": 6,
         "target_weight_kg": 75.0, "rest_seconds": 120, "notes": null,
         "next": {"target_weight_kg": 80.0, "target_reps": 6, "hint": "Every set at 77.5 kg × 6 — try 80 kg next time.",
                  "based_on_date": "2026-10-15",
                  "last": {"date": "2026-10-15", "weight_kg": 77.5, "reps": 6, "set_count": 3}}},
        {"id": 23, "exercise_order": 2, "exercise_name": "Dumbbell Bulgarian Split Squat", "set_count": 3, "target_reps": 8,
         "target_weight_kg": 14.0, "rest_seconds": 120, "notes": null,
         "next": {"target_weight_kg": 16.0, "target_reps": 8, "hint": "Deadline today: holding 16 kg on every lift. Match last time.",
                  "based_on_date": "2026-10-15", "held": "life_load",
                  "last": {"date": "2026-10-15", "weight_kg": 16.0, "reps": 8, "set_count": 3}}},
        {"id": 25, "exercise_order": 3, "exercise_name": "Hanging Leg Raise", "set_count": 3, "target_reps": 12,
         "target_weight_kg": null, "rest_seconds": 90, "notes": null,
         "next": {"target_weight_kg": null, "target_reps": 13, "hint": "Add a rep per set — aim for 13 on every set.",
                  "based_on_date": "2026-09-22",
                  "last": {"date": "2026-09-22", "weight_kg": null, "reps": 12, "set_count": 3}}},
        {"id": 27, "exercise_order": 4, "exercise_name": "Nordic Curl", "set_count": 3, "target_reps": 5,
         "target_weight_kg": null, "rest_seconds": 90, "notes": "Slow lowering", "next": null}
      ]
    }
    """

    private func template() throws -> StrengthTemplate {
        try APIClient.decoder.decode(StrengthTemplate.self, from: Data(sample.utf8))
    }

    @Test func decodesTargetsAndLastTime() throws {
        let template = try template()
        #expect(template.estimatedDurationMinutes == 34)
        #expect(template.exercises[0].next?.last?.weightKg == 77.5)
        #expect(template.exercises[1].next?.held == "life_load")
        #expect(template.exercises[3].next == nil)
    }

    @Test func comparesEachLiftWithLastTime() throws {
        let lifts = BriefLogic.lifts(try template())
        #expect(lifts.map(\.change) == [.up("+2.5 kg"), .hold, .up("+1 rep"), .new])
        #expect(lifts[0].target == "3 × 6 · 80 kg")
        #expect(lifts[2].target == "3 × 13 · BW")
        #expect(lifts[3].target == "3 × 5 · BW")
        #expect(BriefLogic.summary(lifts) == "2 going up · 1 holding · 1 new")
    }

    @Test func dayWideHoldBecomesTheDayNote() throws {
        #expect(BriefLogic.dayNote(try template()) == "Deadline today")
    }

    @Test func liftHoldsAreNotADayNote() {
        let next = StrengthTemplate.Next(targetWeightKg: 18, targetReps: 8, hint: "20 kg is a 11% jump. Stay at 18 kg.",
                                         basedOnDate: nil, held: "big_jump",
                                         last: .init(date: "2026-10-25", weightKg: 18, reps: 8))
        let template = StrengthTemplate(id: 1, name: "C", exercises: [.init(exerciseName: "Press", next: next)])
        #expect(BriefLogic.dayNote(template) == nil)
        #expect(BriefLogic.change(next) == .hold)
    }

    @Test func lighterTargetIsADrop() {
        let next = StrengthTemplate.Next(targetWeightKg: 20, targetReps: 8, hint: nil, basedOnDate: nil, held: "effort",
                                         last: .init(date: "2026-10-25", weightKg: 22.5, reps: 8))
        #expect(BriefLogic.change(next) == .down("−2.5 kg"))
    }
}
