import Foundation
import Testing
@testable import TrainLog

struct StrengthSessionTests {
    private let sample = """
    {
      "id": 41, "template_id": 3, "template_name": "Workout B · Back + Core", "notes": null,
      "status": "active", "started_at": "2026-10-27T19:15:52+01:00", "completed_at": null,
      "current_exercise_order": 1, "current_set_order": 2, "linked_activity": null,
      "progress": {"completed_sets": 1, "total_sets": 5, "fraction": 0.2},
      "exercises": [
        {"id": 7, "exercise_order": 1, "exercise_name": "Dumbbell Row", "notes": null,
         "completed_set_count": 1, "warmup_set_count": 0, "completed_warmup_set_count": 0,
         "sets": [
           {"id": 70, "session_exercise_id": 7, "set_order": 1, "target_reps": 10, "target_weight_kg": 34.0,
            "rest_seconds": 90, "actual_reps": 10, "actual_weight_kg": 36.0, "status": "completed",
            "completed_at": "2026-10-27T19:20:00+01:00", "rest_ends_at": null, "set_type": "working", "effort": "solid"},
           {"id": 71, "session_exercise_id": 7, "set_order": 2, "target_reps": 10, "target_weight_kg": 34.0,
            "rest_seconds": 90, "actual_reps": null, "actual_weight_kg": null, "status": "pending",
            "completed_at": null, "rest_ends_at": null, "set_type": "working", "effort": null},
           {"id": 72, "session_exercise_id": 7, "set_order": 3, "target_reps": 10, "target_weight_kg": 34.0,
            "rest_seconds": 90, "actual_reps": null, "actual_weight_kg": null, "status": "pending",
            "completed_at": null, "rest_ends_at": null, "set_type": "working", "effort": null}
         ]},
        {"id": 8, "exercise_order": 2, "exercise_name": "Pull-ups", "notes": "Slow negatives",
         "completed_set_count": 0, "warmup_set_count": 0, "completed_warmup_set_count": 0,
         "sets": [
           {"id": 80, "session_exercise_id": 8, "set_order": 1, "target_reps": 6, "target_weight_kg": null,
            "rest_seconds": 120, "actual_reps": null, "actual_weight_kg": null, "status": "pending",
            "completed_at": null, "rest_ends_at": null, "set_type": "working", "effort": null},
           {"id": 81, "session_exercise_id": 8, "set_order": 2, "target_reps": 6, "target_weight_kg": null,
            "rest_seconds": 120, "actual_reps": null, "actual_weight_kg": null, "status": "pending",
            "completed_at": null, "rest_ends_at": null, "set_type": "working", "effort": null}
         ]}
      ]
    }
    """

    private func session() throws -> StrengthSession {
        try APIClient.decoder.decode(StrengthSession.self, from: Data(sample.utf8))
    }

    @Test func decodesSession() throws {
        let session = try session()
        #expect(session.isActive)
        #expect(session.exercises.count == 2)
        #expect(session.exercises[1].sets[0].targetWeightKg == nil)
        #expect(SetEffort(backend: session.exercises[0].sets[0].effort) == .solid)
        #expect(StrengthFormat.parseMoment(session.startedAt) != nil)
    }

    @Test func roundTripsThroughLocalStore() throws {
        let original = try session()
        let data = try APIClient.encoder.encode(original)
        #expect(try APIClient.decoder.decode(StrengthSession.self, from: data) == original)
    }

    @Test func currentSetFollowsPosition() throws {
        let current = try #require(StrengthLogic.current(in: try session()))
        #expect(current.set.id == 71)
        #expect(StrengthLogic.label(for: current.set, in: current.exercise) == "Set 2")
    }

    @Test func completingStaysOnExerciseThenMovesOn() throws {
        var session = try session()
        session = StrengthLogic.complete(session, setId: 71, reps: 9, weightKg: 36, effort: .grinding)
        #expect(session.currentExerciseOrder == 1)
        #expect(session.currentSetOrder == 3)
        #expect(session.exercises[0].sets[1].actualReps == 9)
        #expect(session.exercises[0].sets[1].effort == "grinding")

        session = StrengthLogic.complete(session, setId: 72, reps: 10, weightKg: 36, effort: nil)
        #expect(session.exercises[0].isDone)
        #expect(session.currentExerciseOrder == 2)
        #expect(session.currentSetOrder == 1)
        #expect(StrengthLogic.progress(of: session.exercises[0]) == 1)
    }

    @Test func carriesChangedWeightToNextSet() throws {
        let session = try session()
        let exercise = session.exercises[0]
        #expect(StrengthLogic.carriedWeight(for: exercise.sets[1], in: exercise) == 36)
        #expect(StrengthLogic.carriedWeight(for: exercise.sets[0], in: exercise) == 34)
        let pullUps = session.exercises[1]
        #expect(StrengthLogic.carriedWeight(for: pullUps.sets[0], in: pullUps) == nil)
    }

    @Test func stepsWeightInHalfKilos() {
        #expect(StrengthLogic.step(34, by: 1) == 34.5)
        #expect(StrengthLogic.step(33.6, by: 1) == 34)
        #expect(StrengthLogic.step(0.5, by: -1) == nil)
        #expect(StrengthLogic.step(nil, by: 1) == 0.5)
        #expect(StrengthLogic.step(nil, by: -1) == nil)
    }

    @Test func formatsLoadsAndClocks() {
        #expect(StrengthFormat.load(weight: 34, reps: 10) == "34 kg × 10")
        #expect(StrengthFormat.load(weight: 22.5, reps: 15) == "22.5 kg × 15")
        #expect(StrengthFormat.load(weight: nil, reps: 6) == "BW × 6")
        #expect(StrengthFormat.clock(90) == "1:30")
        #expect(StrengthFormat.clock(1122) == "18:42")
        #expect(StrengthFormat.clock(3725) == "1:02:05")
    }

    @Test func queuePersistsUntilFlushed() async throws {
        let file = FileManager.default.temporaryDirectory.appending(path: "queue-\(UUID().uuidString).json")
        let queue = WriteQueue(file: file)
        queue.append(.init(method: "POST", path: "/a", body: Data("{}".utf8)))
        queue.append(.init(method: "PUT", path: "/b", body: nil))
        #expect(queue.pending.map(\.path) == ["/a", "/b"])

        // Nothing listens on port 9: the flush stops and keeps both writes.
        let unreachable = APIClient(baseURL: "http://127.0.0.1:9")
        #expect(await queue.flush(with: unreachable) == false)
        #expect(queue.pending.count == 2)
        try? FileManager.default.removeItem(at: file)
    }

    @Test func liveActivityShowsTheSetUpNextAndTheRest() throws {
        let now = Date(timeIntervalSince1970: 1_000_000)
        let state = try #require(StrengthActivity.state(
            for: try session(), restEndsAt: now.addingTimeInterval(72), restSeconds: 90, now: now
        ))
        #expect(state.exercise == "Dumbbell Row")
        #expect(state.setLabel == "Set 2")
        // The weight changed on set 1 carries on.
        #expect(state.load == "36 kg × 10")
        #expect(state.exerciseNumber == 1 && state.exerciseCount == 2)
        #expect(state.setsDone == 1 && state.setsTotal == 5)
        #expect(state.restRange == now.addingTimeInterval(-18)...now.addingTimeInterval(72))
        #expect(!state.allSetsDone)
    }

    @Test func liveActivityUsesTheShortWorkoutName() {
        #expect(StrengthActivity.shortName("Workout B · Back + Core") == "Workout B")
        #expect(StrengthActivity.shortName("Legs") == "Legs")
    }

    @Test func liveActivityDropsARestThatIsOver() throws {
        let now = Date(timeIntervalSince1970: 1_000_000)
        let state = try #require(StrengthActivity.state(
            for: try session(), restEndsAt: now.addingTimeInterval(-1), restSeconds: 90, now: now
        ))
        #expect(state.restEnd == nil)
        #expect(state.restRange == nil)
    }
}
