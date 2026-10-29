import Foundation
import Testing
@testable import TrainLog

struct RideExportTests {
    private func ride(_ json: String) throws -> IndoorRides.Ride {
        try APIClient.decoder.decode(IndoorRides.self, from: Data(json.utf8)).rides[0]
    }

    @Test func decodesRideAndBuildsSamples() throws {
        // 150 s: two full minutes and a 30 s tail; power only in the first minute.
        let time = (0...150).map(Double.init)
        let watts = time.map { $0 <= 60 ? "200" : "0" }
        let heart = time.map { $0 == 3 ? "null" : "140" }
        let distance = time.map { String($0 * 8) }
        let json = """
        {"rides": [{"id": "20782078210", "name": "Zwift - Endurance 60", "start": "2026-10-29T17:57:37Z",
          "duration_s": 150, "distance_m": 1200, "energy_kcal": 12, "avg_hr": 140,
          "streams": {"time": [\(time.map { String(Int($0)) }.joined(separator: ","))],
                      "heartrate": [\(heart.joined(separator: ","))],
                      "watts": [\(watts.joined(separator: ","))],
                      "distance": [\(distance.joined(separator: ","))]}}]}
        """
        let samples = try #require(RideSamples(try ride(json)))
        let start = try Date("2026-10-29T17:57:37Z", strategy: .iso8601)

        #expect(samples.start == start)
        #expect(samples.end == start.addingTimeInterval(150))
        #expect(samples.heartRate.count == 150)  // the null second is dropped
        #expect(samples.power.count == 151)
        #expect(samples.cadence.isEmpty)
        #expect(samples.distance.map(\.value) == [480, 480, 240])
        #expect(samples.distance.last?.end == start.addingTimeInterval(150))
        // All the work happened in the first minute, so all the energy lands there.
        #expect(samples.energy == [.init(start: start, end: start.addingTimeInterval(60), value: 12)])
        #expect(RideSamples.brand("Zwift - Endurance 60") == "Zwift")
        #expect(RideSamples.brand("Test MyWhoosh & Knee") == "MyWhoosh")
        #expect(RideSamples.brand("Indoor ride") == nil)
    }

    @Test func rideWithoutStreamsKeepsTotals() throws {
        let samples = try #require(RideSamples(try ride("""
        {"rides": [{"id": "1", "name": null, "start": "2026-10-23T17:00:00Z", "duration_s": 2400,
          "distance_m": 20500, "energy_kcal": 480, "avg_hr": null, "streams": null}]}
        """)))
        #expect(samples.heartRate.isEmpty)
        #expect(samples.distance.map(\.value) == [20500])
        #expect(samples.energy.map(\.value) == [480])
        #expect(samples.energy.first?.end == samples.end)
    }

    @Test func rideWithBadStartIsSkipped() throws {
        #expect(RideSamples(try ride("""
        {"rides": [{"id": "1", "start": "yesterday", "duration_s": 60}]}
        """)) == nil)
    }
}
