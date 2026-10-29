import Foundation
import Observation
import UIKit

/// Drives one strength workout: one set at a time, logged optimistically so a dropped
/// connection never loses a set. Writes go through `WriteQueue` and are replayed in order.
@MainActor
@Observable
final class StrengthSessionModel {
    enum Phase: Equatable {
        case loading
        /// A planned workout not started yet: today's targets before the first set.
        case brief(StrengthTemplate)
        case ready
        case failed(String)
        case closed
    }

    private(set) var phase: Phase = .loading
    private(set) var session: StrengthSession?
    private(set) var hints: [String: String] = [:]
    /// The brief's Start button is waiting on the server.
    private(set) var starting = false
    /// Writes waiting for the server.
    private(set) var unsynced = false
    private(set) var restEndsAt: Date?
    private(set) var restSeconds = 0
    /// The set just logged, for the confirmation that pops up over the log button.
    private(set) var lastLogged: LoggedSet?
    /// Bumped by every local write, so a poll that raced one is dropped instead of rolling it back.
    private var edits = 0

    var draftWeight: Double?
    var draftReps = 0
    var draftEffort: SetEffort?

    private let templateId: Int?
    private let client: () -> APIClient
    private let queue: WriteQueue
    private let store: SessionStore

    init(
        templateId: Int?,
        client: @escaping () -> APIClient = { .current },
        queue: WriteQueue = WriteQueue(),
        store: SessionStore = SessionStore()
    ) {
        self.templateId = templateId
        self.client = client
        self.queue = queue
        self.store = store
    }

    // MARK: Derived

    var current: (exercise: StrengthSession.Exercise, set: StrengthSession.WorkoutSet)? {
        session.flatMap { StrengthLogic.current(in: $0) }
    }

    var allSetsDone: Bool {
        session.map { $0.exercises.allSatisfy(\.isDone) } ?? false
    }

    var startedAt: Date? {
        session.flatMap { StrengthFormat.parseMoment($0.startedAt) }
    }

    // MARK: Loading

    func load() async {
        let api = client()
        let synced = await queue.flush(with: api)
        unsynced = !synced
        let local = store.load()

        // Queued writes mean the server is behind this phone: keep the local copy.
        if !synced, let local, local.isActive {
            show(local)
            await loadHints(templateId: local.templateId)
            return
        }

        do {
            var live = try await api.getLive("/strength/workouts/sessions/active", as: StrengthSession?.self)
            if live == nil, let templateId {
                // Brief first; without the template (old server, offline) start straight away.
                if let template = try? await api.get("/strength/workouts/templates/\(templateId)", as: StrengthTemplate.self) {
                    hints = Self.hints(from: template.value)
                    phase = .brief(template.value)
                    return
                }
                live = try await start(templateId, api: api)
            }
            guard let live else {
                phase = .failed("No strength workout planned today. Start one from the web app.")
                return
            }
            show(live)
            await loadHints(templateId: live.templateId)
        } catch {
            if let local, local.isActive {
                unsynced = true
                show(local)
                await loadHints(templateId: local.templateId)
            } else {
                phase = .failed(error.localizedDescription)
            }
        }
    }

    private func start(_ templateId: Int, api: APIClient) async throws -> StrengthSession? {
        let body = try APIClient.encoder.encode(["template_id": templateId])
        do {
            return try await api.send("POST", "/strength/workouts/sessions", body: body, as: StrengthSession.self)
        } catch APIError.status(409) {
            // Started elsewhere a moment ago: resume that one.
            return try await api.getLive("/strength/workouts/sessions/active", as: StrengthSession?.self)
        }
    }

    /// Starts the workout the brief showed.
    func startFromBrief() async {
        guard case .brief = phase, let templateId, !starting else { return }
        starting = true
        defer { starting = false }
        do {
            guard let live = try await start(templateId, api: client()) else { return }
            show(live)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func loadHints(templateId: Int?) async {
        guard let templateId, hints.isEmpty,
              let template = try? await client().get("/strength/workouts/templates/\(templateId)", as: StrengthTemplate.self)
        else { return }
        hints = Self.hints(from: template.value)
    }

    private static func hints(from template: StrengthTemplate) -> [String: String] {
        Dictionary(
            template.exercises.compactMap { exercise in exercise.next?.hint.map { (exercise.exerciseName, $0) } },
            uniquingKeysWith: { first, _ in first }
        )
    }

    private func show(_ session: StrengthSession) {
        let positionChanged = self.session.map {
            $0.currentExerciseOrder != session.currentExerciseOrder || $0.currentSetOrder != session.currentSetOrder
        } ?? true
        self.session = session
        store.save(session)
        if positionChanged { resetDrafts() }
        phase = .ready
        showActivity()
    }

    private func showActivity() {
        guard let session, session.isActive else { return }
        StrengthActivity.show(session, restEndsAt: restEndsAt, restSeconds: restSeconds)
    }

    // MARK: Actions

    func logCurrentSet() async {
        guard var session, let set = current?.set else { return }
        let reps = draftReps
        let weight = draftWeight
        let effort = draftEffort
        let label = current.map { StrengthLogic.label(for: set, in: $0.exercise) } ?? "Set"
        session = StrengthLogic.complete(session, setId: set.id, reps: reps, weightKg: weight, effort: effort)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        lastLogged = LoggedSet(setId: set.id, label: label, load: StrengthFormat.load(weight: weight, reps: reps))
        restSeconds = set.restSeconds
        restEndsAt = .now.addingTimeInterval(TimeInterval(set.restSeconds))
        show(session)
        resetDrafts()
        if let restEndsAt, let next = current, !allSetsDone {
            RestAlarm.schedule(at: restEndsAt, next: "\(next.exercise.exerciseName) · \(StrengthFormat.load(weight: draftWeight, reps: draftReps))")
        } else {
            RestAlarm.cancel()
        }

        let base = "/strength/workouts/sessions/\(session.id)/sets/\(set.id)"
        let completion = StrengthSetCompletion(actualReps: reps, actualWeightKg: weight)
        queue.append(.init(method: "POST", path: base + "/complete", body: try? APIClient.encoder.encode(completion)))
        if let effort {
            queue.append(.init(method: "PUT", path: base + "/effort", body: try? APIClient.encoder.encode(["effort": effort.rawValue])))
        }
        await sync()
    }

    func jump(to exercise: StrengthSession.Exercise) async {
        guard var session, session.isActive else { return }
        let setOrder = exercise.sets.first(where: { !$0.isCompleted })?.setOrder ?? exercise.sets.first?.setOrder ?? 1
        session.currentExerciseOrder = exercise.exerciseOrder
        session.currentSetOrder = setOrder
        show(session)
        let body = try? APIClient.encoder.encode(["exercise_order": exercise.exerciseOrder, "set_order": setOrder])
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/\(session.id)/position", body: body))
        await sync()
    }

    func skipRest() {
        restEndsAt = nil
        RestAlarm.cancel()
        showActivity()
    }

    func adjustWeight(by steps: Int) {
        draftWeight = StrengthLogic.step(draftWeight, by: steps)
    }

    func adjustReps(by delta: Int) {
        draftReps = min(100, max(0, draftReps + delta))
    }

    func finish() async {
        guard let session else { return }
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/\(session.id)/finish", body: Data("{}".utf8)))
        await close()
    }

    func abandon() async {
        guard let session else { return }
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/\(session.id)/abandon", body: nil))
        await close()
    }

    private func close() async {
        store.clear()
        RestAlarm.cancel()
        StrengthActivity.end()
        // Flush before closing so Today's reload doesn't still see the workout as open.
        unsynced = !(await queue.flush(with: client()))
        phase = .closed
    }

    /// Picks up sets logged on the web while this screen is open. Skipped while this phone has
    /// writes the server hasn't seen, and dropped if one started while the request was out.
    func refresh() async {
        let started = edits
        guard phase == .ready, queue.pending.isEmpty, let id = session?.id,
              let live = try? await client().getLive("/strength/workouts/sessions/\(id)", as: StrengthSession.self),
              edits == started, phase == .ready, queue.pending.isEmpty, live != session
        else { return }
        if live.isActive {
            show(live)
        } else {
            // Finished or discarded on the web.
            store.clear()
            RestAlarm.cancel()
            StrengthActivity.end()
            phase = .closed
        }
    }

    /// Replays queued writes, then trusts the server's copy (its progression and position).
    private func sync() async {
        edits += 1
        let api = client()
        guard await queue.flush(with: api) else {
            unsynced = true
            return
        }
        unsynced = false
        guard let id = session?.id,
              let live = try? await api.getLive("/strength/workouts/sessions/\(id)", as: StrengthSession.self)
        else { return }
        show(live)
    }

    private func resetDrafts() {
        guard let session, let current = StrengthLogic.current(in: session) else { return }
        draftWeight = StrengthLogic.carriedWeight(for: current.set, in: current.exercise)
        draftReps = current.set.targetReps
        draftEffort = nil
    }
}

struct LoggedSet: Equatable {
    let setId: Int
    let label: String
    let load: String
}

private struct StrengthSetCompletion: Encodable {
    let actualReps: Int
    let actualWeightKg: Double?
}

/// The live session on disk, so the workout survives the app being killed mid-set.
struct SessionStore: Sendable {
    var file: URL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appending(path: "active-strength-session.json")

    func load() -> StrengthSession? {
        (try? Data(contentsOf: file)).flatMap { try? APIClient.decoder.decode(StrengthSession.self, from: $0) }
    }

    func save(_ session: StrengthSession) {
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? APIClient.encoder.encode(session).write(to: file, options: .atomic)
    }

    func clear() {
        try? FileManager.default.removeItem(at: file)
    }
}

/// Pure session rules, mirroring backend `complete_set` (unit-tested).
enum StrengthLogic {
    static func current(in session: StrengthSession) -> (exercise: StrengthSession.Exercise, set: StrengthSession.WorkoutSet)? {
        guard let exercise = session.exercises.first(where: { $0.exerciseOrder == session.currentExerciseOrder }),
              let set = exercise.sets.first(where: { $0.setOrder == session.currentSetOrder }) ?? exercise.sets.first
        else { return nil }
        return (exercise, set)
    }

    /// Marks a set done and moves to the next pending set, preferring the same exercise.
    static func complete(
        _ session: StrengthSession, setId: Int, reps: Int, weightKg: Double?, effort: SetEffort?
    ) -> StrengthSession {
        var session = session
        guard let exerciseIndex = session.exercises.firstIndex(where: { $0.sets.contains { $0.id == setId } }),
              let setIndex = session.exercises[exerciseIndex].sets.firstIndex(where: { $0.id == setId })
        else { return session }
        session.exercises[exerciseIndex].sets[setIndex].actualReps = reps
        session.exercises[exerciseIndex].sets[setIndex].actualWeightKg = weightKg
        session.exercises[exerciseIndex].sets[setIndex].status = "completed"
        session.exercises[exerciseIndex].sets[setIndex].effort = effort?.rawValue

        let same = session.exercises[exerciseIndex]
        let candidates = [same] + session.exercises.filter { $0.id != same.id }.sorted { $0.exerciseOrder < $1.exerciseOrder }
        for exercise in candidates {
            if let next = exercise.sets.sorted(by: { $0.setOrder < $1.setOrder }).first(where: { !$0.isCompleted }) {
                session.currentExerciseOrder = exercise.exerciseOrder
                session.currentSetOrder = next.setOrder
                break
            }
        }
        return session
    }

    /// A weight changed on an earlier set of the same lift carries to the next one.
    static func carriedWeight(for set: StrengthSession.WorkoutSet, in exercise: StrengthSession.Exercise) -> Double? {
        guard !set.isWarmup else { return set.targetWeightKg }
        let previous = exercise.workingSets.last { $0.isCompleted && $0.setOrder < set.setOrder }
        return previous?.actualWeightKg ?? set.targetWeightKg
    }

    /// 0.5 kg steps; stepping down from 0 goes back to bodyweight (nil).
    static func step(_ weight: Double?, by steps: Int) -> Double? {
        guard let weight else { return steps > 0 ? Double(steps) * 0.5 : nil }
        let next = ((weight + Double(steps) * 0.5) * 2).rounded() / 2
        return next <= 0 ? nil : min(1000, next)
    }

    /// "Set 2" counting working sets only; warm-ups are labelled as such.
    static func label(for set: StrengthSession.WorkoutSet, in exercise: StrengthSession.Exercise) -> String {
        if set.isWarmup { return "Warm-up" }
        let index = exercise.workingSets.firstIndex { $0.id == set.id } ?? 0
        return "Set \(index + 1)"
    }

    /// Completed share of each exercise's working sets, for the segmented progress bar.
    static func progress(of exercise: StrengthSession.Exercise) -> Double {
        let working = exercise.workingSets
        guard !working.isEmpty else { return exercise.isDone ? 1 : 0 }
        return Double(working.filter(\.isCompleted).count) / Double(working.count)
    }
}

enum StrengthFormat {
    static func weight(_ kg: Double?) -> String {
        guard let kg else { return "BW" }
        return TodayFormat.number(kg)
    }

    static func load(weight: Double?, reps: Int) -> String {
        weight.map { "\(TodayFormat.number($0)) kg × \(reps)" } ?? "BW × \(reps)"
    }

    static func clock(_ seconds: Int) -> String {
        let seconds = max(0, seconds)
        let hours = seconds / 3600
        let minutes = seconds % 3600 / 60
        let rest = seconds % 60
        return hours > 0
            ? String(format: "%d:%02d:%02d", hours, minutes, rest)
            : String(format: "%d:%02d", minutes, rest)
    }

    static func parseMoment(_ iso: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: iso) { return date }
        // Backend timestamps without an offset are local time.
        let local = DateFormatter()
        local.locale = Locale(identifier: "en_US_POSIX")
        local.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return local.date(from: iso)
    }
}
