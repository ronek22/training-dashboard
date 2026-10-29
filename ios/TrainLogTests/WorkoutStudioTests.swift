import Foundation
import Testing
@testable import TrainLog

struct WorkoutStudioTests {
    private let sample = """
    [
      {"id": 4, "name": "Workout C · Upper", "exercise_count": 4, "set_count": 12, "estimated_duration_minutes": 36,
       "last_done_at": "2026-10-27T18:02:11+01:00",
       "exercises": [{"exercise_name": "Bench Press"}, {"exercise_name": "Chin Up"}]},
      {"id": 5, "name": "Workout D · Lower + Core", "exercise_count": 1, "set_count": 3, "estimated_duration_minutes": 9,
       "last_done_at": "2026-10-15T07:40:00+02:00", "exercises": [{"exercise_name": "Back Squat"}]},
      {"id": 6, "name": "New Pull", "exercise_count": 0, "set_count": 0, "estimated_duration_minutes": 0,
       "last_done_at": null, "exercises": []},
      {"id": 7, "name": "Old server row"}
    ]
    """

    private func decode() throws -> [StrengthTemplateSummary] {
        try APIClient.decoder.decode([StrengthTemplateSummary].self, from: Data(sample.utf8))
    }

    @Test func decodesTheListRow() throws {
        let rows = try decode()
        #expect(rows[0].exerciseCount == 4)
        #expect(rows[0].lastDoneAt == "2026-10-27T18:02:11+01:00")
        #expect(rows[0].exercises?.map(\.exerciseName) == ["Bench Press", "Chin Up"])
        #expect(rows[3].lastDoneAt == nil && rows[3].exercises == nil)
    }

    @Test func longestWaitingComesFirstAndNeverDoneLast() throws {
        #expect(StudioFormat.ordered(try decode(), planned: nil).map(\.id) == [5, 4, 6, 7])
    }

    @Test func todaysPlannedWorkoutLeads() throws {
        #expect(StudioFormat.ordered(try decode(), planned: 4).map(\.id) == [4, 5, 6, 7])
    }

    @Test func metaAndLifts() throws {
        let rows = try decode()
        #expect(StudioFormat.meta(rows[0]) == "4 lifts · 12 sets · ~36 min")
        #expect(StudioFormat.meta(rows[1]) == "1 lift · 3 sets · ~9 min")
        #expect(StudioFormat.meta(rows[3]) == "")
        #expect(StudioFormat.lifts(rows[0]) == "Bench Press, Chin Up")
        #expect(StudioFormat.lifts(rows[2]) == nil)
    }

    @Test func lastDoneReadsInDays() {
        let today = "2026-10-29"
        #expect(StudioFormat.lastDone("2026-10-29T07:00:00+01:00", today: today) == "Today")
        #expect(StudioFormat.lastDone("2026-10-28T19:00:00+01:00", today: today) == "Yesterday")
        #expect(StudioFormat.lastDone("2026-10-24T19:00:00+02:00", today: today) == "5 days ago")
        #expect(StudioFormat.lastDone("2026-10-08T19:00:00+02:00", today: today) == "3 weeks ago")
        #expect(StudioFormat.lastDone(nil, today: today) == "Not done yet")
    }
}
