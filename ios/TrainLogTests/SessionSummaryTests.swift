import Foundation
import Testing
@testable import TrainLog

struct SessionSummaryTests {
    private let sample = """
    {
      "session_id": 44, "template_id": 4, "name": "Workout C · Wide Shoulders", "status": "completed",
      "date": "2026-10-30", "duration_minutes": 42, "volume_kg": 4172.0, "set_count": 20, "rep_count": 277,
      "previous": {"date": "2026-10-25", "volume_kg": 3896.0, "sets": 20},
      "best_count": 1, "going_up": 1, "holding": 1,
      "exercises": [
        {"exercise_name": "Standing Dumbbell Shoulder Press", "set_count": 3, "reps": 24, "volume_kg": 432.0,
         "top_set": {"weight_kg": 18.0, "reps": 8, "seconds": null}, "seconds": null,
         "last": {"date": "2026-10-25", "volume_kg": 432.0, "top_weight_kg": 18.0, "best_reps": 8},
         "bests": [], "first_time": false,
         "next": {"target_weight_kg": 18.0, "target_reps": 8, "held": "big_jump", "change": "hold",
                  "hint": "20 kg is a 11% jump. Stay at 18 kg until the sets feel easy."}},
        {"exercise_name": "Dumbbell Rear Delt Raise", "set_count": 4, "reps": 48, "volume_kg": 864.0,
         "top_set": {"weight_kg": 18.0, "reps": 12, "seconds": null}, "seconds": null,
         "last": {"date": "2026-10-28", "volume_kg": 840.0, "top_weight_kg": 18.0, "best_reps": 12},
         "bests": ["volume"], "first_time": false,
         "next": {"target_weight_kg": 20.0, "target_reps": 12, "held": null, "change": "up",
                  "hint": "Every set at 18 kg × 12 — try 20 kg next time."}},
        {"exercise_name": "Push-ups", "set_count": 3, "reps": 30, "volume_kg": 0.0,
         "top_set": {"weight_kg": null, "reps": 10, "seconds": null}, "seconds": null, "last": null,
         "bests": [], "first_time": true,
         "next": {"target_weight_kg": null, "target_reps": 11, "held": null, "change": "reps",
                  "hint": "Add a rep per set — aim for 11 on every set."}},
        {"exercise_name": "Plank", "set_count": 2, "reps": null, "volume_kg": 0.0,
         "top_set": {"weight_kg": null, "reps": 1, "seconds": 45}, "seconds": 90, "last": null,
         "bests": [], "first_time": false, "next": null}
      ]
    }
    """

    private func summary() throws -> StrengthSummary {
        try APIClient.decoder.decode(StrengthSummary.self, from: Data(sample.utf8))
    }

    @Test func decodesServerSummary() throws {
        let summary = try summary()
        #expect(summary.fromServer)
        #expect(summary.previous?.volumeKg == 3896)
        #expect(summary.exercises[1].bests == ["volume"])
        #expect(summary.exercises[3].next == nil)
        #expect(summary.exercises[3].topSet.seconds == 45)
    }

    @Test func comparesWithLastTime() throws {
        let summary = try summary()
        #expect(SummaryLogic.versusLast(summary) == 7)
        #expect(SummaryLogic.headline(summary) == "Workout done · a new best")
    }

    @Test func showsWhereEachTargetGoes() throws {
        let exercises = try summary().exercises
        #expect(SummaryLogic.change(exercises[0]) == .hold)
        #expect(SummaryLogic.change(exercises[1]) == .up("+2 kg"))
        #expect(SummaryLogic.change(exercises[2]) == .reps("+1 rep"))
        #expect(SummaryLogic.change(exercises[3]) == nil)
        #expect(SummaryLogic.todayLine(exercises[1]) == "18 kg × 12 · 4 sets")
        #expect(SummaryLogic.todayLine(exercises[3]) == "2 × 45 s")
        #expect(SummaryLogic.targetLine(exercises[1].next!) == "20 kg × 12")
        #expect(SummaryLogic.targetLine(exercises[2].next!) == "BW × 11")
    }

    @Test func namesTheBest() throws {
        let exercises = try summary().exercises
        #expect(SummaryLogic.best(exercises[1])?.title == "Most volume ever")
        #expect(SummaryLogic.best(exercises[0]) == nil)
    }

    @Test func explainsThePaceCalmly() throws {
        var summary = try summary()
        #expect(SummaryLogic.pace(summary) == "1 up, 1 holding. One or two jumps a session keeps progress steady.")
        summary.goingUp = 0
        #expect(SummaryLogic.pace(summary)?.hasPrefix("Every load holds") == true)
    }

    @Test func dayWideHoldLeadsThePace() throws {
        let busy = sample.replacingOccurrences(of: "\"held\": \"big_jump\"", with: "\"held\": \"life_load\"")
            .replacingOccurrences(of: "20 kg is a 11% jump. Stay at 18 kg until the sets feel easy.",
                                  with: "Travel Saturday: holding 18 kg on every lift. Match last time.")
        let summary = try APIClient.decoder.decode(StrengthSummary.self, from: Data(busy.utf8))
        #expect(SummaryLogic.pace(summary) == "Travel Saturday: no load jumps. Match today and keep the streak going.")
        #expect(SummaryLogic.rowHint(summary.exercises[0].next) == nil)
        #expect(SummaryLogic.rowHint(summary.exercises[1].next) != nil)
        #expect(SummaryLogic.grouped(4172) == "4,172")
    }

    @Test func buildsLocalRecapFromSession() throws {
        let json = """
        {"id": 41, "template_id": 3, "template_name": "Workout B", "status": "completed",
         "started_at": "2026-10-27T19:00:00+01:00", "completed_at": null,
         "current_exercise_order": 1, "current_set_order": 1,
         "exercises": [
           {"id": 7, "exercise_order": 1, "exercise_name": "Dumbbell Row", "notes": null, "sets": [
             {"id": 69, "set_order": 0, "target_reps": 10, "target_weight_kg": 20, "rest_seconds": 60,
              "actual_reps": 10, "actual_weight_kg": 20, "status": "completed", "set_type": "warmup"},
             {"id": 70, "set_order": 1, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90,
              "actual_reps": 10, "actual_weight_kg": 36, "status": "completed", "set_type": "working"},
             {"id": 71, "set_order": 2, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90,
              "actual_reps": 8, "actual_weight_kg": 36, "status": "completed", "set_type": "working"}]},
           {"id": 8, "exercise_order": 2, "exercise_name": "Pull-ups", "notes": null, "sets": [
             {"id": 80, "set_order": 1, "target_reps": 6, "target_weight_kg": null, "rest_seconds": 120,
              "actual_reps": null, "actual_weight_kg": null, "status": "pending", "set_type": "working"}]}
         ]}
        """
        let session = try APIClient.decoder.decode(StrengthSession.self, from: Data(json.utf8))
        let start = try #require(StrengthFormat.parseMoment(session.startedAt))
        let summary = SummaryLogic.local(session, now: start.addingTimeInterval(48 * 60))
        #expect(!summary.fromServer)
        #expect(summary.durationMinutes == 48)
        #expect(summary.volumeKg == 648)
        #expect(summary.setCount == 2)
        #expect(summary.repCount == 18)
        #expect(summary.exercises.map(\.exerciseName) == ["Dumbbell Row"])
        #expect(summary.exercises[0].topSet.reps == 10)
        #expect(SummaryLogic.pace(summary) == nil)
    }
}
