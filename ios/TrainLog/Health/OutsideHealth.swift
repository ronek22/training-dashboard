import Foundation
import HealthKit

/// Today in Apple Health for the evening day strip: steps per hour, time in daylight (Watch) and
/// workouts. Read on the phone only, like `LiveHealth`; nothing goes to the Mac.
struct OutsideDay: Sendable, Equatable {
    struct Span: Sendable, Equatable {
        let start: Date
        let end: Date
    }

    struct Workout: Sendable, Equatable {
        let start: Date
        let end: Date
        let sport: Sport
    }

    var steps: [LiveDay.Hour] = []
    var daylight: [Span] = []
    /// Nil without any daylight sample today (no Watch, or no Health access).
    var daylightMinutes: Int?
    var workouts: [Workout] = []

    var stepTotal: Double { steps.map(\.value).reduce(0, +) }
}

enum OutsideHealth {
    static let daylightType = HKQuantityType(.timeInDaylight)
    private static let store = HKHealthStore()

    /// Asks once for time in daylight, which older installs never requested. Only while Health
    /// reading is on in Settings, so the sheet never shows for someone who turned it off.
    @MainActor
    static func requestDaylightIfNeeded() async {
        guard HealthSync.isAvailable, HealthSync.shared.readsRecovery else { return }
        let status = try? await store.statusForAuthorizationRequest(toShare: [], read: [daylightType])
        guard status == .shouldRequest else { return }
        try? await store.requestAuthorization(toShare: [], read: [daylightType])
    }

    static func today(now: Date = .now) async -> OutsideDay? {
        guard HealthSync.isAvailable else { return nil }
        let start = Calendar.current.startOfDay(for: now)
        var day = OutsideDay()
        day.steps = await LiveHealth.today(now: now)?.steps ?? []
        let range = HKQuery.predicateForSamples(withStart: start, end: now)
        let daylight = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: daylightType, predicate: range)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        if let samples = try? await daylight.result(for: store), !samples.isEmpty {
            day.daylight = samples.map { OutsideDay.Span(start: $0.startDate, end: $0.endDate) }
            let minutes = samples.map { $0.quantity.doubleValue(for: .minute()) }.reduce(0, +)
            day.daylightMinutes = Int(minutes.rounded())
        }
        let workouts = HKSampleQueryDescriptor(
            predicates: [.workout(range)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )
        if let samples = try? await workouts.result(for: store) {
            day.workouts = samples.map { .init(start: $0.startDate, end: $0.endDate, sport: sport($0.workoutActivityType)) }
        }
        return day.steps.isEmpty && day.daylightMinutes == nil && day.workouts.isEmpty ? nil : day
    }

    static func sport(_ type: HKWorkoutActivityType) -> Sport {
        switch type {
        case .cycling: .ride
        case .running: .run
        case .traditionalStrengthTraining, .functionalStrengthTraining, .coreTraining, .highIntensityIntervalTraining: .strength
        case .walking: .walk
        case .hiking: .hike
        case .yoga, .pilates, .flexibility, .mindAndBody, .cooldown: .mobility
        default: .other
        }
    }
}
