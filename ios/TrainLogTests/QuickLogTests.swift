import Foundation
import Testing
@testable import TrainLog

@MainActor
struct QuickLogTests {
    private let day = ISO8601DateFormatter().date(from: "2026-10-28T07:12:00Z")!

    private func model() -> QuickLogModel {
        QuickLogModel(today: day)
    }

    @Test func decodesTodayCheckin() throws {
        let json = """
        {"checkin": {"date": "2026-10-28", "energy": 4, "muscle_soreness": 2, "stress": 2,
                     "sleep_quality": 3, "pain_level": 1, "note": "Niggle: Knee", "updated_at": "x"}}
        """
        let response = try APIClient.decoder.decode(CheckinResponse.self, from: Data(json.utf8))
        #expect(response.checkin?.muscleSoreness == 2)
        #expect(response.checkin?.note == "Niggle: Knee")
        let empty = try APIClient.decoder.decode(CheckinResponse.self, from: Data(#"{"checkin": null}"#.utf8))
        #expect(empty.checkin == nil)
        let sick = try APIClient.decoder.decode(SickModeResponse.self, from: Data(#"{"sick_mode": {"active": false}}"#.utf8))
        #expect(sick.sickMode.active == false)
    }

    @Test func checkinNeedsTheThreeScales() {
        let log = model()
        #expect(log.checkinInput == nil)
        log.energy = 4
        log.sleep = 3
        log.stress = 2
        log.pain = 1
        log.toggleSore("Chest")
        let input = log.checkinInput
        #expect(input == CheckinInput(date: "2026-10-28", energy: 4, muscleSoreness: 2, stress: 2,
                                      sleepQuality: 3, painLevel: 1, note: nil))
    }

    @Test func encodesCheckinInSnakeCase() throws {
        let input = CheckinInput(date: "2026-10-28", energy: 4, muscleSoreness: 2, stress: 2, sleepQuality: 3, painLevel: 1, note: nil)
        let json = String(decoding: try APIClient.encoder.encode(input), as: UTF8.self)
        #expect(json.contains("\"muscle_soreness\":2"))
        #expect(json.contains("\"sleep_quality\":3"))
    }

    @Test func soreAreasMapToSoreness() {
        #expect(QuickLogFormat.soreness([]) == 1)
        #expect(QuickLogFormat.soreness(["None"]) == 1)
        #expect(QuickLogFormat.soreness(["Legs"]) == 2)
        #expect(QuickLogFormat.soreness(["Legs", "Back", "Chest", "Arms"]) == 4)
    }

    @Test func noneClearsTheOtherAreas() {
        let log = model()
        log.toggleSore("Legs")
        log.toggleSore("Back")
        log.toggleSore("None")
        #expect(log.soreAreas == ["None"])
        log.toggleSore("Chest")
        #expect(log.soreAreas == ["Chest"])
    }

    @Test func weightAcceptsCommaAndRejectsNonsense() {
        let log = model()
        log.weight = "82,4"
        #expect(log.weightInput == MetricInput(date: "2026-10-28", metric: "weight", value: 82.4, unit: "kg"))
        log.weight = "8"
        #expect(log.weightInput == nil)
    }

    @Test func weightIsOptionalButMustMakeSense() {
        let log = model()
        log.energy = 4
        log.sleep = 3
        log.stress = 2
        #expect(log.canSave)
        #expect(log.writes.map(\.path) == ["/checkins"])
        log.weight = "8"
        #expect(!log.canSave)
        log.weight = "82,4"
        #expect(log.canSave)
        #expect(log.writes.map(\.path) == ["/checkins", "/metrics"])
    }

    @Test func sickToggleAddsItsWrite() {
        let log = model()
        log.energy = 2
        log.sleep = 2
        log.stress = 3
        log.sick = true
        #expect(log.writes.map(\.path) == ["/checkins", "/sick-mode"])
    }
}
