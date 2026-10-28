import Foundation
import Testing
@testable import TrainLog

struct HealthSyncTests {
    private var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Warsaw")!
        return calendar
    }

    private func date(_ iso: String) -> Date { ISO8601DateFormatter().date(from: iso)! }

    @Test func encodesTheShortcutPayloadKeys() throws {
        var push = HealthPush(exportedAt: "2026-10-28T09:00:00+01:00")
        push.sleep = [.init(start: "2026-10-27T23:00:00+01:00", end: "2026-10-28T01:00:00+01:00", value: 4,
                            source: "Apple Watch", sourceBundle: "com.apple.health.ABC", device: "Watch7,5")]
        push.walkingRunningDistance = [.init(start: "2026-10-28T00:00:00+01:00", value: 3.2, unit: "km")]
        let json = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(push)) as! [String: Any]

        #expect(json["exported_at"] as? String == "2026-10-28T09:00:00+01:00")
        let sleep = (json["sleep"] as! [[String: Any]])[0]
        #expect(sleep["source_bundle"] as? String == "com.apple.health.ABC")
        #expect(sleep["value"] as? Double == 4)
        #expect((json["walking_running_distance"] as! [Any]).count == 1)
        #expect((json["resting_hr"] as! [Any]).isEmpty)
        #expect(push.sampleCount == 2)
    }

    @Test func timestampsKeepTheLocalOffset() {
        let warsaw = TimeZone(identifier: "Europe/Warsaw")!
        #expect(HealthPush.timestamp(date("2026-10-27T23:00:00Z"), in: warsaw) == "2026-10-28T00:00:00+01:00")
    }

    @Test func windowIsAWeekNormallyAndReachesBackAfterAGap() {
        let now = date("2026-10-28T08:00:00Z")
        let start = { (last: Date?) in HealthPush.windowStart(now: now, lastSuccess: last, calendar: calendar) }

        // Midnight on 21 Oct is still summer time (UTC+2); clocks went back on the 25th.
        #expect(start(date("2026-10-28T06:00:00Z")) == date("2026-10-20T22:00:00Z"))
        #expect(start(date("2026-10-12T06:00:00Z")) == date("2026-10-10T22:00:00Z"))
        #expect(start(nil) == date("2026-09-27T22:00:00Z"))
        #expect(start(date("2026-08-01T06:00:00Z")) == date("2026-09-27T22:00:00Z"))
    }
}
