import Foundation
import HealthKit

/// Body of `POST /integrations/health-workouts/push`: Apple Watch workouts with their streams in
/// Strava's shape (one array per key, all as long as `time`), so the backend computes load and
/// charts before Strava has the activity. Strava links to the same activity later and adds its
/// title, power and photos.
struct WorkoutPush: Encodable, Sendable {
    struct Workout: Encodable, Sendable, Equatable {
        let uuid: String
        let type: String
        let name: String
        let start: String
        let end: String
        let durationS: Double
        var distanceM: Double?
        var energyKcal: Double?
        var elevationM: Double?
        var avgHr: Double?
        var maxHr: Double?
        var avgWatts: Double?
        var sourceBundle: String?
        var device: String?
        var streams: Streams?
    }

    struct Streams: Encodable, Sendable, Equatable {
        var time: [Int] = []
        var heartrate: [Double?] = []
        var latlng: [[Double]]?
        var altitude: [Double]?
        var velocitySmooth: [Double?]?
        var distance: [Double]?
        var cadence: [Double?]?
        var watts: [Double?]?
    }

    let workouts: [Workout]
}

struct WorkoutPushResult: Decodable, Sendable {
    let counts: [String: Int]
}

/// The backend's activity type and a readable default name for a HealthKit workout.
enum WorkoutKind {
    static func type(_ activity: HKWorkoutActivityType) -> String {
        switch activity {
        case .running: "Run"
        case .cycling: "Ride"
        case .walking: "Walk"
        case .hiking: "Hike"
        case .traditionalStrengthTraining, .functionalStrengthTraining: "WeightTraining"
        case .yoga: "Yoga"
        case .swimming: "Swim"
        case .rowing: "Rowing"
        case .elliptical: "Elliptical"
        default: "Workout"
        }
    }

    static func name(_ activity: HKWorkoutActivityType, indoor: Bool) -> String {
        switch activity {
        case .running: indoor ? "Indoor Run" : "Outdoor Run"
        case .cycling: indoor ? "Indoor Cycling" : "Outdoor Cycling"
        case .walking: indoor ? "Indoor Walk" : "Outdoor Walk"
        case .hiking: "Hiking"
        case .traditionalStrengthTraining: "Traditional Strength Training"
        case .functionalStrengthTraining: "Functional Strength Training"
        case .coreTraining: "Core Training"
        case .highIntensityIntervalTraining: "HIIT"
        case .yoga: "Yoga"
        case .swimming: "Swimming"
        case .rowing: "Rowing"
        case .elliptical: "Elliptical"
        default: "Workout"
        }
    }

    /// Only the watch's own Workout app (and the phone's Fitness app): Zwift and other apps that
    /// write to Health reach the backend through Strava, so taking them here would duplicate them.
    static func isAppleRecorded(bundle: String) -> Bool {
        bundle.hasPrefix("com.apple.health")
    }
}

/// Lines HealthKit samples up on one timeline. The route's GPS points (about one a second) are the
/// timeline when there is one; indoors it's the heart-rate samples. Other series take their last
/// value at or before each point, and nothing when that value is older than `staleAfter`.
struct WorkoutStreamBuilder {
    struct Location: Equatable {
        let date: Date
        let latitude: Double
        let longitude: Double
        let altitude: Double
        let speed: Double?  // m/s; nil when GPS didn't know
    }

    struct Sample: Equatable {
        let date: Date
        let value: Double
    }

    var staleAfter: TimeInterval = 15

    func build(
        start: Date,
        locations: [Location],
        heartRate: [Sample],
        power: [Sample] = [],
        cadence: [Sample] = [],
        speed: [Sample] = []
    ) -> WorkoutPush.Streams? {
        let dates = locations.isEmpty ? heartRate.map(\.date) : locations.map(\.date)
        guard !dates.isEmpty else { return nil }

        var streams = WorkoutPush.Streams()
        streams.time = dates.map { max(0, Int(($0.timeIntervalSince(start)).rounded())) }
        streams.heartrate = align(heartRate, to: dates).map { $0.map { $0.rounded() } }
        if !power.isEmpty { streams.watts = align(power, to: dates).map { $0.map { $0.rounded() } } }
        if !cadence.isEmpty { streams.cadence = align(cadence, to: dates).map { $0.map { $0.rounded() } } }

        if locations.isEmpty {
            if !speed.isEmpty { streams.velocitySmooth = align(speed, to: dates).map { $0.map(Self.twoPlaces) } }
            return streams
        }
        streams.latlng = locations.map { [Self.sixPlaces($0.latitude), Self.sixPlaces($0.longitude)] }
        streams.altitude = locations.map { (($0.altitude) * 10).rounded() / 10 }
        var total = 0.0
        var distance: [Double] = []
        for (index, location) in locations.enumerated() {
            if index > 0 { total += Self.meters(from: locations[index - 1], to: location) }
            distance.append(total.rounded())
        }
        streams.distance = distance
        let gpsSpeed = locations.map { $0.speed.flatMap { $0 >= 0 ? Self.twoPlaces($0) : nil } }
        streams.velocitySmooth = gpsSpeed.contains { $0 != nil } ? gpsSpeed : nil
        return streams
    }

    private func align(_ samples: [Sample], to dates: [Date]) -> [Double?] {
        var index = 0
        var last: Sample?
        return dates.map { date in
            while index < samples.count, samples[index].date <= date {
                last = samples[index]
                index += 1
            }
            guard let last, date.timeIntervalSince(last.date) <= staleAfter else { return nil }
            return last.value
        }
    }

    private static func meters(from a: Location, to b: Location) -> Double {
        let radius = 6_371_000.0
        let lat1 = a.latitude * .pi / 180, lat2 = b.latitude * .pi / 180
        let dLat = lat2 - lat1, dLon = (b.longitude - a.longitude) * .pi / 180
        let h = sin(dLat / 2) * sin(dLat / 2) + cos(lat1) * cos(lat2) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * radius * asin(min(1, sqrt(h)))
    }

    private static func twoPlaces(_ value: Double) -> Double { (value * 100).rounded() / 100 }
    private static func sixPlaces(_ value: Double) -> Double { (value * 1_000_000).rounded() / 1_000_000 }
}
