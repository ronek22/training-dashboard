import Foundation
import Testing
@testable import TrainLog

struct WidgetTests {
    @Test func formatsWeekHoursLikeTheArtboard() {
        #expect(WidgetFormat.clock(167) == "2:47")
        #expect(WidgetFormat.clock(5) == "0:05")
        #expect(WidgetFormat.hours(370) == "6h10")
        #expect(WidgetFormat.hours(360) == "6h")
        #expect(WidgetFormat.share(167, of: 370) > 0.45)
        #expect(WidgetFormat.share(400, of: 370) == 1)
        #expect(WidgetFormat.share(10, of: 0) == 0)
    }

    @Test func foodCountsDownToTheTarget() {
        let food = WidgetSnapshot.Food(date: "2026-10-28", eatenKcal: 1862, targetKcal: 2780, proteinG: 96, proteinTargetG: 140)
        #expect(food.kcalToGo == 918)
        #expect(abs(food.share - 0.67) < 0.01)
        let over = WidgetSnapshot.Food(date: "2026-10-28", eatenKcal: 3000, targetKcal: 2780, proteinG: 96, proteinTargetG: nil)
        #expect(over.kcalToGo == 0)
        #expect(over.share == 1)
    }

    @Test func yesterdaysSnapshotDoesNotCountToday() throws {
        let food = WidgetSnapshot.Food(date: "2026-10-27", eatenKcal: 1000, targetKcal: 2000, proteinG: 50, proteinTargetG: 140)
        let snapshot = WidgetSnapshot(food: food)
        let calendar = Calendar(identifier: .gregorian)
        let today = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 28, hour: 9)))
        let yesterday = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 27, hour: 21)))
        #expect(snapshot.food(on: today) == nil)
        #expect(snapshot.food(on: yesterday) == food)
    }

    @Test func buildsTodayFromPhoneToday() throws {
        let json = """
        {"date": "2026-10-28", "streak_days": 4,
         "readiness": {"level": "green", "label": "Good", "advice": null, "suggests_swap": false},
         "vitals": {"resting_hr": 52, "sleep_h": 7.2, "pain": null}, "checkin_done": true, "sick": null,
         "today": {"title": "Workout B", "session_type": "strength", "duration_min": 45, "status": "planned", "sport": "strength",
                   "strength": {"template_id": 2, "exercises": [{"name": "Squat", "sets": 3}, {"name": "RDL", "sets": 3}]}},
         "tomorrow": {"title": "Easy run", "sport": "run", "duration_min": 40},
         "week": [{"date": "2026-10-27", "label": "Mon", "title": "Workout A", "sport": "strength", "status": "done", "done_sports": ["strength"]}],
         "week_minutes": {"done": 167, "planned": 370, "by_sport": [{"sport": "strength", "minutes": 98}]}}
        """
        let phone = try APIClient.decoder.decode(PhoneToday.self, from: Data(json.utf8))
        let today = WidgetSnapshot.Today(phone)
        #expect(today.title == "Workout B")
        #expect(today.sport == "strength")
        #expect(!today.isDone)
        #expect(today.weekDoneMin == 167 && today.weekPlannedMin == 370)
        #expect(today.weekBySport == [.init(sport: "strength", minutes: 98)])
        #expect(today.liftCount == 2)
        #expect(today.tomorrow == .init(sport: "run", durationMin: 40))
        #expect(today.week == [.init(sport: "strength", status: "done", doneSports: ["strength"])])
    }

    @Test func shortensLongPlanTitlesForTheWidget() {
        let title = "Workout C · Wide Shoulders (extra upper volume)"
        #expect(WidgetFormat.shortTitle(title) == "Workout C")
        #expect(WidgetFormat.focus(title) == "Wide Shoulders")
        #expect(WidgetFormat.shortTitle("Recovery spin (knee-gated) + rehab") == "Recovery spin + rehab")
        #expect(WidgetFormat.focus("Recovery spin (knee-gated) + rehab") == nil)
    }

    @Test func kickerLeadsWithTheSportThenTheFocus() {
        func today(_ title: String?, sport: String, intent: String? = nil, sickDay: Int? = nil) -> WidgetSnapshot.Today {
            WidgetSnapshot.Today(
                date: "2026-10-30", title: title, sport: sport, durationMin: 45, isDone: false, readiness: "green",
                streakDays: 3, weekDoneMin: 0, weekPlannedMin: 0, weekBySport: [], intent: intent, sickDay: sickDay
            )
        }
        #expect(today("Workout C · Wide Shoulders (extra upper volume)", sport: "strength").kicker == "Strength · Wide Shoulders")
        #expect(today("Recovery spin", sport: "ride", intent: "Easy aerobic").kicker == "Ride · Easy aerobic")
        #expect(today("Rest", sport: "rest").kicker == "Recovery")
        #expect(today("Workout A", sport: "strength", sickDay: 2).kicker == "Sick · day 2")
    }

    @Test func kcalTurnsAmberOnlyOnABehindEvening() throws {
        let calendar = Calendar(identifier: .gregorian)
        let morning = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 30, hour: 9)))
        let evening = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 30, hour: 19)))
        let low = WidgetSnapshot.Food(date: "2026-10-30", eatenKcal: 1300, targetKcal: 2780, proteinG: 58, proteinTargetG: 140)
        let fine = WidgetSnapshot.Food(date: "2026-10-30", eatenKcal: 1862, targetKcal: 2780, proteinG: 96, proteinTargetG: 140)
        #expect(!WidgetFormat.isBehind(low, at: morning, calendar: calendar))
        #expect(WidgetFormat.isBehind(low, at: evening, calendar: calendar))
        #expect(!WidgetFormat.isBehind(fine, at: evening, calendar: calendar))
    }

    @Test func oldStoredSnapshotStillDecodes() throws {
        let json = """
        {"today": {"date": "2026-10-30", "title": "Workout B", "sport": "strength", "durationMin": 45, "isDone": false,
         "readiness": "green", "streakDays": 6, "weekDoneMin": 167, "weekPlannedMin": 370, "weekBySport": []}}
        """
        let snapshot = try JSONDecoder().decode(WidgetSnapshot.self, from: Data(json.utf8))
        #expect(snapshot.today?.week == nil)
        #expect(snapshot.today?.kicker == "Strength")
    }

    @Test func extensionAsksTheLastAnsweringAddressFirst() {
        var snapshot = WidgetSnapshot(baseURL: "https://mac.ts.net", fallbackURL: "http://mac.local:8000")
        #expect(snapshot.addresses == ["https://mac.ts.net", "http://mac.local:8000"])
        snapshot.fallbackURL = "https://mac.ts.net"
        #expect(snapshot.addresses == ["https://mac.ts.net"])
        #expect(WidgetSnapshot().addresses.isEmpty)
    }

    @Test @MainActor func appStoresBothServerAddresses() {
        let defaults = UserDefaults(suiteName: "widget-\(UUID().uuidString)")!
        let route = ServerRoute(defaults: defaults, ping: { _ in 5 })
        route.setHome("http://mac.local:8000")
        route.setRemote("https://mac.ts.net")
        var snapshot = WidgetSnapshot()
        snapshot.setAddresses(route)
        #expect(snapshot.addresses == ["http://mac.local:8000", "https://mac.ts.net"])
        route.use("https://mac.ts.net")
        snapshot.setAddresses(route)
        #expect(snapshot.addresses == ["https://mac.ts.net", "http://mac.local:8000"])
        route.setRemote(nil)
        snapshot.setAddresses(route)
        #expect(snapshot.addresses == ["http://mac.local:8000"])
    }
}
