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
         "today": {"title": "Workout B", "session_type": "strength", "duration_min": 45, "status": "planned", "sport": "strength"},
         "tomorrow": null, "week": [],
         "week_minutes": {"done": 167, "planned": 370, "by_sport": [{"sport": "strength", "minutes": 98}]}}
        """
        let phone = try APIClient.decoder.decode(PhoneToday.self, from: Data(json.utf8))
        let today = WidgetSnapshot.Today(phone)
        #expect(today.title == "Workout B")
        #expect(today.sport == "strength")
        #expect(!today.isDone)
        #expect(today.weekDoneMin == 167 && today.weekPlannedMin == 370)
        #expect(today.weekBySport == [.init(sport: "strength", minutes: 98)])
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
