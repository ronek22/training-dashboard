import Foundation
import Testing
@testable import TrainLog

struct TodayTests {
    private let sample = """
    {
      "date": "2026-10-28", "generated_at": "2026-10-28T07:12:00+01:00", "streak_days": 299,
      "readiness": {"level": "green", "label": "Green", "advice": "Lift as planned.", "drivers": [], "suggests_swap": false},
      "vitals": {"resting_hr": 58.0, "sleep_h": 7.4, "pain": 1},
      "checkin_done": true, "sick": null,
      "today": {"title": "Workout B · Back + Arms", "session_type": "strength", "intent_label": "Upper-body strength",
                "duration_min": 45, "distance_km": null, "details": "Pull day.", "purpose": null, "rpe": null,
                "status": "not_completed_yet", "sport": "strength", "fallback": "Short version.",
                "strength": {"template_id": 3, "last_done": "2026-10-22",
                             "exercises": [{"name": "Pull-ups", "sets": 3, "reps": 6, "weight_kg": null},
                                           {"name": "DB Row", "sets": 3, "reps": 10, "weight_kg": 34.0}]}},
      "tomorrow": null,
      "week": [{"date": "2026-10-26", "label": "Mon", "title": "Workout A", "sport": "strength", "status": "done", "done_sports": ["strength"]},
               {"date": "2026-10-27", "label": "Tue", "title": "Rehab", "sport": "mobility", "status": "done", "done_sports": ["mobility", "ride"]},
               {"date": "2026-10-28", "label": "Wed", "title": "Workout B", "sport": "strength", "status": "today", "done_sports": []},
               {"date": "2026-11-01", "label": "Sun", "title": null, "sport": "paddle", "status": "upcoming", "done_sports": []}],
      "week_minutes": {"done": 167, "planned": 370, "by_sport": [{"sport": "strength", "minutes": 99}]}
    }
    """

    @Test func decodesPhoneToday() throws {
        let today = try APIClient.decoder.decode(PhoneToday.self, from: Data(sample.utf8))
        #expect(today.streakDays == 299)
        #expect(today.vitals.sleepH == 7.4)
        #expect(today.today?.sport == .strength)
        #expect(today.today?.strength?.exercises.count == 2)
        #expect(today.today?.isDone == false)
        #expect(today.week[1].doneSports == [.mobility, .ride])
        #expect(today.week[3].sport == .other)
        #expect(today.weekMinutes.planned == 370)
    }

    @Test func bodyweightDayStartsAsAOneTimeSession() throws {
        let json = """
        {"template_id": null, "name": "Bodyweight upper", "last_done": null,
         "exercises": [{"name": "Push Up", "sets": 4, "reps": 12, "weight_kg": null, "rest_seconds": 90, "notes": "Hands on a table"}]}
        """
        let strength = try APIClient.decoder.decode(PhoneToday.Strength.self, from: Data(json.utf8))
        let workout = try #require(strength.oneTime)
        #expect(workout.name == "Bodyweight upper")
        #expect(workout.exercises == [.init(exerciseName: "Push Up", setCount: 4, targetReps: 12, targetWeightKg: nil, restSeconds: 90, notes: "Hands on a table")])

        let saved = try APIClient.decoder.decode(PhoneToday.Strength.self, from: Data(#"{"template_id": 2, "exercises": [{"name": "Squat", "sets": 3}]}"#.utf8))
        #expect(saved.oneTime == nil)
    }

    @Test func savedWorkoutsKeepHolds() throws {
        let json = """
        {"id": 7, "name": "Core", "exercises": [
          {"exercise_name": "Plank", "set_count": 3, "target_reps": 1, "target_seconds": 45, "rest_seconds": 45},
          {"exercise_name": "Dead Bug", "set_count": 3, "target_reps": 10, "rest_seconds": 45}]}
        """
        let draft = WorkoutDraft(try APIClient.decoder.decode(TemplateDetail.self, from: Data(json.utf8)))
        #expect(draft.exercises.map(\.seconds) == [45, nil])
        #expect(draft.exercises.map(\.dose) == ["3 × 45 s", "3 × 10"])
        let saved = draft.input.exercises
        #expect((saved[0].targetReps, saved[0].targetSeconds) == (1, 45))
        #expect((saved[1].targetReps, saved[1].targetSeconds) == (10, nil))
    }

    @Test func holdsStartAsTimedSets() throws {
        let json = """
        {"template_id": null, "name": "Bodyweight core",
         "exercises": [{"name": "Plank", "sets": 3, "reps": null, "seconds": 40, "rest_seconds": 45}]}
        """
        let strength = try APIClient.decoder.decode(PhoneToday.Strength.self, from: Data(json.utf8))
        let plank = try #require(strength.oneTime?.exercises.first)
        #expect((plank.targetReps, plank.targetSeconds, plank.restSeconds) == (1, 40, 45))
        #expect(TodayFormat.exerciseTarget(strength.exercises[0]) == "3 × 40 s")
        #expect(StrengthFormat.hold(90) == "1:30")
        #expect(StrengthFormat.load(weight: 10, reps: 1, seconds: 40) == "10 kg · 40 s")
    }

    @Test func formatsDurations() {
        #expect(TodayFormat.duration(167) == "2h 47m")
        #expect(TodayFormat.duration(45) == "45m")
        #expect(TodayFormat.duration(120) == "2h")
    }

    @Test func formatsExerciseTargets() {
        #expect(TodayFormat.exerciseTarget(.init(name: "Pull-ups", sets: 3, reps: 6, weightKg: nil)) == "3 × 6 · BW")
        #expect(TodayFormat.exerciseTarget(.init(name: "Raise", sets: 3, reps: 15, weightKg: 22.5)) == "3 × 15 · 22.5 kg")
    }

    @Test func formatsDates() {
        #expect(TodayFormat.dateKicker("2026-10-28") == "Wednesday · 28 October")
        #expect(TodayFormat.shortDay("2026-10-22", relativeTo: "2026-10-28") == "Thu 22")
        #expect(TodayFormat.shortDay("2026-09-17", relativeTo: "2026-10-28") == "Thu 17 Sep")
    }
}
