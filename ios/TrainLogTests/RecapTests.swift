import Foundation
import Testing
@testable import TrainLog

struct RecapTests {
    /// A mountain week, trimmed from the real `/reviews/weekly/report`.
    private let report = """
    {"week_start": "2026-10-19", "week_end": "2026-10-25", "through": "2026-10-25", "finished": true, "day_of_week": 7,
     "previous_week": "2026-10-12", "next_week": "2026-10-26",
     "totals": {"minutes": 45, "movement_minutes": 1577, "sessions": 1, "active_days": 7, "distance_km": 0, "elevation_m": 3746, "load": 458,
       "by_sport": {"cycling": {"minutes": 0, "sessions": 0}, "strength": {"minutes": 45, "sessions": 1}, "walking": {"minutes": 1532, "sessions": 7}}},
     "norm": {"weeks": 4, "minutes": 335.8, "minutes_to_date": 335.8, "sessions": 6.2},
     "fitness": {"start": 47, "end": 50, "form": -2}, "plan": null,
     "goals": [{"id": 4, "title": "Lift three times per week", "metric": "strength_sessions", "done": 1.0, "target": 3.0, "anchor": true, "met": false}],
     "recovery": {"sleep": {"value": 7.5, "baseline": 6.7, "days": 6}, "hrv": {"value": 60.9, "baseline": 46.6, "days": 7},
       "resting_hr": {"value": 63.3, "baseline": 70.8, "days": 7}, "steps": {"value": 7700, "baseline": 7635, "days": 7}},
     "sick_days": 0, "longest_gap": 6,
     "days": [
       {"date": "2026-10-23", "future": false, "today": false, "planned": [], "activities": [
         {"id": "1", "date": "2026-10-23", "type": "Hike", "sport": "walking", "name": "Morning Hike", "duration_min": 172, "distance_km": 9.9, "elevation_m": 484},
         {"id": "2", "date": "2026-10-23", "type": "WeightTraining", "sport": "strength", "name": "Lift", "duration_min": 45, "distance_km": null, "elevation_m": 0},
         {"id": "3", "date": "2026-10-23", "type": "Walk", "sport": "walking", "name": "Evening Walk", "duration_min": 30, "distance_km": 2.1, "elevation_m": 10}],
        "load": 58, "sick": false, "tags": ["Mountains"]}],
     "history": [{"week_start": "2026-10-12", "current": false, "minutes": 392, "load": 282, "sessions": 7},
                 {"week_start": "2026-10-19", "current": true, "minutes": 45, "load": 458, "sessions": 1}],
     "sport_labels": {}, "fuelling": {"ready": false}, "insights": []}
    """

    private func decoded() throws -> WeekReport {
        try APIClient.decoder.decode(WeekReport.self, from: Data(report.utf8))
    }

    @Test func decodesReport() throws {
        let week = try decoded()
        #expect(week.finished)
        #expect(week.nextWeek == "2026-10-26")
        #expect(week.plan == nil)
        #expect(week.goals.first?.anchor == true)
        #expect(week.days.first?.tags == ["Mountains"])
        #expect(week.history.last?.current == true)
    }

    @Test func decodesWins() throws {
        let json = """
        {"week_start": "2026-10-26", "finished": false, "sessions": 5, "minutes": 262,
         "wins": [{"kind": "consistency", "headline": "300 days in a row", "detail": "A streak milestone.", "activity_id": "1", "date": "2026-10-29"}],
         "focus": {"source": "goal", "headline": "Lift three times per week: 1 to go", "detail": "Pick the day now."}}
        """
        let wins = try APIClient.decoder.decode(WeekWins.self, from: Data(json.utf8))
        #expect(wins.wins.first?.headline == "300 days in a row")
        #expect(RecapFormat.winSymbol(wins.wins[0].kind) == "flame.fill")
        #expect(wins.focus?.headline.hasSuffix("1 to go") == true)
    }

    @Test func mountainWeekCountsWalksAndHikes() throws {
        let week = try decoded()
        #expect(RecapFormat.movedMinutes(week.totals) == 1577)
        #expect(RecapFormat.activityCount(week) == 3)
        #expect(abs(RecapFormat.distanceKm(week) - 12.0) < 0.001)
        let shares = RecapFormat.shares(week.totals)
        #expect(shares.map(\.label) == ["Walks & hikes", "Strength"])
        #expect(shares.first?.sport == .walk)
        // Training fell short of a usual week, so no "+%" pill.
        #expect(RecapFormat.versusUsual(week) == -87)
    }

    @Test func daySegmentsMergeBySport() throws {
        let segments = RecapFormat.daySegments(try decoded().days[0])
        #expect(segments.map(\.sport) == [.walk, .strength])
        #expect(segments.map(\.minutes) == [202, 45])
    }

    @Test func vitalsJudgedAgainstBaseline() throws {
        let vitals = RecapFormat.vitals(try decoded().recovery)
        #expect(vitals.map(\.title) == ["Sleep", "HRV", "Resting HR", "Steps"])
        #expect(vitals[0].mood == .better)
        #expect(vitals[1].change == "+31% vs usual")
        // Lower resting HR is better.
        #expect(vitals[2].mood == .better)
        #expect(vitals[2].change == "−11% vs usual")
        #expect(vitals[3].mood == .steady)
    }

    @Test func todayOffersRecapOnSundayAndMonday() {
        #expect(RecapFormat.offer(today: "2026-11-01")?.weekStart == "2026-10-26")
        #expect(RecapFormat.offer(today: "2026-11-02")?.weekStart == "2026-10-26")
        #expect(RecapFormat.offer(today: "2026-11-02")?.label == "Last week in review")
        #expect(RecapFormat.offer(today: "2026-10-29") == nil)
    }

    @Test func labels() {
        #expect(RecapFormat.range("2026-10-19", "2026-10-25") == "19–25 OCT")
        #expect(RecapFormat.range("2026-09-28", "2026-10-04") == "28 SEP – 4 OCT")
        #expect(RecapFormat.weekEnd("2026-10-26") == "2026-11-01")
        #expect(RecapFormat.weekNumber("2026-10-19") == 43)
        #expect(RecapFormat.number(34.1) == "34.1")
        #expect(RecapFormat.number(3) == "3")
    }

    @Test func paths() {
        #expect(WeekRecapModel.reportPath(nil, day: "2026-11-01") == "/reviews/weekly/report?day=2026-11-01")
        #expect(WeekRecapModel.winsPath("2026-10-19", day: "2026-11-01") == "/reviews/weekly/wins?week_start=2026-10-19&day=2026-11-01")
    }

    @Test func sundayNudgeOnlyOnSunday() throws {
        let enabled = Reminders.Enabled(recap: true)
        let now = try #require(Calendar.current.date(from: DateComponents(year: 2026, month: 10, day: 29, hour: 9)))
        let nudges = Reminders.plan(enabled, today: nil, now: now)
        #expect(nudges.count == 1)
        let recap = try #require(nudges.first)
        #expect(recap.kind == .recap)
        #expect(recap.day == "2026-11-01")
        #expect(Calendar.current.component(.hour, from: recap.date) == 19)
        #expect(recap.kind.link == "trainlog://recap")
    }
}
