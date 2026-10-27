import Foundation
import Testing
@testable import TrainLog

struct PlanTests {
    private let sample = """
    [{
      "week_start": "2026-10-26",
      "title": "Knee calm-down week: upper-body lifts, easy knee-gated spins, rehab",
      "focus": "Settle the left outer knee.",
      "overview": "Long text the phone ignores.",
      "revisions": [],
      "days": [
        {"session_id": "a", "date": "2026-10-26", "label": "Mon", "session_type": "strength", "workout_intent": "strength_upper",
         "workout_intent_label": "Upper-body strength", "template_id": "strength-a", "template_label": "Workout A · Upper Chest",
         "title": "Workout A · Upper Chest", "details": "Push.", "check": null, "steps": ["Bench"], "cues": [], "fallback": null,
         "target_duration_min": 45, "target_distance_km": null, "cycling_workout_name": null,
         "comparison": {"status": "matched", "label": "Matched",
                        "completed_activities": [{"id": "1", "date": "2026-10-26", "type": "WeightTraining", "duration_min": 98.9}]},
         "rehab": [], "fuel_plan": null},
        {"session_id": "b", "date": "2026-10-27", "label": "Tue", "session_type": "recovery", "workout_intent": "recovery",
         "workout_intent_label": "Recovery", "title": "Rehab: knee", "target_duration_min": 25,
         "comparison": {"status": "matched", "completed_activities": [{"id": "2", "duration_min": 25.0}]},
         "rehab": [{"issue_id": 2, "routine_id": 7, "title": "Left knee", "ticked": [0],
                    "exercises": [{"name": "Quad isometric", "dose": "5 x 30 sec", "how": "Press down."},
                                  {"name": "Glute bridge", "dose": "3 x 12", "how": null}]}]},
        {"session_id": "c", "date": "2026-10-29", "label": "Thu", "session_type": "ride", "workout_intent": "recovery",
         "workout_intent_label": "Recovery", "title": "Recovery spin (knee-gated) + rehab", "target_duration_min": 40,
         "cycling_workout_name": "Recovery spin", "comparison": {"status": "not_completed_yet"}},
        {"session_id": "d", "date": "2026-10-31", "label": "Sat", "session_type": "ride", "workout_intent": "easy",
         "workout_intent_label": "Easy", "title": "Easy endurance ride", "target_duration_min": 60, "target_distance_km": 28.0,
         "comparison": {"status": "not_completed_yet"}}
      ]
    }]
    """

    private func week() throws -> WeeklyPlan {
        try #require(try APIClient.decoder.decode([WeeklyPlan].self, from: Data(sample.utf8)).first)
    }

    private func day(_ date: String) throws -> PlanDay {
        try #require(try week().days.first { $0.date == date })
    }

    @Test func decodesWeeklyPlan() throws {
        let week = try week()
        #expect(week.days.count == 4)
        #expect(week.days[1].rehab?.first?.exercises.count == 2)
        #expect(week.days[1].rehab?.first?.ticked == [0])
        #expect(week.days[0].comparison?.completedActivities?.first?.durationMin == 98.9)
    }

    @Test func sportFollowsServerColours() throws {
        #expect(PlanFormat.sport(try day("2026-10-26")) == .strength)
        #expect(PlanFormat.sport(try day("2026-10-27")) == .mobility)
        // A recovery-intent ride is still a ride.
        #expect(PlanFormat.sport(try day("2026-10-29")) == .ride)
    }

    @Test func fillsTheWeekWithFreeDays() throws {
        let slots = PlanFormat.slots(try week())
        #expect(slots.map(\.date) == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"])
        #expect(slots[2].day == nil)
        #expect(PlanFormat.status(slots[2].day, today: "2026-10-27") == .rest)
    }

    @Test func statusAndMeta() throws {
        let today = "2026-10-27"
        #expect(PlanFormat.status(try day("2026-10-26"), today: today) == .done)
        #expect(PlanFormat.meta(try day("2026-10-26"), today: today) == "Done · 1h 39")
        #expect(PlanFormat.meta(try day("2026-10-27"), today: today) == "Today · done · 25m")
        #expect(PlanFormat.meta(try day("2026-10-31"), today: today) == "Easy · 60 min · 28 km")
        #expect(PlanFormat.status(try day("2026-10-29"), today: "2026-10-30") == .missed)
    }

    @Test func summaryCountsDoneSessionsAndMinutes() throws {
        let summary = PlanFormat.summary(try week(), today: "2026-10-27")
        #expect(summary.done == 2)
        #expect(summary.sessions == 4)
        #expect(summary.doneMinutes == 124)
        #expect(summary.plannedMinutes == 170)
        #expect(summary.bySport.first?.sport == .strength)
    }

    @Test func titles() {
        #expect(PlanFormat.shortTitle("Knee calm-down week: upper-body lifts") == "Knee calm-down week")
        #expect(PlanFormat.rowTitle("Recovery spin (knee-gated) + rehab") == "Recovery spin + rehab")
        #expect(PlanFormat.weekKicker("2026-10-26") == "Week 44 · Oct 26 – Nov 1")
        #expect(PlanFormat.fallback("Short on time: bench and pull-ups only.") == "Bench and pull-ups only.")
        #expect(PlanFormat.fallback("If pain is 3/10, walk.") == "If pain is 3/10, walk.")
        #expect(PlanFormat.fallback("") == nil)
    }

    @Test func moveRules() throws {
        let today = "2026-10-27"
        let slots = PlanFormat.slots(try week())
        #expect(!PlanFormat.canMove(try day("2026-10-26"), today: today))
        #expect(!PlanFormat.canMove(try day("2026-10-27"), today: today))
        #expect(PlanFormat.canMove(try day("2026-10-29"), today: today))
        #expect(!PlanFormat.canReceive(slots[0], today: today))
        #expect(PlanFormat.canReceive(slots[2], today: today))

        let swap = PlanFormat.moveDescription(try day("2026-10-29"), to: slots[5])
        #expect(swap.button == "Swap Thu ↔ Sat")
        #expect(swap.sentence == "The two days swap: Easy endurance ride moves to Thu 29, Recovery spin + rehab to Sat 31.")
        #expect(PlanFormat.moveDescription(try day("2026-10-29"), to: slots[2]).button == "Move to Wed")
    }

    @Test func picksTheWeekContainingToday() {
        let starts = ["2026-10-05", "2026-10-12", "2026-10-26", "2026-11-02"]
        #expect(PlanFormat.currentWeek(starts, today: "2026-10-28") == "2026-10-26")
        #expect(PlanFormat.currentWeek(starts, today: "2026-10-21") == "2026-10-12")
        #expect(PlanFormat.weekStart(of: "2026-11-01") == "2026-10-26")
    }

    @Test func encodesSwapInSnakeCase() throws {
        let data = try APIClient.encoder.encode(PlanSwap(fromDate: "2026-10-29", toDate: "2026-10-31"))
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: String])
        #expect(json == ["from_date": "2026-10-29", "to_date": "2026-10-31"])
    }
}
