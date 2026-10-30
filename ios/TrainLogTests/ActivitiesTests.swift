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
      "run_dynamics": {"cadence_spm": 154.8, "stance_time_ms": 251, "vertical_oscillation_cm": 10.46, "vertical_ratio_pct": 8.99,
                       "step_length_m": 1.163, "avg_power_w": 241, "splits": [
        {"km": 1, "seconds": 350, "heart_rate": 154.8, "cadence_spm": 151.5, "power_w": 229.3},
        {"km": 2, "seconds": 338, "heart_rate": 167.1, "cadence_spm": 157.2, "power_w": 240.7},
        {"km": 3, "seconds": 351, "heart_rate": 172.2, "cadence_spm": 155.4, "power_w": 234.8},
        {"km": 4, "seconds": 333, "heart_rate": 176.2, "cadence_spm": 156.0, "power_w": 252.9},
        {"km": 5, "seconds": 332, "heart_rate": 176.9, "cadence_spm": 155.5, "power_w": 243.2}]},
      "analysis": {"status": "not_requested", "session_read": {"verdict": {"tone": "bad", "badge": "Off intent", "headline": "Easy run ran hot"},
                   "signals": [{"key": "pace_at_hr", "label": "Pace at ~169 bpm", "value": "5:38/km", "detail": "17 s/km slower than 5 similar runs", "tone": "warn"},
                               {"key": "hr_cap", "label": "Average heart rate", "value": "169 bpm", "detail": "over the 162 bpm easy cap", "tone": "warn"}],
                   "wins": [{"score": 40, "detail": "Kept it in zone 2."}]}}
    }
    """

    private let fitness = """
    {"form": {"baseline": {"cadence_spm": 155.2, "step_length_m": 1.2, "vertical_oscillation_cm": 10.23, "vertical_ratio_pct": 8.55,
                           "stance_time_ms": 248.8, "avg_power_w": 244},
              "ranges": {"cadence_spm": {"good": [165, 185]}, "stance_time_ms": {"good": [200, 260]},
                         "vertical_oscillation_cm": {"good": [6, 10]}, "vertical_ratio_pct": {"good": [6, 8.5]}}}}
    """

    private func run() throws -> ActivityDetail {
        try APIClient.decoder.decode(ActivityDetail.self, from: Data(detail.utf8))
    }

    @Test func runHeaderAndGrid() throws {
        let value = try run()
        let header = ActivityDetailFormat.header(value.activity, detail: value)
        #expect(header.big?.value == "5.04")
        #expect(header.big?.unit == "km")
        #expect(header.dateLine == "Tue 20 Oct · HealthFit")
        #expect(header.facts.map(\.value) == ["Recovery", "+20 m"])
        let cells = ActivityDetailFormat.grid(value)
        #expect(cells.map(\.label) == ["Moving time", "Avg pace", "Climb", "Avg heart rate"])
        #expect(cells[0].parts.map(\.value) == ["28", "24"])
        #expect(cells[0].status?.text == "Recovery run planned")
        #expect(cells[1].status?.text == "17 s/km slower at this HR")
        #expect(cells[1].status?.tone == .warn)
        #expect(cells[3].status?.text == "Over the 162 easy cap")
    }

    @Test func headerWithoutDetailComesFromTheListRow() throws {
        let header = ActivityDetailFormat.header(try run().activity)
        #expect(header.title == "Evening Run")
        #expect(header.dateLine == "Tue 20 Oct")
        #expect(header.facts.isEmpty)
    }

    @Test func splitsFillTheFastestKilometre() throws {
        let rows = ActivityDetailFormat.splits(try run())
        #expect(rows.map(\.pace) == ["5:50", "5:38", "5:51", "5:33", "5:32"])
        #expect(rows.filter(\.fastest).map(\.km) == [5])
        #expect(abs(rows[2].share - 0.46) < 0.001)
        #expect(rows[4].share == 1)
        let lines = ActivityDetailFormat.splitLines(rows)
        #expect(lines.map(\.text) == ["Negative split: the last two km were your fastest", "Heart rate rose every km, 155 → 177 bpm"])
    }

    @Test func runningFormUsesRangesAndUsualValues() throws {
        let form = try APIClient.decoder.decode(RunningFitness.self, from: Data(fitness.utf8)).form
        let cells = ActivityDetailFormat.form(try run(), fitness: form)
        #expect(cells.map(\.label) == ["Cadence", "Ground contact", "Step length", "Vert. oscillation", "Vert. ratio", "Power"])
        #expect(cells.map(\.word) == ["Low", "Good", "Shorter", "High", "High", "Typical"])
        #expect(cells.map(\.ranged) == [true, true, false, true, true, false])
        #expect(cells[0].usual == "155")
        let summary = try #require(ActivityDetailFormat.formSummary(cells))
        #expect(summary.text == "Cadence is low and you bounce a little more than ideal, both usual for you. Ground contact is good.")
    }

    @Test func sessionReadKeepsAVerdictSentenceAndLines() throws {
        let read = try #require(ActivityDetailFormat.sessionRead(try run()))
        #expect(read.badge == "Off intent")
        #expect(read.tone == .warn)
        #expect(read.lines.first?.text == "Pace at ~169 bpm: 5:38/km · 17 s/km slower than 5 similar runs")
    }

    @Test func feelWordsFollowTheReading() throws {
        let feel = ActivityDetailFormat.feel(ActivityFeedback(rpe: 2, energy: 4, muscleSoreness: 3, painLevel: 6, note: "ITBS a lot of knee pain"))
        #expect(feel.map(\.word) == ["Very easy", "Good", "Some", "Knee"])
        #expect(ActivityDetailFormat.painAlert(ActivityFeedback(rpe: 2, energy: 4, muscleSoreness: 3, painLevel: 6, note: "x"))?.pain == 6)
        #expect(ActivityDetailFormat.feel(nil).isEmpty)
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

    @Test func indoorRideGridComparisonsAndTrace() throws {
        let value = try APIClient.decoder.decode(ActivityDetail.self, from: Data(ride.utf8))
        #expect(ActivityDetailFormat.isIndoorRide(value))
        #expect(ActivityDetailFormat.route(value) == nil)
        let header = ActivityDetailFormat.header(value.activity, detail: value)
        #expect(header.kicker == "Indoor ride · MyWhoosh")
        #expect(header.dateLine == "Tue 27 Oct · FTP 215 W")
        #expect(header.big?.value == "13.5")
        let cells = ActivityDetailFormat.grid(value)
        #expect(cells.map(\.label) == ["Moving time", "Avg speed", "Normalized power", "Avg heart rate"])
        #expect(cells[2].status?.text == "Avg 113 W")
        #expect(cells[3].status?.text == "69% in Zone 2")
        let compared = ActivityDetailFormat.compared(value)
        #expect(compared.map(\.label) == ["Intensity"])
        #expect(compared[0].status?.text == "TSS 17 · VI 1.11")
        #expect(ActivityDetailFormat.zoneRows(value.heartRateZones).map(\.name) == ["Zone 1", "Zone 2", "Zone 3", "Zone 4+"])
        #expect(ActivityDetailFormat.zoneRows(value.heartRateZones, full: true).count == 5)
        #expect(ActivityDetailFormat.zoneSummary(value)?.text == "Easy all the way: 99% in Zones 1–2.")
        // The win repeats the verdict, so it shows in the read only.
        #expect(ActivityDetailFormat.win(value) == nil)
        #expect(ActivityDetailFormat.coachState(value.analysis) == .canAsk(failed: false))
    }

    @Test func zoneIndexAndColourScale() {
        #expect(ActivityDetailFormat.zoneIndex(100, lowers: [118, 161, 194]) == 0)
        #expect(ActivityDetailFormat.zoneIndex(150, lowers: [118, 161, 194]) == 1)
        #expect(ActivityDetailFormat.zoneIndex(300, lowers: [118, 161, 194]) == 3)
        #expect(ActivityDetailFormat.durationParts(43.6) .map(\.value) == ["43", "36"])
        #expect(ActivityDetailFormat.durationParts(98.9).map(\.value) == ["1", "39"])
        #expect(ActivityDetailFormat.withStops(179.9) == "3h 00m with stops")
        #expect(ActivityDetailFormat.world("Zwift - California Dreamin' in Watopia") == "Watopia")
        #expect(ActivityDetailFormat.niceTicks(5.3...7.1, steps: [0.25, 0.5, 1]) == [5.5, 6, 6.5, 7])
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
                    "current": {"volume_kg": 2000}, "previous": {"volume_kg": 1920, "date": "2026-10-10",
                    "sets": [{"reps": 8, "weight_kg": 60}, {"reps": 8, "weight_kg": 60}, {"reps": 8, "weight_kg": 60}, {"reps": 8, "weight_kg": 60}]}},
          "pullup": {"exercise_name": "Pull Up", "metric": "reps", "delta": -2, "direction": "down", "is_pr": false,
                     "current": {"volume_kg": 0}, "previous": {"volume_kg": 0, "date": "2026-10-18", "sets": [{"reps": 12, "weight_kg": null}, {"reps": 10, "weight_kg": null}]}}}}}
        """
        var value = try run()
        value = ActivityDetail(activity: value.activity, stats: [], charts: [], feedback: nil, sessionTags: nil,
                               strengthDetail: try APIClient.decoder.decode(ActivityDetail.StrengthDetail.self, from: Data(json.utf8)),
                               analysis: nil)
        let rows = ActivityDetailFormat.liftRows(value)
        #expect(rows.map(\.muscle) == ["Chest", "Lats"])
        #expect(rows[0].sets.map { $0.value + $0.unit } == ["62.5×8", "62.5×8"])
        #expect(rows[1].sets.map { $0.value + $0.unit } == ["10 reps"])
        #expect(rows[0].badge?.text == "▲ 3.2 kg e1RM")
        #expect(rows[1].badge?.text == "▼ 2 reps")
        #expect(rows[0].last == "Last 4 × 8 @ 60 kg · 10 Oct")
        #expect(rows[1].last == "Last 12 · 10 reps · 18 Oct")
        #expect(rows[0].next == "65 kg next time")
        let volume = try #require(ActivityDetailFormat.volumeChange(value))
        #expect(volume.parts.first?.value == "+4")
        #expect(volume.status?.text == "1.92 t · same 2 lifts")
        #expect(ActivityDetailFormat.liftsComparedTo(value) == "vs last time")
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

    @Test func chartModelsFollowTheSport() throws {
        let value = try run()
        // Flat ground: no elevation chip, so heart rate alone.
        #expect(ActivityDetailFormat.chips(value).map(\.key) == ["heartrate"])
        let model = try #require(ActivityDetailFormat.chartModel(value, key: "heartrate"))
        #expect(model.xTicks.map(\.label) == ["0:00", "10:00", "20:00", "28:00"])
        #expect(model.averageLabel == "169")
        #expect(ActivityDetailFormat.scrubValue("pace", 5.5) == "5:30 /km")
    }

    @Test func sheetsStackHeartRateUnderEverythingElse() throws {
        let value = try run()
        #expect(ActivityDetailFormat.compareKeys(value, key: "pace") == ["heartrate"])
        // Flat ground: elevation is too flat to compare with.
        #expect(ActivityDetailFormat.compareKeys(value, key: "heartrate") == [])
    }

    @Test func runningFormSheetPlacesTodayOnTheRange() throws {
        let form = try APIClient.decoder.decode(RunningFitness.self, from: Data(fitness.utf8)).form
        let rows = ActivityDetailFormat.formDetails(try run(), fitness: form)
        #expect(rows.map(\.cell.label) == ["Cadence", "Ground contact", "Step length", "Vert. oscillation", "Vert. ratio", "Power"])
        let cadence = rows[0]
        #expect(cadence.good == 165...185)
        #expect(cadence.usual == 155.2)
        #expect(cadence.scale.contains(cadence.value) && cadence.scale.contains(185))
        #expect(cadence.perKm.count == 5)
        #expect(cadence.drift == "152 → 156 spm from the first km to the last")
        // No range for step length or power: compared with your usual only.
        #expect(rows[2].good == nil)
        #expect(rows[5].note?.hasPrefix("Running power") == true)
    }

    @Test func splitsSheetKeepsColumnsThatHaveData() throws {
        let columns = ActivityDetailFormat.splitColumns(try run())
        // The fixture's splits have no ground contact, oscillation or step length.
        #expect(columns.map(\.title) == ["Pace", "HR", "Cad", "W"])
        #expect(columns[0].values.first == "5:50")
        #expect(columns[3].values.last == "243")
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
