import Foundation
import HealthKit
import Observation

/// `GET /phone/today`, only what the Watch's start screen uses.
struct WatchToday: Decodable, Sendable {
    let date: String
    let today: Session?

    struct Session: Decodable, Sendable {
        let title: String?
        let durationMin: Int?
        let status: String?
        let strength: Strength?

        var isDone: Bool { ["matched", "linked", "rest_day_changed"].contains(status ?? "") }
    }

    struct Strength: Decodable, Sendable {
        /// Nil on a bodyweight day: the exercises start as a one-time session.
        let templateId: Int?
        var name: String?
        let exercises: [Exercise]
    }

    struct Exercise: Decodable, Sendable {
        let name: String
        let sets: Int
        let reps: Int?
        let weightKg: Double?
        var restSeconds: Int?
        var notes: String?
        var seconds: Int?
    }
}

/// `POST /strength/workouts/sessions/one-time` body (TemplateInput on the phone).
private struct OneTimeWorkout: Encodable {
    let name: String
    let notes: String?
    let exercises: [Exercise]

    struct Exercise: Encodable {
        let exerciseName: String
        let setCount: Int
        let targetReps: Int
        let targetWeightKg: Double?
        let restSeconds: Int
        let notes: String?
        let targetSeconds: Int?
    }

    init(_ strength: WatchToday.Strength) {
        name = strength.name ?? "Bodyweight"
        notes = nil
        exercises = strength.exercises.map {
            Exercise(exerciseName: $0.name, setCount: $0.sets, targetReps: $0.seconds == nil ? $0.reps ?? 10 : 1,
                     targetWeightKg: $0.weightKg, restSeconds: $0.restSeconds ?? 60, notes: $0.notes, targetSeconds: $0.seconds)
        }
    }
}

/// What can start from the wrist today: the planned lift (or a bodyweight day), a workout already
/// running on the phone or web, and the rehab routine.
@MainActor
@Observable
final class StartModel {
    enum Phase: Equatable {
        case loading
        case ready
        case failed(String)
    }

    private(set) var phase: Phase = .loading
    private(set) var date: String?
    private(set) var strength: WatchToday.Strength?
    private(set) var strengthDone = false
    private(set) var durationMin: Int?
    private(set) var active: StrengthSession?
    private(set) var rehab: GuidedSession?
    /// Drawn from a cache: the phone or server is out of reach.
    private(set) var stale = false
    private(set) var starting = false
    var startError: String?

    var isEmpty: Bool { strength == nil && active == nil && rehab == nil }

    func load() async {
        #if DEBUG
        if WatchDemo.enabled {
            date = WatchDemo.today.date
            strength = WatchDemo.today.today?.strength
            durationMin = 45
            rehab = WatchDemo.rehab
            phase = .ready
            return
        }
        #endif
        async let today = try? WatchAPI.get("/phone/today", as: WatchToday.self)
        async let active = try? WatchAPI.get("/strength/workouts/sessions/active", as: StrengthSession?.self)
        async let rehab = try? WatchAPI.get("/guided-sessions/rehab", as: GuidedSessionEnvelope.self)
        let (loadedToday, loadedActive, loadedRehab) = await (today, active, rehab)

        guard loadedToday != nil || loadedActive != nil else {
            phase = .failed(PhoneLink.shared.reachable ? LinkError.serverUnreachable.localizedDescription : LinkError.phoneUnreachable.localizedDescription)
            return
        }
        date = loadedToday?.value.date
        let session = loadedToday?.value.today
        strength = session?.strength.flatMap { $0.exercises.isEmpty ? nil : $0 }
        strengthDone = session?.isDone ?? false
        durationMin = session?.durationMin
        // Only a live answer: a cached one may be a workout finished since, and Resume would log
        // sets into it.
        let running: StrengthSession? = loadedActive.flatMap { $0.stale ? nil : $0.value }
        self.active = running?.isActive == true ? running : nil
        self.rehab = loadedRehab?.value.session.exercises.isEmpty == false ? loadedRehab?.value.session : nil
        stale = loadedToday?.stale ?? true
        phase = .ready
    }

    /// Starts today's lift on the server (or picks up the one already running). Nil on failure, with
    /// `startError` set.
    func startStrength() async -> StrengthSession? {
        if let active { return active }
        #if DEBUG
        if WatchDemo.enabled { return WatchDemo.session() }
        #endif
        guard let strength, !starting else { return nil }
        starting = true
        defer { starting = false }
        do {
            if let templateId = strength.templateId {
                let body = try WatchAPI.encoder.encode(["template_id": templateId])
                return try await start("/strength/workouts/sessions", body: body)
            }
            return try await start("/strength/workouts/sessions/one-time", body: WatchAPI.encoder.encode(OneTimeWorkout(strength)))
        } catch {
            startError = error.localizedDescription
            return nil
        }
    }

    private func start(_ path: String, body: Data) async throws -> StrengthSession? {
        do {
            return try await WatchAPI.send("POST", path, body: body, as: StrengthSession.self)
        } catch LinkError.status(409) {
            // Started elsewhere a moment ago: resume that one.
            return try await WatchAPI.get("/strength/workouts/sessions/active", as: StrengthSession?.self).value
        }
    }

    /// Bodyweight days (no saved workout) are functional strength in Apple Health.
    func activityType(for session: StrengthSession) -> HKWorkoutActivityType {
        session.templateId == nil ? .functionalStrengthTraining : .traditionalStrengthTraining
    }
}
