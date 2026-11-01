import Foundation
import Testing
@testable import TrainLog

struct WatchGlanceTests {
    private let calendar = Calendar(identifier: .gregorian)

    private func at(_ hour: Int) -> Date {
        calendar.date(from: DateComponents(year: 2026, month: 11, day: 1, hour: hour))!
    }

    private func today(sport: String = "strength", title: String? = "Workout B", done: Bool = false,
                       sickDay: Int? = nil, rehab: WidgetSnapshot.Rehab? = nil) -> WidgetSnapshot.Today {
        var today = WidgetSnapshot.Today(
            date: "2026-11-01", title: title, sport: sport, durationMin: 45, isDone: done, readiness: "green",
            streakDays: 3, weekDoneMin: 167, weekPlannedMin: 370, weekBySport: [], sickDay: sickDay
        )
        today.rehab = rehab
        return today
    }

    @Test func todayLeadsUntilTheSessionIsDone() {
        let planned = WidgetSnapshot(today: today())
        #expect(WatchGlance.relevance(.today, planned, at: at(7), calendar: calendar) == 80)
        #expect(WatchGlance.relevance(.week, planned, at: at(7), calendar: calendar) < 80)
        let done = WidgetSnapshot(today: today(done: true))
        #expect(WatchGlance.state(done.today) == .done)
        #expect(WatchGlance.relevance(.today, done, at: at(10), calendar: calendar) > WatchGlance.relevance(.week, done, at: at(10), calendar: calendar))
    }

    @Test func unfinishedRehabRisesAboveTodayInTheEvening() {
        let snapshot = WidgetSnapshot(today: today(rehab: .init(title: "Left knee", done: 3, total: 6, durationMin: 4)))
        #expect(WatchGlance.relevance(.rehab, snapshot, at: at(9), calendar: calendar) < WatchGlance.relevance(.today, snapshot, at: at(9), calendar: calendar))
        #expect(WatchGlance.relevance(.rehab, snapshot, at: at(19), calendar: calendar) > WatchGlance.relevance(.today, snapshot, at: at(19), calendar: calendar))
        let ticked = WidgetSnapshot(today: today(rehab: .init(title: "Left knee", done: 6, total: 6, durationMin: 0)))
        #expect(WatchGlance.relevance(.rehab, ticked, at: at(19), calendar: calendar) == 5)
        #expect(WatchGlance.rehabLine(.init(title: "Left knee", done: 3, total: 6, durationMin: 4)) == "3 left · ~4 min")
        #expect(WatchGlance.rehabLine(.init(title: "Left knee", done: 6, total: 6, durationMin: 0)) == "All done")
    }

    @Test func foodRisesInTheEveningWhenBehind() {
        let food = WidgetSnapshot.Food(date: "2026-11-01", eatenKcal: 1200, targetKcal: 2780, proteinG: 60, proteinTargetG: 140)
        let snapshot = WidgetSnapshot(today: today(), food: food)
        #expect(WatchGlance.relevance(.food, snapshot, at: at(12), calendar: calendar) == 20)
        #expect(WatchGlance.relevance(.food, snapshot, at: at(19), calendar: calendar) == 85)
        #expect(WatchGlance.relevance(.food, snapshot, at: at(19), calendar: calendar) > WatchGlance.relevance(.today, snapshot, at: at(19), calendar: calendar))
    }

    @Test func restAndSickDaysShowTomorrowOrTheDayCount() {
        var rest = today(sport: "rest", title: nil)
        #expect(WatchGlance.state(rest) == .rest)
        #expect(WatchGlance.inline(rest) == "Rest day")
        rest.tomorrow = .init(sport: "ride", durationMin: 75)
        #expect(WatchGlance.inline(rest) == "Rest · tmrw Ride")
        let sick = today(sickDay: 2)
        #expect(WatchGlance.state(sick) == .sick)
        #expect(WatchGlance.inline(sick) == "Sick · day 2")
        #expect(WatchGlance.inline(today()) == "Workout B · 45 min")
        #expect(WatchGlance.inline(nil) == "TrainLog")
    }

    @Test func strengthDetailNamesTheFirstLift() {
        var strength = today()
        strength.liftCount = 5
        strength.firstLift = "Row 34 kg × 10"
        #expect(WatchGlance.detail(strength) == "5 exercises · Row 34 kg × 10")
        #expect(WatchGlance.week(strength) == "2:47 / 6:10")
        let lift = PhoneToday.Exercise(name: "Dumbbell Row", sets: 3, reps: 10, weightKg: 34, restSeconds: nil, notes: nil, seconds: nil)
        #expect(WidgetFormat.lift(lift) == "Row 34 kg × 10")
        let plank = PhoneToday.Exercise(name: "Plank", sets: 3, reps: nil, weightKg: nil, restSeconds: nil, notes: nil, seconds: 30)
        #expect(WidgetFormat.lift(plank) == "Plank 3 × 30 s")
    }

    @Test func timelineStepsAtSixAndMidnight() {
        let morning = WatchGlance.timeline(from: at(9), calendar: calendar)
        #expect(morning.count == 3)
        #expect(calendar.component(.hour, from: morning[1]) == 18)
        #expect(WatchGlance.timeline(from: at(20), calendar: calendar).count == 2)
    }

    @Test func phoneTodayCarriesRehabTicks() throws {
        let json = """
        {"date": "2026-11-01", "streak_days": 4,
         "readiness": {"level": "green", "label": "Good", "advice": null, "suggests_swap": false},
         "vitals": {"resting_hr": 52, "sleep_h": 7.2, "pain": null}, "checkin_done": true, "sick": null,
         "today": null, "tomorrow": null, "week": [],
         "rehab": {"title": "Left knee", "done": 2, "total": 6, "duration_min": 5},
         "week_minutes": {"done": 0, "planned": 0, "by_sport": []}}
        """
        let phone = try APIClient.decoder.decode(PhoneToday.self, from: Data(json.utf8))
        #expect(WidgetSnapshot.Today(phone).rehab == .init(title: "Left knee", done: 2, total: 6, durationMin: 5))
    }
}
