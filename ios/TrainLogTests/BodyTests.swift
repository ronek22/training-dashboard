import Foundation
import Testing
@testable import TrainLog

struct BodyTests {
    private let json = """
    {"date": "2026-10-28",
     "readiness": {"level": "amber", "label": "Amber", "advice": "Keep it easy.", "factors": [
       {"key": "sleep", "label": "Sleep", "detail": "6.2 h last night", "tone": "caution"},
       {"key": "hrv", "label": "HRV", "detail": "49 ms", "tone": "steady"}]},
     "sleep": {"date": "2026-10-28", "asleep_h": 6.0, "stages": {"core": 3.5, "deep": 1.0, "rem": 1.5, "awake": 0.25},
       "start": "2026-10-28T00:00:00Z", "end": "2026-10-28T08:00:00Z", "baseline_h": 7.0,
       "segments": [
         {"stage": "core", "start": "2026-10-28T00:00:00Z", "end": "2026-10-28T02:00:00Z"},
         {"stage": "asleep_unspecified", "start": "2026-10-28T02:00:00Z", "end": "2026-10-28T04:00:00Z"},
         {"stage": "in_bed", "start": "2026-10-28T04:00:00Z", "end": "2026-10-28T05:00:00Z"},
         {"stage": "deep", "start": "2026-10-28T06:00:00Z", "end": "2026-10-28T08:00:00Z"}]},
     "vitals": {"resting_hr": {"date": "2026-10-28", "value": 57.0, "baseline": 60.0},
                "hrv": {"date": "2026-10-28", "value": 49.1, "baseline": 48.5},
                "steps": {"date": "2026-10-27", "value": 9000, "baseline": null}},
     "load": {"fitness": 49, "fatigue": 45, "form": 4, "ratio": 0.93, "ratio_status": "balanced",
              "chart": [{"date": "2026-10-28", "load": 0.0, "fitness": 48.9, "fatigue": 45.3, "form": 3.6}]}}
    """

    private func decoded() throws -> PhoneBody {
        try APIClient.decoder.decode(PhoneBody.self, from: Data(json.utf8))
    }

    @Test func decodesBody() throws {
        let body = try decoded()
        #expect(body.readiness.factors.map(\.key) == ["sleep", "hrv"])
        #expect(body.sleep?.stages.awake == 0.25)
        #expect(body.vitals.steps?.baseline == nil)
        #expect(body.load.ratioStatus == "balanced")
        #expect(body.load.chart.first?.form == 3.6)
    }

    @Test func sleepBlocksAreFractionsOfTheNight() throws {
        let sleep = try #require(try decoded().sleep as PhoneBody.Sleep?)
        let blocks = BodyFormat.blocks(sleep)
        // Unstaged sleep sits in the core lane; in-bed time isn't a stage.
        #expect(blocks.map(\.stage) == [.core, .core, .deep])
        #expect(blocks[0] == SleepBlock(stage: .core, from: 0, to: 0.25))
        #expect(blocks[2].from == 0.75)
        #expect(blocks[2].to == 1)
    }

    @Test func formatsSleep() throws {
        let sleep = try #require(try decoded().sleep as PhoneBody.Sleep?)
        #expect(BodyFormat.duration(6.2) == "6 h 12")
        #expect(BodyFormat.duration(0.8) == "48 min")
        #expect(BodyFormat.sleepDelta(sleep)?.text == "−60 min vs 30 d")
        #expect(BodyFormat.sleepDelta(sleep)?.good == false)
        #expect(BodyFormat.hours(.awake, sleep.stages) == 0.25)
    }

    @Test func vitalStatusColoursOutliersByDirection() {
        #expect(VitalStatus(value: 50, low: 40, high: 60) == .typical)
        #expect(VitalStatus(value: 40, low: 40, high: 60) == .typical)
        #expect(VitalStatus(value: 35, low: 40, high: 60) == .low)
        #expect(VitalStatus(value: 65, low: 40, high: 60) == .high)
        #expect(VitalStatus(value: 65, low: nil, high: 60) == .unknown)
        #expect(VitalStatus.low.color(.hrv) == .warning)
        #expect(VitalStatus.low.color(.restingHr) == .mobility)
        #expect(VitalStatus.high.color(.restingHr) == .warning)
    }

    @Test func formZones() {
        #expect(BodyFormat.formZone(30).label == "Detraining")
        #expect(BodyFormat.formZone(12).label == "Fresh")
        #expect(BodyFormat.formZone(4).label == "Neutral")
        #expect(BodyFormat.formZone(-20).label == "Building")
        #expect(BodyFormat.formZone(-31).label == "Overreaching")
        #expect(BodyFormat.signed(3.6) == "+4")
        #expect(BodyFormat.signed(-12.2) == "−12")
    }

    @MainActor
    @Test func stepsPreferThePhonesCountAndIgnoreAnOldDay() async throws {
        let body = try decoded()
        let dir = FileManager.default.temporaryDirectory.appending(path: "body-\(UUID().uuidString)", directoryHint: .isDirectory)
        // Nothing listens on port 9, so both loads answer from the cache.
        let client = APIClient(baseURL: "http://127.0.0.1:9", cache: ResponseCache(directory: dir), reachability: Reachability())
        client.cache.store(Data(json.utf8), for: BodyModel.path)

        let offline = BodyModel(client: { client }, readLive: { nil })
        await offline.load()
        #expect(offline.data == body)
        // The server's steps are from yesterday, so today has no count yet.
        #expect(offline.steps == nil)

        let live = LiveDay(steps: [.init(start: .now, value: 1200), .init(start: .now, value: 300)])
        let withPhone = BodyModel(client: { client }, readLive: { live })
        await withPhone.load()
        #expect(withPhone.steps == 1500)
    }
}
