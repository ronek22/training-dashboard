import Foundation
import Testing
@testable import TrainLog

struct ActivitiesTests {
    private let list = """
    [
      {"id": "20755213826", "date": "2026-10-27", "type": "VirtualRide", "name": "Test MyWhoosh & Knee",
       "distance_km": 13.49, "duration_min": 30.4, "avg_hr": 140, "max_hr": 159, "avg_pace": null, "avg_watts": 113.1,
       "elevation_m": 1, "created_at": "2026-10-27 19:06:08", "workout_intent": "recovery", "workout_intent_label": "Recovery",
       "recorded_strength_session": null, "guided_session": null, "display_name": "Test MyWhoosh & Knee",
       "feedback": {"rpe": 3, "energy": 3, "muscle_soreness": 2, "pain_level": 0, "fuelling": null, "note": "ok"},
       "session_tags": {"verdict": null, "pre_fuel": null}},
      {"id": "20750126936", "date": "2026-10-27", "type": "Workout", "name": "Lunch Workout",
       "distance_km": 0.0, "duration_min": 34.0, "avg_hr": 116, "max_hr": 148, "avg_watts": null, "elevation_m": 0,
       "created_at": "2026-10-27 12:23:33", "workout_intent": "mobility", "workout_intent_label": "Mobility",
       "guided_session": {"title": "Rehab routine", "context_label": "Rehab"}, "display_name": "Rehab routine",
       "feedback": null, "session_tags": {"verdict": null}},
      {"id": "20742910273", "date": "2026-10-26", "type": "WeightTraining", "name": "Evening Weight Training",
       "distance_km": 0.0, "duration_min": 98.9, "avg_hr": 106, "created_at": "2026-10-26 21:30:21",
       "workout_intent": null, "recorded_strength_session": {"id": 36, "name": "Workout A · Upper Chest"},
       "display_name": "Workout A · Upper Chest", "feedback": {"rpe": 3, "energy": 3, "muscle_soreness": 2, "pain_level": 0}},
      {"id": "1", "date": "2026-10-24", "type": "Hike", "name": "Morning Hike", "distance_km": 10.17, "duration_min": 156.4,
       "elevation_m": 398, "feedback": {"rpe": 5, "energy": 3, "muscle_soreness": 3, "pain_level": 6}},
      {"id": "2", "date": "2026-10-25", "type": "WeightTraining", "name": "Workout C", "duration_min": 45,
       "session_tags": {"verdict": "loved"}}
    ]
    """

    private func activities() throws -> [ActivitySummary] {
        try APIClient.decoder.decode([ActivitySummary].self, from: Data(list.utf8))
    }

    @Test func decodesList() throws {
        let items = try activities()
        #expect(items.count == 5)
        #expect(items[0].feedback?.painLevel == 0)
        #expect(items[1].title == "Rehab routine")
        #expect(items[2].recordedStrengthSession?.id == 36)
        #expect(items[3].sessionTags == nil)
    }

    @Test func mapsSports() throws {
        let items = try activities()
        #expect(items.map(ActivityFormat.sport) == [.ride, .mobility, .strength, .hike, .strength])
    }

    @Test func subtitleSurfacesPainThenVerdictThenIntent() throws {
        let items = try activities()
        #expect(ActivityFormat.subtitle(items[0]).plain == "Tue 27 · Virtual ride · Recovery")
        #expect(ActivityFormat.subtitle(items[1]).plain == "Tue 27 · Guided · Rehab")
        #expect(ActivityFormat.subtitle(items[2]).plain == "Mon 26 · Strength · RPE 3")
        #expect(ActivityFormat.subtitle(items[3]).highlight == .init(text: "Pain 6/10", tone: .pain))
        #expect(ActivityFormat.subtitle(items[4]).highlight == .init(text: "Loved it", tone: .win))
    }

    @Test func headlineIsDistanceOrTime() throws {
        let items = try activities()
        #expect(ActivityFormat.headline(items[0]) == ("13.5", " km"))
        #expect(ActivityFormat.detail(items[0]) == "30m · 113 W")
        #expect(ActivityFormat.headline(items[1]) == ("34", " min"))
        #expect(ActivityFormat.detail(items[1]) == "116 bpm")
        #expect(ActivityFormat.headline(items[2]) == ("1h 39", "m"))
        #expect(ActivityFormat.detail(items[3]) == "2h 36 · 398 m↑")
    }

    @Test func groupsByMondayWeekNewestFirst() throws {
        let today = try #require(FoodFormat.parse("2026-10-27"))
        let weeks = ActivityFormat.weeks(try activities(), today: today)
        #expect(weeks.map(\.title) == ["This week · Oct 26 – Nov 1", "Last week · Oct 19 – 25"])
        // Same day: the later upload first.
        #expect(weeks[0].activities.map(\.id) == ["20755213826", "20750126936", "20742910273"])
        #expect(weeks[1].activities.map(\.id) == ["2", "1"])
    }

    @Test func clockFormats() {
        #expect(ActivityFormat.clock(30.4) == "30:24")
        #expect(ActivityFormat.clock(98.9) == "1:38:54")
    }

    private let detail = """
    {
      "activity": {"id": "9", "date": "2026-10-20", "type": "Run", "name": "Evening Run", "distance_km": 5.04,
                   "duration_min": 28.4, "avg_hr": 169, "workout_intent": "recovery", "workout_intent_label": "Recovery"},
      "stats": [
        {"key": "distance_km", "label": "Distance", "value": 5.04, "unit": "km"},
        {"key": "moving_time_min", "label": "Moving time", "value": 28.4, "unit": "min"},
        {"key": "avg_pace", "label": "Avg pace", "value": "5:38", "unit": null},
        {"key": "avg_hr", "label": "Avg HR", "value": 169, "unit": "bpm"},
        {"key": "max_hr", "label": "Max HR", "value": 179, "unit": "bpm"},
        {"key": "elevation_m", "label": "Elevation", "value": 20, "unit": "m"}
      ],
      "charts": [
        {"key": "heartrate", "label": "Heart rate", "unit": "bpm", "points": [{"x": 0, "t": 0, "y": 100}, {"x": 28, "t": 28, "y": 170}]},
        {"key": "altitude", "label": "Elevation", "unit": "m", "points": [{"x": 0, "t": 0, "y": 200}, {"x": 28, "t": 28, "y": 205}]}
      ],
      "feedback": {"rpe": 6, "energy": 3, "muscle_soreness": 2, "pain_level": 2, "note": null},
      "strength_detail": null,
      "analysis": {"status": "not_requested", "session_read": {"verdict": {"tone": "good", "headline": "Easy run stayed easy"},
                   "wins": [{"score": 40, "detail": "Kept it in zone 2."}]}}
    }
    """

    @Test func decodesDetailAndBuildsRunTiles() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        let tiles = ActivityDetailFormat.tiles(value, feedback: value.feedback)
        #expect(tiles.map(\.label) == ["Distance", "Time", "Pace", "Avg HR", "Max HR", "Pain"])
        #expect(tiles[1].value == "28:24")
        #expect(tiles[2].value == "5:38")
        #expect(tiles[5].value == "2")
    }

    @Test func chartFallsBackToHeartRateOnFlatGround() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        let series = try #require(ActivityDetailFormat.chartSeries(value.charts, sport: .run, minutes: 28.4))
        #expect(series.area == nil)
        #expect(series.title == "Heart rate")
        #expect(series.heartRate?.points.map(\.y) == [0.15, 1])
        #expect(series.duration == 28.4)
        #expect(series.ticks == [0, 10, 20, 28.4])
    }

    @Test func coachTakePrefersSavedAnalysis() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        #expect(ActivityDetailFormat.coachTake(value.analysis) == .init(headline: "Easy run stayed easy", body: "Kept it in zone 2."))
        let saved = """
        {"status": "stale", "headline": "Held up", "summary": "Keep it easy.", "session_read": null}
        """
        let analysis = try APIClient.decoder.decode(ActivityDetail.Analysis.self, from: Data(saved.utf8))
        #expect(ActivityDetailFormat.coachTake(analysis) == .init(headline: "Held up", body: "Keep it easy."))
    }

    @Test func setsLineUsesWorkSets() throws {
        let json = """
        {"id": "e1", "exercise_name": "Bench", "work_set_count": 3, "sets": [
          {"reps": 10, "weight_kg": 40, "is_warmup": true},
          {"reps": 8, "weight_kg": 62.5, "is_warmup": false},
          {"reps": 8, "weight_kg": 62.5, "is_warmup": false},
          {"reps": 7, "weight_kg": 60, "is_warmup": false}]}
        """
        let exercise = try APIClient.decoder.decode(ActivityDetail.StrengthDetail.Exercise.self, from: Data(json.utf8))
        #expect(ActivityDetailFormat.setsLine(exercise) == "3 × 8 · 62.5 kg")
    }

    @Test func encodesFeedbackInSnakeCase() throws {
        let input = ActivityFeedbackInput(rpe: 4, energy: 3, muscleSoreness: 2, painLevel: 1, note: nil)
        let object = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(input)) as? [String: Any]
        #expect(object?["muscle_soreness"] as? Int == 2)
        #expect(object?["pain_level"] as? Int == 1)
    }
}
