import Foundation
import Testing
@testable import TrainLog

struct WeightTrendTests {
    @Test func decodesTheMuscleGainWeightBlock() throws {
        let json = """
        {"weight": {"window_days": 42, "min_weigh_ins": 4, "available": true, "status": "gentle_gain",
          "weigh_ins": [{"date": "2026-10-12", "kg": 79.0, "source": "manual"}, {"date": "2026-11-02", "kg": 80.0, "source": "manual"}],
          "smoothed": [{"date": "2026-10-12", "kg": 79.0}, {"date": "2026-11-02", "kg": 79.75}],
          "start_kg": 79.0, "end_kg": 79.75, "kg_per_week": 0.25, "pct_per_week": 0.32,
          "gentle_gain_kg_per_week": [0.08, 0.28]},
         "groups": []}
        """
        let trend = try APIClient.decoder.decode(MuscleGainWeight.self, from: Data(json.utf8)).weight
        let line = try #require(QuickLogFormat.trendLine(trend))
        #expect(line.average == "79.8")
        #expect(line.rate == "+0.25 kg a week, lean gain")
        #expect(line.onTrack)
    }

    @Test func offTrackStatesAreNamed() throws {
        let flat = WeightTrend(available: true, status: "flat", endKg: 79.5, kgPerWeek: -0.1)
        #expect(QuickLogFormat.trendLine(flat)?.rate == "−0.10 kg a week, flat")
        #expect(QuickLogFormat.trendLine(flat)?.onTrack == false)
        let fast = WeightTrend(available: true, status: "fast_gain", endKg: 80.4, kgPerWeek: 0.6)
        #expect(QuickLogFormat.trendLine(fast)?.rate == "+0.60 kg a week, faster than lean gain")
    }

    @Test func notEnoughWeighInsSaysHowManyMore() {
        let point = WeightTrend.Point(date: "2026-11-02", kg: 80)
        let sparse = WeightTrend(available: false, status: "unavailable", minWeighIns: 4, weighIns: [point, point])
        #expect(QuickLogFormat.trendLine(sparse) == nil)
        #expect(QuickLogFormat.trendNeeds(sparse) == "2 more weigh-ins for a trend")
        let spanTooShort = WeightTrend(available: false, status: "unavailable", minWeighIns: 4, weighIns: Array(repeating: point, count: 4))
        #expect(QuickLogFormat.trendNeeds(spanTooShort) == "a few more days for a trend")
        #expect(QuickLogFormat.trendNeeds(nil) == nil)
    }

    @Test func typoWarningOnlyWhenFarFromTheAverage() {
        #expect(QuickLogFormat.typoWarning(typed: 89.6, average: 79.7) == "9.9 kg above your average · typo?")
        #expect(QuickLogFormat.typoWarning(typed: 77.0, average: 79.7) == "2.7 kg below your average · typo?")
        #expect(QuickLogFormat.typoWarning(typed: 80.5, average: 79.7) == nil)
        #expect(QuickLogFormat.typoWarning(typed: 89.6, average: nil) == nil)
        #expect(QuickLogFormat.shortDate("2026-11-02") == "Nov 2")
    }
}
