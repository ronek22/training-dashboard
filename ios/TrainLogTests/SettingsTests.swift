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

    private func date(_ day: Int, _ hour: Int, _ minute: Int = 0) throws -> Date {
        try #require(Calendar.current.date(from: DateComponents(year: 2026, month: 10, day: day, hour: hour, minute: minute)))
    }

    private let all = Reminders.Enabled(morning: 7 * 60 + 30, rehab: true, dinner: true)

    @Test func nudgesBookAWeekAheadWithoutTodaysState() throws {
        let nudges = Reminders.plan(all, today: nil, now: try date(27, 6))
        #expect(nudges.filter { $0.kind == .checkin }.count == 7)
        #expect(nudges.filter { $0.kind == .dinner }.count == 7)
        // Rehab only once the server says exercises are open today.
        #expect(nudges.filter { $0.kind == .rehab }.isEmpty)
        let dinner = try #require(nudges.first { $0.kind == .dinner })
        #expect(Calendar.current.component(.hour, from: dinner.date) == 20)
        #expect(Calendar.current.component(.minute, from: dinner.date) == 30)
        #expect(dinner.id == "nudge.dinner.2026-10-27")
    }

    @Test func nudgesSkipTimesAlreadyPast() throws {
        let nudges = Reminders.plan(all, today: nil, now: try date(27, 21))
        #expect(nudges.filter { $0.kind == .dinner }.count == 6)
        #expect(nudges.first { $0.kind == .dinner }?.day == "2026-10-28")
    }

    @Test func doneThingsStayQuietToday() throws {
        let today = Reminders.Today(date: "2026-10-27", checkinDone: true, rehabLeft: 0, eatenKcal: 2450, targetKcal: 2600)
        let nudges = Reminders.plan(all, today: today, now: try date(27, 6))
        #expect(!nudges.contains { $0.day == "2026-10-27" })
        // Tomorrow is still booked.
        #expect(nudges.contains { $0.kind == .checkin && $0.day == "2026-10-28" })
        #expect(nudges.contains { $0.kind == .dinner && $0.day == "2026-10-28" })
    }

    @Test func openThingsNudgeWithNumbers() throws {
        let today = Reminders.Today(date: "2026-10-27", checkinDone: false, rehabLeft: 3, eatenKcal: 1240, targetKcal: 2600)
        let nudges = Reminders.plan(all, today: today, now: try date(27, 12))
        let rehab = try #require(nudges.first { $0.kind == .rehab })
        #expect(rehab.body.hasPrefix("3 exercises left"))
        #expect(Calendar.current.component(.hour, from: rehab.date) == 19)
        let dinner = try #require(nudges.first { $0.kind == .dinner && $0.day == "2026-10-27" })
        #expect(dinner.body.hasPrefix("1240 of 2600 kcal so far, 1360 to go"))
        #expect(dinner.body.contains("to go"))
    }

    @Test func yesterdaysStateIsIgnored() throws {
        let stale = Reminders.Today(date: "2026-10-26", checkinDone: true, rehabLeft: 2)
        let nudges = Reminders.plan(all, today: stale, now: try date(27, 6))
        #expect(nudges.contains { $0.kind == .checkin && $0.day == "2026-10-27" })
        #expect(!nudges.contains { $0.kind == .rehab })
    }

    @Test func offSettingsBookNothing() throws {
        #expect(Reminders.plan(.init(), today: nil, now: try date(27, 6)).isEmpty)
    }

    @Test func phoneProgressSurvivesAStaleServer() {
        let phone = Reminders.Today(date: "2026-10-27", checkinDone: true, rehabLeft: 0, eatenKcal: 2000, targetKcal: 2600)
        let server = Reminders.Today(date: "2026-10-27", checkinDone: false, rehabLeft: 4, eatenKcal: 1500, targetKcal: 2700)
        let merged = phone.merged(with: server)
        #expect(merged.checkinDone == true)
        #expect(merged.rehabLeft == 0)
        #expect(merged.eatenKcal == 2000)
        #expect(merged.targetKcal == 2700)
        // Unknown server fields keep what the phone knows; a new day starts over.
        #expect(phone.merged(with: .init(date: "2026-10-27")) == phone)
        #expect(phone.merged(with: .init(date: "2026-10-28")) == .init(date: "2026-10-28"))
    }

    @Test func refreshRunsLateAfternoon() throws {
        let before = try #require(Reminders.nextRefresh(after: try date(27, 9)))
        #expect(before == (try date(27, 17, 30)))
        let after = try #require(Reminders.nextRefresh(after: try date(27, 18)))
        #expect(after == (try date(28, 17, 30)))
    }
}
