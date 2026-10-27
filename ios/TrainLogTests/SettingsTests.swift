import Foundation
import Testing
@testable import TrainLog

struct SettingsTests {
    @Test func bareHostGetsSchemeAndPort() {
        #expect(ServerAddress.normalize("192.168.1.24") == "http://192.168.1.24:8000")
        #expect(ServerAddress.normalize("  MacBook-Pro-Jakub.local/ ") == "http://MacBook-Pro-Jakub.local:8000")
        #expect(ServerAddress.normalize("mac.local:9000") == "http://mac.local:9000")
    }

    @Test func explicitSchemeKeepsItsPort() {
        #expect(ServerAddress.normalize("https://mac.tail1234.ts.net") == "https://mac.tail1234.ts.net")
        #expect(ServerAddress.normalize("HTTP://10.0.0.5:8000") == "http://10.0.0.5:8000")
    }

    @Test func rejectsUnusableAddresses() {
        #expect(ServerAddress.normalize("") == nil)
        #expect(ServerAddress.normalize("my mac") == nil)
        #expect(ServerAddress.normalize("ftp://mac.local") == nil)
        #expect(ServerAddress.normalize("mac.local:8000/api") == nil)
    }

    @Test func displayNames() {
        #expect(ServerAddress.displayName("http://localhost:8000") == "TrainLog on this Mac")
        #expect(ServerAddress.displayName("http://MacBook-Pro-Jakub.local:8000") == "TrainLog on MacBook Pro Jakub")
        #expect(ServerAddress.displayName("https://mac.tail1234.ts.net") == "TrainLog over Tailscale")
        #expect(ServerAddress.displayName("http://192.168.1.24:8000") == "TrainLog server")
    }

    @Test func computerNameToLocalHost() {
        #expect(ServerAddress.localHost(forComputerName: "MacBook Pro Jakub") == "MacBook-Pro-Jakub.local")
        #expect(ServerAddress.localHost(forComputerName: "Jakub’s MacBook Pro") == "Jakubs-MacBook-Pro.local")
        #expect(ServerAddress.localHost(forComputerName: "’") == nil)
    }

    @Test func dinnerNudgesSkipPastAndMetDays() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = .current
        let morning = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 27, hour: 9)))
        let all = Reminders.dinnerDates(from: morning, skipping: nil, calendar: calendar)
        #expect(all.count == 7)
        #expect(calendar.component(.hour, from: all[0]) == 20)
        #expect(calendar.component(.minute, from: all[0]) == 30)

        #expect(Reminders.dinnerDates(from: morning, skipping: "2026-10-27", calendar: calendar).count == 6)

        let late = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 27, hour: 21)))
        let afterDinner = Reminders.dinnerDates(from: late, skipping: nil, calendar: calendar)
        #expect(afterDinner.count == 6)
        #expect(FoodFormat.iso(afterDinner[0]) == "2026-10-28")
    }
}
