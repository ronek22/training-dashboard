import Foundation
import Testing
@testable import TrainLog

struct TrendsTests {
    private let history = """
    {"heart_rate_zone_summary": {}, "activity_heatmap": {"year": 2026},
     "ride_year_series": [
       {"month": "Jan", "monthly_km": 300.0, "monthly_hours": 10.0, "monthly_sessions": 8, "cumulative_km": 300.0, "cumulative_hours": 10.0, "cumulative_sessions": 8},
       {"month": "Feb", "monthly_km": 883.0, "monthly_hours": 30.0, "monthly_sessions": 15, "cumulative_km": 1183.0, "cumulative_hours": 40.0, "cumulative_sessions": 23},
       {"month": "Mar", "monthly_km": 255.8, "monthly_hours": 8.0, "monthly_sessions": 8, "cumulative_km": 1438.8, "cumulative_hours": 48.0, "cumulative_sessions": 31}],
     "run_year_series": [
       {"month": "Jan", "monthly_km": 0.0, "monthly_hours": 0.0, "monthly_sessions": 0, "cumulative_km": 0.0, "cumulative_hours": 0.0, "cumulative_sessions": 0}],
     "strength_year_series": [
       {"month": "Jan", "monthly_hours": 7.5, "monthly_sessions": 9, "cumulative_hours": 7.5, "cumulative_sessions": 9}]}
    """

    private let health = """
    {"metrics": {
       "resting_hr": {"label": "Resting heart rate", "available": true, "latest": null, "history": [
         {"date": "2026-10-24", "value": 57.0, "unit": "bpm"}, {"date": "2026-10-23", "value": 59.0, "unit": "bpm"}]},
       "hrv": {"label": "Heart-rate variability", "available": true, "history": [{"date": "2026-10-24", "value": 54.0}]},
       "weight": {"label": "Body weight", "available": false, "history": []},
       "sleep": {"label": "Sleep", "available": true, "history": [
         {"date": "2026-10-24", "value": 6.33, "stages": {"core": 4.27, "deep": 0.42, "rem": 1.65, "awake": 1.61}}]},
       "steps": {"label": "Steps", "available": false, "history": []}},
     "sleep_debt": {"available": false}, "last_import": {"export_date": "2026-10-24T07:08:55Z"}}
    """

    @Test func decodesTrainingHistory() throws {
        let decoded = try APIClient.decoder.decode(TrainingHistory.self, from: Data(history.utf8))
        #expect(decoded.rideYearSeries.count == 3)
        #expect(decoded.strengthYearSeries[0].monthlyKm == nil)

        let ride = TrendsFormat.year(.ride, decoded.rideYearSeries)
        #expect(ride.total == 1438.8)
        #expect(ride.best?.name == "Feb")
        #expect(ride.current?.letter == "M")
        #expect(TrendsFormat.total(ride.total) == "1,439")
        #expect(TrendsFormat.monthValue(2549.2, unit: "km") == "2,549 km")

        let strength = TrendsFormat.year(.strength, decoded.strengthYearSeries)
        #expect(strength.unit == "h")
        #expect(strength.total == 7.5)
        #expect(TrendsFormat.year(.run, decoded.runYearSeries).best == nil)
    }

    @Test func decodesHealthSummary() throws {
        let decoded = try APIClient.decoder.decode(HealthSummary.self, from: Data(health.utf8))
        #expect(decoded.metrics.restingHr?.history.count == 2)
        #expect(decoded.metrics.sleep?.history.first?.stages?.deep == 0.42)
        #expect(decoded.metrics.steps?.available == false)
        #expect(decoded.lastImport?.exportDate == "2026-10-24T07:08:55Z")
    }

    private func points(_ values: [Double], endingOn end: String = "2026-10-24") -> [HealthPoint] {
        let last = FoodFormat.parse(end)!
        return values.reversed().enumerated().map { offset, value in
            HealthPoint(date: FoodFormat.iso(Calendar(identifier: .gregorian).date(byAdding: .day, value: -offset, to: last)!), value: value)
        }
    }

    @Test func comparesLastWeekToTheMonthBefore() {
        // 20 days at 60 bpm, then a week at 56.
        let trend = TrendsFormat.trend(.restingHr, points(Array(repeating: 60, count: 20) + Array(repeating: 56, count: 7)), days: 30)
        #expect(trend.days.count == 27)
        #expect(trend.weekAverage == 56)
        #expect(trend.baseline == 60)
        let delta = TrendsFormat.delta(trend)
        #expect(delta?.text == "−4 bpm vs 30 d")
        #expect(delta?.good == true)
    }

    @Test func needsABaselineAndCallsSmallChangesSteady() {
        #expect(TrendsFormat.trend(.hrv, points([50, 52, 54]), days: 30).baseline == nil)
        let steady = TrendsFormat.trend(.sleep, points(Array(repeating: 7.0, count: 10) + Array(repeating: 7.1, count: 7)), days: 30)
        #expect(TrendsFormat.delta(steady)?.good == nil)
        #expect(TrendsFormat.health(6.33, .sleep) == "6 h 20")
    }

    @Test func rangeLimitsTheChart() {
        let trend = TrendsFormat.trend(.hrv, points(Array(repeating: 50, count: 90)), days: 30)
        #expect(trend.days.count == 30)
    }
}
