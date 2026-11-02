import Foundation
import Testing
@testable import TrainLog

struct RunTests {
    private let sample = """
    {
      "available": true, "today": "2026-11-03",
      "summary": {"runs": 1395, "last_run": {"date": "2026-09-09", "activity_id": "1", "name": "Evening Run", "distance_km": 5.04, "days_ago": 55}},
      "vdot": {"current": 38.2, "basis": "heart_rate", "stale": false,
               "peak": {"date": "2015-09-23", "activity_id": "2", "name": "10K", "vdot": 55.1, "effort": "10K", "seconds": 2282.9, "distance_m": 10000.0},
               "projected": 41.2, "projection_weeks": 8, "share_of_peak_pct": 69},
      "paces": {"vdot": 38.2, "zones": {
                  "easy": {"label": "Easy", "from_s": 364, "to_s": 408, "use": "Most of your running"},
                  "marathon": {"label": "Marathon", "pace_s": 339, "use": "Steady"},
                  "threshold": {"label": "Threshold", "pace_s": 317, "use": "Tempo"},
                  "interval": {"label": "Interval", "pace_s": 291, "use": "Reps"},
                  "repetition": {"label": "Repetition", "pace_s": 277, "use": "Short reps"}},
                "quality_allowed": false, "hr_cap_bpm": 162, "eased_s": 0, "peak_easy": {"from_s": 272, "to_s": 305}},
      "return_to_run": {"active": true, "stage": 3, "stage_name": "Run/walk 5:1", "stages": 6,
                        "stage_names": ["Run/walk 1:2", "Run/walk 2:1", "Run/walk 5:1", "Continuous 20 min", "Continuous 30–40 min", "Back to normal running"],
                        "minutes": 30, "pace_target": false, "symptom": "Knee", "quality_allowed": false,
                        "blocks": [{"kind": "walk", "minutes": 5}, {"kind": "jog", "minutes": 5}, {"kind": "walk", "minutes": 1},
                                   {"kind": "jog", "minutes": 5}, {"kind": "walk", "minutes": 1}]},
      "felt": [{"activity_id": "a", "date": "2026-11-01", "name": "Run", "distance_km": 5.0, "duration_min": 31.0, "pace_s": 372, "avg_hr": 150, "felt": "hard"},
               {"activity_id": "b", "date": "2026-11-03", "name": "Morning Run", "distance_km": 5.2, "duration_min": 32.2, "pace_s": 371, "avg_hr": 149.5, "felt": null}],
      "form": {"baseline": {"cadence_spm": 168}, "ranges": {"cadence_spm": {"good": [165, 185]}}}
    }
    """

    private var fitness: RunningFitness {
        get throws { try APIClient.decoder.decode(RunningFitness.self, from: Data(sample.utf8)) }
    }

    @Test func decodesRunningFitness() throws {
        let fitness = try fitness
        #expect(fitness.vdot?.shareOfPeakPct == 69)
        #expect(fitness.paces?.zones.easy == .init(fromS: 364, toS: 408))
        #expect(fitness.paces?.peakEasy?.fromS == 272)
        #expect(fitness.returnToRun?.blocks?.count == 5)
        #expect(fitness.felt?.first?.felt == .hard)
        #expect(fitness.felt?.last?.felt == nil)
        #expect(fitness.form?.baseline?.cadenceSpm == 168)
    }

    @Test func decodesAnOlderServerWithoutTheNewFields() throws {
        let json = #"{"available": true, "paces": {"vdot": 40, "quality_allowed": true, "hr_cap_bpm": 160, "zones": {"easy": {"from_s": 350, "to_s": 390}, "marathon": {"pace_s": 320}, "threshold": {"pace_s": 300}, "interval": {"pace_s": 280}, "repetition": {"pace_s": 265}}}, "return_to_run": {"active": false, "quality_allowed": true}}"#
        let fitness = try APIClient.decoder.decode(RunningFitness.self, from: Data(json.utf8))
        #expect(fitness.paces?.easedS == nil)
        #expect(fitness.returnToRun?.blocks == nil)
        #expect(fitness.felt == nil)
    }

    @Test func formatsPaces() {
        #expect(RunFormat.pace(364) == "6:04")
        #expect(RunFormat.pace(305) == "5:05")
        #expect(RunFormat.band(.init(fromS: 364, toS: 408)) == "6:04–6:48")
    }

    @Test func tapeSpansTheBandOnTenSecondMarks() {
        #expect(RunFormat.tapeRange(.init(fromS: 364, toS: 408)) == 350...420)
    }

    @Test func verdictComparesThePaceWithTheBand() {
        let band = RunningFitness.Band(fromS: 364, toS: 408)
        #expect(RunFormat.verdict(371, band: band) == .inside)
        #expect(RunFormat.verdict(338, band: band) == .faster)
        #expect(RunFormat.verdict(420, band: band) == .slower)
    }

    @Test func asksOnceForTheNewestRecentRun() throws {
        let runs = try fitness.felt ?? []
        #expect(RunFormat.pendingFeel(runs, today: "2026-11-03", answered: [], dismissed: [])?.activityId == "b")
        #expect(RunFormat.pendingFeel(runs, today: "2026-11-04", answered: [], dismissed: [])?.activityId == "b")
        #expect(RunFormat.pendingFeel(runs, today: "2026-11-05", answered: [], dismissed: []) == nil, "older than two days")
        #expect(RunFormat.pendingFeel(runs, today: "2026-11-03", answered: ["b"], dismissed: []) == nil)
        #expect(RunFormat.pendingFeel(runs, today: "2026-11-03", answered: [], dismissed: ["b"]) == nil)
        #expect(RunFormat.pendingFeel(Array(runs.prefix(1)), today: "2026-11-01", answered: [], dismissed: []) == nil, "already answered")
    }

    @Test func secondHardRunEasesTheNextBand() {
        let band = RunningFitness.Band(fromS: 364, toS: 408)
        let eased = RunFormat.nextBand(after: .hard, previous: [.easy, .hard], current: band, easedNow: 0)
        #expect(eased.eased == 10)
        #expect(eased.band == .init(fromS: 374, toS: 418))
        let first = RunFormat.nextBand(after: .hard, previous: [.easy], current: band, easedNow: 0)
        #expect(first.eased == 0 && first.band == band)
        // An easy run after the band was eased puts it back.
        let back = RunFormat.nextBand(after: .easy, previous: [.hard, .hard], current: .init(fromS: 374, toS: 418), easedNow: 10)
        #expect(back.band == band)
    }

    @Test func stageLabelsAndHeadline() throws {
        let fitness = try fitness
        #expect(fitness.returnToRun?.stageNames?.map(RunFormat.stageShort) == ["1:2", "2:1", "5:1", "20′", "40′", "Full"])
        let headline = RunFormat.stageHeadline(fitness.returnToRun?.blocks ?? [])
        #expect(headline.big == "5:1")
        #expect(headline.line == "2 rounds, after a 5 min walk")
        let continuous = RunFormat.stageHeadline([.init(kind: "walk", minutes: 5), .init(kind: "jog", minutes: 20)])
        #expect(continuous.big == "20 min")
        #expect(continuous.line == "After a 5 min walk")
    }

    @Test func qualityPacesShowWhenTheyOpen() throws {
        let zones = RunFormat.zones(try #require(try fitness.paces))
        #expect(zones.map(\.name) == ["Easy", "Marathon", "Threshold", "Interval", "Repetition"])
        #expect(zones[0].pace == "6:04–6:48")
        #expect(zones[1].opens == "in 2 weeks")
        #expect(zones[4].opens == "later")
    }

    @Test func syncLogNamesTheRunWrites() {
        #expect(SyncFormat.label(method: "PUT", path: "/activities/123/felt") == "Run feel")
        #expect(SyncFormat.label(method: "PUT", path: "/activities/123/symptoms") == "Run pain")
    }
}
