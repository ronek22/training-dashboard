import Foundation
import HealthKit
import Testing
@testable import TrainLog

struct WorkoutSyncTests {
    private let start = Date(timeIntervalSince1970: 1_790_000_000)

    private func at(_ seconds: TimeInterval) -> Date { start.addingTimeInterval(seconds) }

    @Test func mapsWorkoutTypesToBackendTypes() {
        #expect(WorkoutKind.type(.running) == "Run")
        #expect(WorkoutKind.type(.cycling) == "Ride")
        #expect(WorkoutKind.type(.traditionalStrengthTraining) == "WeightTraining")
        #expect(WorkoutKind.type(.functionalStrengthTraining) == "WeightTraining")
        #expect(WorkoutKind.type(.highIntensityIntervalTraining) == "Workout")
        #expect(WorkoutKind.name(.cycling, indoor: true) == "Indoor Cycling")
        #expect(WorkoutKind.name(.running, indoor: false) == "Outdoor Run")
    }

    @Test func takesOnlyAppleRecordedWorkouts() {
        #expect(WorkoutKind.isAppleRecorded(bundle: "com.apple.health.7F3A2C"))
        #expect(!WorkoutKind.isAppleRecorded(bundle: "com.zwift.ZwiftGame"))
        #expect(!WorkoutKind.isAppleRecorded(bundle: "com.strava.stravaride"))
    }

    @Test func indoorWorkoutUsesHeartRateAsTheTimeline() throws {
        let streams = try #require(WorkoutStreamBuilder().build(
            start: start,
            locations: [],
            heartRate: [.init(date: at(0), value: 98.4), .init(date: at(5), value: 110), .init(date: at(40), value: 120)],
            power: [.init(date: at(4), value: 180.6)]
        ))
        #expect(streams.time == [0, 5, 40])
        #expect(streams.heartrate == [98, 110, 120])
        // Power from second 4 holds for the next point, then goes stale.
        #expect(streams.watts == [nil, 181, nil])
        #expect(streams.latlng == nil)
        #expect(streams.velocitySmooth == nil)
    }

    @Test func outdoorWorkoutUsesTheRouteAndAddsDistance() throws {
        let route = (0..<3).map { second in
            WorkoutStreamBuilder.Location(
                date: at(Double(second)), latitude: 50.0 + Double(second) * 0.0001, longitude: 19.9,
                altitude: 210.04, speed: second == 1 ? nil : 8.456
            )
        }
        let streams = try #require(WorkoutStreamBuilder().build(
            start: start, locations: route, heartRate: [.init(date: at(1), value: 140)]
        ))
        #expect(streams.time == [0, 1, 2])
        #expect(streams.heartrate == [nil, 140, 140])
        #expect(streams.latlng?[1] == [50.0001, 19.9])
        #expect(streams.altitude == [210.0, 210.0, 210.0])
        #expect(streams.distance == [0, 11, 22])  // 0.0001° of latitude ≈ 11 m
        #expect(streams.velocitySmooth == [8.46, nil, 8.46])
    }

    @Test func noSamplesMeansNoStreams() {
        #expect(WorkoutStreamBuilder().build(start: start, locations: [], heartRate: []) == nil)
    }

    @Test func encodesTheBackendKeys() throws {
        var streams = WorkoutPush.Streams(time: [0, 1], heartrate: [120, nil])
        streams.velocitySmooth = [3.1, 3.2]
        let workout = WorkoutPush.Workout(
            uuid: "ABC", type: "Run", name: "Outdoor Run", start: "2026-10-28T07:00:00+01:00",
            end: "2026-10-28T07:30:00+01:00", durationS: 1800, distanceM: 5000, avgHr: 150,
            sourceBundle: "com.apple.health.X", streams: streams
        )
        let json = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(WorkoutPush(workouts: [workout]))) as! [String: Any]
        let item = (json["workouts"] as! [[String: Any]])[0]
        #expect(item["duration_s"] as? Double == 1800)
        #expect(item["distance_m"] as? Double == 5000)
        #expect(item["avg_hr"] as? Double == 150)
        #expect(item["source_bundle"] as? String == "com.apple.health.X")
        let encoded = item["streams"] as! [String: Any]
        #expect(encoded["velocity_smooth"] != nil)
        #expect((encoded["heartrate"] as! [Any]).count == 2)
    }
}
