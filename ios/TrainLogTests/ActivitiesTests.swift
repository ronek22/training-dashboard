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

    private let paces = """
    {"paces": {"vdot": 38.2, "zones": {"easy": {"from_s": 364, "to_s": 408}, "marathon": {"pace_s": 339},
      "threshold": {"pace_s": 317}, "interval": {"pace_s": 291}, "repetition": {"pace_s": 277}}}}
    """

    @Test func runStatBlockPlacesPaceOnTrainingPaces() throws {
        var value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        value.bestEfforts = try APIClient.decoder.decode(ActivityDetail.BestEfforts.self, from: Data("""
        {"efforts": [{"label": "1K", "duration_s": 328, "metric_value": 5.47, "metric_unit": "min/km", "avg_hr": 177}]}
        """.utf8))
        let zones = try APIClient.decoder.decode(RunningPaces.self, from: Data(paces.utf8)).paces?.zones
        let block = ActivityDetailFormat.statBlock(value, paces: zones)
        #expect(block.headline.map(\.value) == ["5.04", "28:24"])
        let pace = try #require(block.gauges.first)
        #expect(pace.value == "5:38")
        #expect(pace.side.map(\.bold) == ["5:28", "≈ Marathon"])
        // 7:30 → 4:23 track: 5:38 sits 62% of the way along, the best km just past it.
        #expect(abs(pace.dot - (450 - 338) / (450 - 263)) < 0.001)
        #expect(pace.tick.map { $0 > pace.dot } == true)
        #expect(block.gauges[1].label == "Heart rate")
        #expect(block.gauges[1].bands.isEmpty)
        #expect(block.footer.map(\.0) == ["Climb"])
    }

    @Test func paceGaugeGoesPlainWithoutPaces() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        let pace = try #require(ActivityDetailFormat.statBlock(value).gauges.first)
        #expect(pace.bands.isEmpty)
        #expect(pace.labels.map(\.text) == ["7:30", "4:30"])
    }

    private let ride = """
    {
      "activity": {"id": "1", "date": "2026-10-27", "type": "VirtualRide", "name": "Test MyWhoosh & Knee", "duration_min": 30.4},
      "stats": [
        {"key": "distance_km", "label": "Distance", "value": 13.49, "unit": "km"},
        {"key": "moving_time_min", "label": "Moving time", "value": 30.4, "unit": "min"},
        {"key": "avg_speed_kmh", "label": "Speed", "value": 26.6, "unit": "km/h"},
        {"key": "avg_hr", "label": "Avg HR", "value": 140, "unit": "bpm"},
        {"key": "max_hr", "label": "Max HR", "value": 159, "unit": "bpm"}
      ],
      "charts": [],
      "heart_rate_zones": {"available": true, "zone2_pct": 69, "zones": [
        {"key": "zone1", "label": "Zone 1", "minutes": 9.1, "pct": 30, "bpm_range": "< 140 bpm", "lower_bpm": null, "upper_bpm": 140},
        {"key": "zone2", "label": "Zone 2", "minutes": 20.9, "pct": 69, "bpm_range": "140-152 bpm", "lower_bpm": 140, "upper_bpm": 152},
        {"key": "zone3", "label": "Zone 3", "minutes": 0.4, "pct": 1, "bpm_range": "153-162 bpm", "lower_bpm": 153, "upper_bpm": 162},
        {"key": "zone4", "label": "Zone 4", "minutes": 0, "pct": 0, "bpm_range": "163-172 bpm", "lower_bpm": 163, "upper_bpm": 172},
        {"key": "zone5", "label": "Zone 5", "minutes": 0, "pct": 0, "bpm_range": ">= 173 bpm", "lower_bpm": 173, "upper_bpm": null}]},
      "cycling": {"environment": "indoor", "ftp_watts": 215, "power_source": "measured",
        "power": {"avg_watts": 113.1, "normalized_watts": 126, "intensity_factor": 0.58, "tss": 17, "variability_index": 1.11, "work_kj": 206},
        "decoupling": {"available": false, "reason_label": "Shorter than 45 minutes"}},
      "win": {"kind": "consistency", "headline": "Easy ride stayed easy", "detail": "1% above Zone 2."},
      "analysis": {"status": "not_requested", "session_read": {"verdict": {"tone": "good", "badge": "On intent", "headline": "Easy ride stayed easy"}}}
    }
    """

    @Test func rideStatBlockUsesFtpAndHeartRateZones() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(ride.utf8))
        let block = ActivityDetailFormat.statBlock(value)
        #expect(block.headline.map(\.value) == ["13.5", "30:24"])
        let power = block.gauges[0]
        #expect(power.value == "113")
        #expect(power.side.map(\.bold) == ["126", "53%"])
        #expect(abs(power.dot - 113.1 / 215 / 1.5) < 0.001)
        #expect(power.bands.count == 6)
        let hr = block.gauges[1]
        #expect(hr.labels.map(\.text) == ["100", "Z2 140", "Z4 163", "190"])
        #expect(hr.side.map(\.bold) == ["159", "69%"])
        #expect(abs(hr.dot - 40.0 / 90) < 0.001)
        #expect(block.footer.map(\.0) == ["Speed", "TSS"])
    }

    @Test func rideCardsFromThePayload() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(ride.utf8))
        #expect(ActivityDetailFormat.chips(value) == ["Indoor · MyWhoosh", "FTP 215 W"])
        // The read only repeats the win, so it hides.
        #expect(ActivityDetailFormat.sessionRead(value) == nil)
        let rows = ActivityDetailFormat.zoneRows(value.heartRateZones, unit: "bpm")
        #expect(rows.map(\.name) == ["Z1", "Z2", "Z3", "Z4+"])
        #expect(rows.last?.range == "163 bpm and up")
        let load = try #require(ActivityDetailFormat.loadTiles(value.cycling))
        #expect(load.note == "measured power")
        #expect(load.tiles.map(\.value) == ["126", "0.58", "17", "1.11", "206", "< 45 min"])
        #expect(ActivityDetailFormat.coachState(value.analysis) == .canAsk(failed: false))
    }

    @Test func liftRowsCompareWithLastTime() throws {
        let json = """
        {"session": {"set_count": 4, "rep_count": 32, "total_volume_kg": 2000, "exercises": [
          {"id": "e1", "exercise_name": "Barbell Incline Bench Press", "work_set_count": 2, "sets": [
            {"reps": 10, "weight_kg": 40, "is_warmup": true},
            {"reps": 8, "weight_kg": 62.5, "is_warmup": false},
            {"reps": 8, "weight_kg": 62.5, "is_warmup": false}]},
          {"id": "e2", "exercise_name": "Pull Up", "work_set_count": 1, "sets": [{"reps": 10, "weight_kg": null, "is_warmup": false}]}]},
         "progression": {"exercises": {
          "bench": {"exercise_name": "Barbell Incline Bench Press", "metric": "e1rm", "delta": 3.2, "direction": "up", "is_pr": false,
                    "next_hint": "Every set at 62.5 kg × 8 — try 65 kg next time.",
                    "current": {"volume_kg": 2000}, "previous": {"volume_kg": 1920, "date": "2026-10-10"}},
          "pullup": {"exercise_name": "Pull Up", "metric": "reps", "delta": -2, "direction": "down", "is_pr": false,
                     "next_hint": "Add a rep per set — aim for 11 on every set.",
                     "current": {"volume_kg": 0}, "previous": {"volume_kg": 0, "date": "2026-10-18"}}}}}
        """
        var value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        value = ActivityDetail(activity: value.activity, stats: [], charts: [], feedback: nil, sessionTags: nil,
                               strengthDetail: try APIClient.decoder.decode(ActivityDetail.StrengthDetail.self, from: Data(json.utf8)),
                               analysis: nil)
        let rows = ActivityDetailFormat.liftRows(value)
        #expect(rows.map(\.name) == ["Barbell Incline Bench", "Pull Up"])
        #expect(rows[0].sets == ["62.5×8", "62.5×8"])
        #expect(rows[1].sets == ["BW×10"])
        #expect(rows[0].badge?.text == "↑ e1RM +3.2 kg")
        #expect(rows[1].badge?.text == "↓ 2 reps")
        #expect(rows[0].hint?.action == "try 65 kg")
        #expect(rows[1].hint?.lead == "Add a rep per set")
        let volume = try #require(ActivityDetailFormat.volumeGauge(value))
        #expect(volume.value == "+4")
        #expect(volume.side.first?.bold == "1.92 t")
    }

    @Test func coachStatePrefersSavedAnalysis() throws {
        let saved = """
        {"status": "stale", "headline": "Held up", "summary": "Keep it easy.", "key_observations": ["One", "Two"], "session_read": null}
        """
        let analysis = try APIClient.decoder.decode(ActivityDetail.Analysis.self, from: Data(saved.utf8))
        #expect(ActivityDetailFormat.coachState(analysis) == .take(.init(headline: "Held up", body: "Keep it easy.", observations: ["One", "Two"])))
        let pending = try APIClient.decoder.decode(ActivityDetail.Analysis.self, from: Data(#"{"status": "pending"}"#.utf8))
        #expect(ActivityDetailFormat.coachState(pending) == .pending)
        let unsupported = try APIClient.decoder.decode(ActivityDetail.Analysis.self, from: Data(#"{"available": false, "status": "not_requested"}"#.utf8))
        #expect(ActivityDetailFormat.coachState(unsupported) == .none)
    }

    @Test func chartTabsFollowTheSport() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
        let set = try #require(ActivityDetailFormat.chartSet(value))
        // Flat ground: no elevation tab, so heart rate alone.
        #expect(set.tabs.map(\.key) == ["heartrate"])
        #expect(set.duration == 28.4)
        #expect(set.ticks == [0, 10, 20, 28.4])
        #expect(ActivityDetailFormat.scrubValue("pace", 5.5) == "5:30 /km")
    }

    @Test func decodesEncodedPolyline() {
        let points = ActivityDetailFormat.decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        #expect(points.count == 3)
        #expect(abs(points[0].latitude - 38.5) < 0.00001 && abs(points[0].longitude + 120.2) < 0.00001)
        #expect(abs(points[2].latitude - 43.252) < 0.00001 && abs(points[2].longitude + 126.453) < 0.00001)
    }

    @Test func encodesFeedbackInSnakeCase() throws {
        let input = ActivityFeedbackInput(rpe: 4, energy: 3, muscleSoreness: 2, painLevel: 1, note: nil)
        let object = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(input)) as? [String: Any]
        #expect(object?["muscle_soreness"] as? Int == 2)
        #expect(object?["pain_level"] as? Int == 1)
    }
}
