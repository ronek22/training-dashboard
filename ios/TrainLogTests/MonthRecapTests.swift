import Foundation
import Testing
@testable import TrainLog

struct MonthRecapTests {
    /// October 2026, trimmed from the real `/reviews/monthly/report`.
    private let report = """
    {"month": "2026-10", "label": "October 2026", "start_date": "2026-10-01", "end_date": "2026-10-31", "finished": true,
     "previous_month": "2026-09", "next_month": "2026-11",
     "totals": {"sessions": 30, "minutes": 2665, "active_days": 31, "days": 31, "movement_minutes": 2888, "elapsed_days": 31},
     "prior_average": {"months": 3, "sessions": 35.7, "minutes": 2460.7, "active_days": 30.7, "minutes_to_date": 2460.7},
     "streak_days": 302, "plan": {"planned": 24, "done": 23},
     "days": [{"date": "2026-10-01", "minutes": 10, "sport": "mobility", "sick": true, "record": false, "future": false},
              {"date": "2026-10-08", "minutes": 65, "sport": "strength", "sick": false, "record": true, "future": false},
              {"date": "2026-10-20", "minutes": 514, "sport": "hiking", "sick": false, "record": false, "future": false}],
     "records": [{"date": "2026-10-08", "name": "Lift Incline Dumbbell Curl", "display": "19.6 kg", "previous": "16.8 kg"}],
     "weight": {"weigh_ins": [{"date": "2026-10-12", "kg": 79.0, "avg_kg": 79.0}, {"date": "2026-10-30", "kg": 79.0, "avg_kg": 79.83}],
                "lane_pct_per_week": [0.1, 0.35], "available": true, "status": "fast_gain", "start_kg": 79.0, "end_kg": 79.83,
                "change_kg": 0.83, "kg_per_week": 0.32, "pct_per_week": 0.41, "lane_kg_per_week": [0.08, 0.28]},
     "strength": {"up": 9, "held": 3, "down": 4,
       "top": [{"name": "Dumbbell Lateral Raise", "e1rm_kg": 26.7, "previous_kg": 20.0, "change_kg": 6.7, "trend": "up", "sets": 31}],
       "dropped": [{"name": "Barbell Incline Bench Press", "e1rm_kg": 79.2, "previous_kg": 88.7, "change_kg": -9.5, "trend": "down", "sets": 8},
                   {"name": "Bent Over Barbell Row", "e1rm_kg": 104.5, "previous_kg": 106.7, "change_kg": -2.2, "trend": "down", "sets": 8}],
       "lift_days": 12, "weeks": [{"week_start": "2026-09-28", "week_number": 40, "days": 2, "sick": true}], "per_week_target": 3},
     "rides": {"rides": 9, "minutes": 522, "by_intensity": {"recovery": 281, "z2": 171, "sweet_spot": 70, "vo2": 0},
               "previous_minutes": 1960, "previous_by_intensity": {"recovery": 392, "z2": 1514, "sweet_spot": 54, "vo2": 0}, "hiking_minutes": 1482},
     "run": {"vdot": 38.2, "basis": "heart_rate", "peak": 55.1, "share_of_peak_pct": 69, "projected": 41.2, "runs": 0, "km": 0.0,
             "previous_vdot": 38.2, "last_estimate_date": "2026-09-09"},
     "wins": [{"kind": "streak", "headline": "First 300-day streak", "detail": "Reached on 29 Oct."}],
     "focus": {"source": "goal", "headline": "Protect Lift three times per week", "detail": "Kept in 2 of 3 full weeks."}}
    """

    private func decoded() throws -> MonthReport {
        try APIClient.decoder.decode(MonthReport.self, from: Data(report.utf8))
    }

    @Test func decodesReport() throws {
        let month = try decoded()
        #expect(month.finished)
        #expect(month.totals.minutes == 2665)
        #expect(month.days[1].record)
        #expect(month.days[0].sick)
        #expect(month.strength?.top.first?.e1rmKg == 26.7)
        #expect(month.rides?.byIntensity["recovery"] == 281)
        #expect(month.run?.lastEstimateDate == "2026-09-09")
        #expect(month.wins.first?.kind == "streak")
        #expect(RecapFormat.winSymbol("streak") == "flame.fill")
        #expect(month.focus?.headline.hasPrefix("Protect") == true)
    }

    @Test func decodesMonthInProgressWithoutLetter() throws {
        let json = """
        {"month": "2026-11", "label": "November 2026", "start_date": "2026-11-01", "end_date": "2026-11-30", "finished": false,
         "previous_month": "2026-10", "next_month": null, "totals": {"sessions": 4, "minutes": 111, "active_days": 4, "days": 30, "elapsed_days": 5},
         "prior_average": null, "streak_days": 306, "plan": null, "days": [{"date": "2026-11-06", "minutes": 0, "sport": null, "future": true}],
         "records": [], "weight": {"weigh_ins": [], "lane_pct_per_week": [0.1, 0.35], "available": false, "needed": 3},
         "strength": null, "rides": null, "run": null, "wins": [], "focus": null}
        """
        let month = try APIClient.decoder.decode(MonthReport.self, from: Data(json.utf8))
        #expect(!month.finished)
        #expect(month.nextMonth == nil)
        #expect(month.days.first?.future == true)
        #expect(month.weight?.available == false)
        #expect(MonthRecapFormat.versusUsual(month) == nil)
        #expect(MonthRecapFormat.verdicts(month).isEmpty)
    }

    @Test func todayOffersLastMonthOnTheFirstSevenDays() {
        #expect(MonthRecapFormat.offer(today: "2026-11-01")?.month == "2026-10")
        #expect(MonthRecapFormat.offer(today: "2026-11-07")?.label == "October in review")
        #expect(MonthRecapFormat.offer(today: "2026-11-08") == nil)
        #expect(MonthRecapFormat.offer(today: "2027-01-03")?.month == "2026-12")
        #expect(MonthRecapFormat.offerRange("2026-10") == "1–31 OCT")
        #expect(MonthRecapFormat.offerRange("2028-02") == "1–29 FEB")
    }

    @Test func aWeekBelongsToTheMonthOfItsThursday() {
        #expect(MonthRecapFormat.month(ofWeek: "2026-09-28") == "2026-10")  // Thursday 1 Oct
        #expect(MonthRecapFormat.month(ofWeek: "2026-10-26") == "2026-10")  // Thursday 29 Oct
        #expect(MonthRecapFormat.month(ofWeek: "2026-11-30") == "2026-12")
    }

    @Test func calendarStartsOnMonday() throws {
        let month = try decoded()
        #expect(MonthRecapFormat.leadingBlanks(month) == 3)  // 1 Oct 2026 is a Thursday
        #expect(MonthRecapFormat.sport("hiking") == .hike)
        #expect(MonthRecapFormat.sport("walking") == .mobility)
        #expect(MonthRecapFormat.sport(nil) == nil)
        #expect(MonthRecapFormat.intensity(10) < MonthRecapFormat.intensity(45))
        #expect(MonthRecapFormat.intensity(90) == 1)
        #expect(MonthRecapFormat.range(month) == "1–31 OCT")
    }

    @Test func trainingIsComparedWithTheUsualMonth() throws {
        let versus = try #require(MonthRecapFormat.versusUsual(try decoded()))
        #expect(versus.pct == 8)
    }

    @Test func verdictsAreWordsNotNumbers() throws {
        let verdicts = MonthRecapFormat.verdicts(try decoded())
        #expect(verdicts.map(\.word) == ["Gaining", "Stronger", "Lighter", "Paused"])
        #expect(verdicts.map(\.id) == ["body", "lifts", "base", "run"])
        #expect(verdicts[2].direction == .down)
    }

    @Test func fastGainIsNeverScolded() throws {
        let weight = try #require(try decoded().weight)
        let line = MonthRecapFormat.weightLine(weight)
        #expect(line.lead == "Gaining.")
        #expect(line.rest.contains("0.32 kg a week"))
        #expect(line.rest.contains("Keep eating"))
    }

    @Test func liftNamesAreShortened() {
        #expect(MonthRecapFormat.liftName("Standing Dumbbell Shoulder Press") == "Shoulder press")
        #expect(MonthRecapFormat.liftName("Bent Over Barbell Row") == "Barbell row")
        #expect(MonthRecapFormat.liftName("Dumbbell Rear Delt Raise") == "Rear delt raise")
        #expect(MonthRecapFormat.liftName("Romanian Deadlift") == "Romanian deadlift")
        let dropped = try? decoded().strength?.dropped ?? []
        #expect(MonthRecapFormat.droppedLine(dropped ?? []) == "Incline bench press −9.5, Barbell row −2.2 kg")
    }

    @Test func runLineSaysWhenThereWereNoRuns() throws {
        let run = try #require(try decoded().run)
        #expect(MonthRecapFormat.runLine(run, month: "October")
                == "No runs in October. Last estimate 9 Sep. One easy run a week brings it back toward 41.")
        var running = run
        running.runs = 6
        running.km = 31
        #expect(MonthRecapFormat.runLine(running, month: "November") == "6 runs, 31 km in November.")
        #expect(MonthRecapFormat.vdotChange(run) == nil)
    }

    @Test func pathCarriesThePhonesDate() {
        #expect(MonthRecapModel.path("2026-10", day: "2026-11-05") == "/reviews/monthly/report?month=2026-10&day=2026-11-05")
        #expect(MonthRecapModel.path(nil, day: "2026-11-05") == "/reviews/monthly/report?day=2026-11-05")
    }
}
