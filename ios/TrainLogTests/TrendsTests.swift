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

    @Test func averagesTheLastSevenDays() {
        let trend = TrendsFormat.trend(.hrv, points([40, 40, 40, 40, 40, 40, 40, 54]), days: 30)
        #expect(trend.average.count == 8)
        #expect(trend.average.first?.value == 40)
        #expect(trend.average.last?.value == 42)
    }

    // MARK: Weekly hours and the year card

    /// 12 weeks from 17 Aug; `totals` are ride hours, with one hiking week.
    private func weeks(_ totals: [Double], hike: Int? = nil) -> [TrendWeek] {
        let start = FoodFormat.parse("2026-08-17")!
        return totals.enumerated().map { index, hours in
            let day = Calendar(identifier: .gregorian).date(byAdding: .day, value: index * 7, to: start)!
            let isHike = index == hike
            return TrendWeek(
                start: FoodFormat.iso(day),
                hours: isHike ? ["other": hours, "strength": 0.75] : ["ride": hours, "strength": 1],
                sessions: isHike ? 6 : 3,
                top: isHike ? .init(type: "Hike", sessions: 5, share: 0.94) : .init(type: "Ride", sessions: 2, share: 0.5)
            )
        }
    }

    private let trendsJSON = """
    {"today": "2026-11-02",
     "weeks": [{"start": "2026-10-26", "hours": {"ride": 1.23, "strength": 3.8, "run": 0.0, "mobility": 1.49, "other": 0.0},
                "sessions": 9, "top": {"type": "WeightTraining", "sessions": 4, "share": 0.58}},
               {"start": "2026-11-02", "hours": {"ride": 0, "strength": 0, "run": 0, "mobility": 0, "other": 0}, "sessions": 0, "top": null}],
     "sports": [{"sport": "run", "unit": "km", "total": 258.1, "last_year_to_date": 355.5,
                 "last_year_months": [0, 0, 0, 41.8, 65.6, 53.2, 22.3, 2.0, 34.3, 123.1, 126.1, 51.1], "last_date": "2026-09-09"}]}
    """

    @Test func decodesTrends() throws {
        let decoded = try APIClient.decoder.decode(TrendsSummary.self, from: Data(trendsJSON.utf8))
        #expect(decoded.weeks[0].hours["mobility"] == 1.49)
        #expect(decoded.weeks[1].top == nil)
        #expect(decoded.sports[0].sport == .run)
        #expect(decoded.sports[0].lastYearToDate == 355.5)
        #expect(decoded.sports[0].lastYearMonths.count == 12)
    }

    @Test func typicalWeekIsTheMedianOfTheEightBeforeLast() {
        // Last week 5 h, this week empty; the 26 h trip week doesn't drag the median up.
        let volume = TrendsFormat.weekly(weeks([9, 10, 16, 11, 7, 6, 4, 8, 6, 26, 5, 0], hike: 9))
        #expect(volume.lastWeek?.total == 6)
        #expect(volume.thisWeek?.total == 1)
        // Weeks 3–10 (index 2…9) total 17, 12, 8, 7, 5, 9, 7, 26.75 → median 8.5.
        #expect(volume.typical == 8.5)
        #expect(volume.typicalByGroup[.strength] == 1)
        // The trip week is more than 1.4× the next, so the scale stops at 17 × 1.15.
        #expect(abs(volume.cap - 19.55) < 0.001)
    }

    @Test func noCapWithoutAnOutlier() {
        let volume = TrendsFormat.weekly(weeks([9, 10, 12, 11, 7, 6, 4, 8, 6, 9, 5, 0]))
        #expect(abs(volume.cap - 13 * 1.05) < 0.001)
    }

    @Test func namesADominantWeek() {
        let volume = TrendsFormat.weekly(weeks([9, 10, 16, 11, 7, 6, 4, 8, 6, 26, 5, 0], hike: 9))
        #expect(TrendsFormat.weekNote(volume.weeks[9]) == "Mostly hiking · 5 hikes")
        #expect(TrendsFormat.weekNote(volume.weeks[0]) == "3 sessions")
        #expect(TrendsFormat.weekRange(volume.weeks[9].start) == "19 – 25 Oct")
        #expect(TrendsFormat.hours(6.53) == "6h 32")
        #expect(TrendsFormat.hours(0.75) == "45 min")
    }

    @Test func headlineComparesTheLastFourWeeks() {
        let volume = TrendsFormat.weekly(weeks([9, 10, 16, 11, 7, 6, 4, 8, 6, 26, 5, 0], hike: 9))
        // Recent 4: 9, 7, 26.75, 6 → 8 h; before: 10, 11, 17, 12, 8, 7, 5 → 10 h.
        #expect(TrendsFormat.headline(volume) == "Last 4 weeks: about 8h 00 a week, down from 10h 00 before. Strength holding at about 1h 00.")
    }

    private func row(_ total: Double, lastYear: Double, sport: Sport = .ride, unit: String = "km", lastDate: String? = nil) -> SportYearRow {
        SportYearRow(toDate: SportToDate(sport: sport, unit: unit, total: total, lastYearToDate: lastYear,
                                         lastYearMonths: [], lastDate: lastDate), year: nil)
    }

    @Test func comparesWithLastYear() {
        #expect(TrendsFormat.comparison(row(5180.7, lastYear: 400.7), year: 2025)! == ("+4,780 km vs 2025", true))
        #expect(TrendsFormat.comparison(row(133.1, lastYear: 60.5, sport: .strength, unit: "h"), year: 2025)! == ("2.2× 2025", true))
        #expect(TrendsFormat.comparison(row(258.1, lastYear: 355.5, sport: .run), year: 2025)! == ("355.5 km by now in 2025", false))
        // Too little last year to mean anything.
        #expect(TrendsFormat.comparison(row(5000, lastYear: 100), year: 2025) == nil)
    }

    @Test func notesAQuietSport() {
        let today = FoodFormat.parse("2026-11-02")!
        #expect(TrendsFormat.idleNote(row(258.1, lastYear: 355.5, sport: .run, lastDate: "2026-09-09"), today: today) == "Last run 9 Sep")
        #expect(TrendsFormat.idleNote(row(5000, lastYear: 400, lastDate: "2026-10-29"), today: today) == nil)
    }

    @Test func footerShowsTheMonthJustFinishedEarlyInAMonth() throws {
        let decoded = try APIClient.decoder.decode(TrainingHistory.self, from: Data(history.utf8))
        var series = decoded.rideYearSeries
        series.append(YearMonth(month: "Apr", monthlyKm: 0, monthlyHours: 0, monthlySessions: 0, cumulativeKm: 1438.8, cumulativeHours: 48))
        #expect(TrendsFormat.year(.ride, series).shown?.name == "Mar")
        #expect(TrendsFormat.year(.ride, decoded.rideYearSeries).shown?.name == "Mar")
    }
}
