import Foundation
import Observation
import UIKit

/// Drives one strength workout: one set at a time, logged optimistically so a dropped
/// connection never loses a set. Writes go through `WriteQueue` and are replayed in order.
///
/// With TrainLog on the Watch showing the same workout, every change here goes to `onShare` and
/// the Watch's changes come back through `adopt`, merged set by set; either device can end it.
@MainActor
@Observable
final class StrengthSessionModel {
    enum Phase: Equatable {
        case loading
        /// A planned workout not started yet: today's targets before the first set.
        case brief(StrengthTemplate)
        case ready
        case failed(String)
        /// Finished: the recap, until Done.
        case summary(StrengthSummary)
        case closed
    }

    private(set) var phase: Phase = .loading
    private(set) var session: StrengthSession?
    private(set) var hints: [String: String] = [:]
    /// The last few sessions of each lift in this workout, by exercise name.
    private(set) var history: [String: LiftHistory] = [:]
    /// Bar and plates from the Athlete page, for the plate row and the warm-up ramp.
    private(set) var kit = GymKit.standard
    /// Exercises whose warm-up ramp is done or skipped (kept per session on this phone).
    private(set) var rampDone: Set<Int> = []
    /// Ramp steps ticked for the current lift; never logged.
    private(set) var rampTicks: Set<Int> = []
    /// Screenshot state from `-strengthDemo`; never touches the server or the Watch.
    private(set) var isDemo = false
    /// The brief's Start button is waiting on the server.
    private(set) var starting = false
    /// Finish was tapped and the recap is on its way.
    private(set) var finishing = false
    /// Writes waiting for the server.
    private(set) var unsynced = false
    private(set) var restEndsAt: Date?
    private(set) var restSeconds = 0
    /// The set just logged, for the confirmation that pops up over the log button.
    private(set) var lastLogged: LoggedSet?
    /// Bumped by every local write, so a poll that raced one is dropped instead of rolling it back.
    private var edits = 0
    /// The session after a change here, for the Watch.
    var onShare: ((WatchWire.Strength) -> Void)?
    /// Finished or discarded here, so the Watch ends its workout too.
    var onEnd: ((WatchWire.Command) -> Void)?

    var draftWeight: Double?
    var draftReps = 0
    var draftEffort: SetEffort?
    /// Hold length for a timed set; adjustable until the timer starts.
    var draftSeconds = 0
    /// The hold timer is running since this moment. Started by hand, never by the rest ending.
    private(set) var holdStartedAt: Date?
    private var holdTask: Task<Void, Never>?

    private let templateId: Int?
    /// A bodyweight day's exercises, started as a one-time session when nothing is running.
    private let oneTime: TemplateInput?
    private let client: () -> APIClient
    private let queue: WriteQueue
    private let store: SessionStore

    init(
        templateId: Int?,
        oneTime: TemplateInput? = nil,
        client: @escaping () -> APIClient = { .current },
        queue: WriteQueue = WriteQueue(),
        store: SessionStore = SessionStore()
    ) {
        self.templateId = templateId
        self.oneTime = oneTime
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

    /// The warm-up ramp, while the current lift is the session's first barbell lift and nothing
    /// of it is logged yet. Skipped when the workout already has warm-up sets for it.
    var ramp: (exercise: StrengthSession.Exercise, working: Double, reps: Int, steps: [LiftLogic.RampStep])? {
        guard let session, let current, !allSetsDone, !current.set.isWarmup, !current.set.isTimed else { return nil }
        let exercise = current.exercise
        guard !rampDone.contains(exercise.id), !exercise.sets.contains(where: \.isWarmup),
              !exercise.workingSets.contains(where: \.isCompleted),
              let first = session.exercises.sorted(by: { $0.exerciseOrder < $1.exerciseOrder }).first(where: {
                  LiftLogic.isBarbell($0.exerciseName) && ($0.workingSets.first?.targetWeightKg ?? 0) > 0
              }),
              first.id == exercise.id,
              let working = draftWeight ?? current.set.targetWeightKg
        else { return nil }
        let steps = LiftLogic.ramp(to: working, kit: kit)
        return steps.isEmpty ? nil : (exercise, working, current.set.targetReps, steps)
    }

    var startedAt: Date? {
        session.flatMap { StrengthFormat.parseMoment($0.startedAt) }
    }

    // MARK: Loading

    func load() async {
        guard !isDemo else { return }
        let api = client()
        let synced = await queue.flush(with: api)
        unsynced = !synced
        let local = store.load()

        // Queued writes mean the server is behind this phone: keep the local copy.
        if !synced, let local, local.isActive {
            show(local)
            await loadExtras(for: local)
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
            } else if live == nil, let oneTime {
                live = try await startOneTime(oneTime, api: api)
            }
            guard let live else {
                phase = .failed("No strength workout planned today. Start one from the web app.")
                return
            }
            show(live)
            await loadExtras(for: live)
        } catch {
            if let local, local.isActive {
                unsynced = true
                show(local)
                await loadExtras(for: local)
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

    private func startOneTime(_ workout: TemplateInput, api: APIClient) async throws -> StrengthSession? {
        let body = try APIClient.encoder.encode(workout)
        do {
            return try await api.send("POST", "/strength/workouts/sessions/one-time", body: body, as: StrengthSession.self)
        } catch APIError.status(409) {
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
            await loadExtras(for: live)
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

    /// Hints, lift history and the gym's bar and plates: cached, so they still show offline.
    private func loadExtras(for session: StrengthSession) async {
        rampDone = Set(UserDefaults.standard.array(forKey: Self.rampKey(session.id)) as? [Int] ?? [])
        let api = client()
        async let hinted: Void = loadHints(templateId: session.templateId)
        async let profile = try? api.get("/settings/athlete-profile", as: GymKit.self)
        let names = session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }.map(\.exerciseName)
        if let path = LiftLogic.historyPath(for: names), let lifts = try? await api.get(path, as: [LiftHistory].self) {
            history = Dictionary(lifts.value.map { ($0.exerciseName, $0) }, uniquingKeysWith: { first, _ in first })
        }
        if let profile = await profile { kit = profile.value }
        await hinted
    }

    private static func rampKey(_ sessionId: Int) -> String { "strengthRampDone.\(sessionId)" }

    private static func hints(from template: StrengthTemplate) -> [String: String] {
        Dictionary(
            template.exercises.compactMap { exercise in exercise.next?.hint.map { (exercise.exerciseName, $0) } },
            uniquingKeysWith: { first, _ in first }
        )
    }

    /// `logged` is the set just logged here; `share` is false for a copy that came from the Watch.
    private func show(_ session: StrengthSession, logged: Int? = nil, share: Bool = true) {
        let positionChanged = self.session.map {
            $0.currentExerciseOrder != session.currentExerciseOrder || $0.currentSetOrder != session.currentSetOrder
        } ?? true
        self.session = session
        store.save(session)
        if positionChanged { resetDrafts() }
        phase = .ready
        showActivity()
        if share, session.isActive, let data = try? JSONEncoder().encode(session) {
            onShare?(WatchWire.Strength(session: data, loggedSetId: logged, restEndsAt: logged == nil ? nil : restEndsAt))
        }
    }

    // MARK: The Watch

    /// The Watch's copy after a change there: merged in (a set done here stays done), its rest
    /// started here too, and a finish or discard there closes this screen.
    func adopt(_ incoming: WatchWire.Strength) {
        guard let session, let theirs = try? JSONDecoder().decode(StrengthSession.self, from: incoming.session),
              theirs.id == session.id
        else { return }
        edits += 1
        let merged = StrengthLogic.merge(session, with: theirs)
        let doneHere = Set(session.exercises.flatMap(\.sets).filter(\.isCompleted).map(\.id))
        if let setId = incoming.loggedSetId, !doneHere.contains(setId),
           let exercise = merged.exercises.first(where: { $0.sets.contains { $0.id == setId } }),
           let set = exercise.sets.first(where: { $0.id == setId }), set.isCompleted {
            restSeconds = set.restSeconds
            restEndsAt = incoming.restEndsAt
            lastLogged = LoggedSet(
                setId: set.id, label: StrengthLogic.label(for: set, in: exercise) + " · on Watch",
                load: StrengthFormat.load(weight: set.actualWeightKg, reps: set.actualReps ?? 0, seconds: set.actualSeconds)
            )
        }
        guard merged.isActive else { return endedElsewhere(finished: merged.status == "completed") }
        show(merged, share: false)
    }

    /// A button on the Watch: Start on its ready screen starts the briefed workout here (for
    /// both); an end closes this screen (the Watch already told the server).
    func handleWatch(_ command: WatchWire.Command) {
        switch command {
        case .start: Task { await startFromBrief() }
        case .finish: endedElsewhere(finished: true)
        case .discard: endedElsewhere()
        default: break
        }
    }

    /// Ended on the Watch or the web; a finished workout still ends on its recap here.
    private func endedElsewhere(finished: Bool = false) {
        if case .summary = phase { return }
        guard phase != .closed else { return }
        store.clear()
        RestAlarm.cancel()
        StrengthActivity.end()
        guard finished, let session else {
            phase = .closed
            return
        }
        // The recap shows at once; the server's version follows when the Watch's finish lands there.
        phase = .summary(SummaryLogic.local(session))
        Task { await loadSummary(of: session) }
    }

    private func showActivity() {
        guard let session, session.isActive else { return }
        StrengthActivity.show(session, restEndsAt: restEndsAt, restSeconds: restSeconds)
    }

    // MARK: Actions

    /// Starts the hold timer; it logs the set by itself when the target time is up.
    func startHold() {
        guard current?.set.isTimed == true, holdStartedAt == nil else { return }
        skipRest()
        holdStartedAt = .now
        let seconds = draftSeconds
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        RestAlarm.schedule(at: .now.addingTimeInterval(TimeInterval(seconds)), title: "Hold done", next: nil)
        holdTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(seconds))
            guard !Task.isCancelled, let self else { return }
            // Logging cancels holdTask; drop the handle first so this task (and its upload) isn't cancelled.
            self.holdTask = nil
            RestAlarm.countdown(0)
            await self.logCurrentSet(seconds: seconds)
        }
    }

    /// Stops early and logs the time held so far.
    func stopHold() async {
        guard let holdStartedAt else { return }
        let held = min(draftSeconds, Int(Date.now.timeIntervalSince(holdStartedAt).rounded()))
        await logCurrentSet(seconds: held)
    }

    func logCurrentSet(seconds: Int? = nil) async {
        guard var session, let set = current?.set else { return }
        holdTask?.cancel()
        holdTask = nil
        holdStartedAt = nil
        let held = set.isTimed ? seconds ?? draftSeconds : nil
        let reps = set.isTimed ? 1 : draftReps
        let weight = draftWeight
        let effort = draftEffort
        let label = current.map { StrengthLogic.label(for: set, in: $0.exercise) } ?? "Set"
        session = StrengthLogic.complete(session, setId: set.id, reps: reps, weightKg: weight, effort: effort, seconds: held)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        lastLogged = LoggedSet(setId: set.id, label: label, load: StrengthFormat.load(weight: weight, reps: reps, seconds: held))
        restSeconds = set.restSeconds
        restEndsAt = .now.addingTimeInterval(TimeInterval(set.restSeconds))
        show(session, logged: set.id)
        resetDrafts()
        if let restEndsAt, let next = current, !allSetsDone {
            let load = StrengthFormat.load(weight: draftWeight, reps: draftReps, seconds: next.set.isTimed ? draftSeconds : nil)
            RestAlarm.schedule(at: restEndsAt, next: "\(next.exercise.exerciseName) · \(load)")
        } else {
            RestAlarm.cancel()
        }

        let base = "/strength/workouts/sessions/\(session.id)/sets/\(set.id)"
        let completion = StrengthSetCompletion(actualReps: reps, actualWeightKg: weight, actualSeconds: held)
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

    func toggleRampStep(_ index: Int) {
        if rampTicks.contains(index) { rampTicks.remove(index) } else { rampTicks.insert(index) }
    }

    /// Warm-up done or skipped: the set card comes back.
    func finishRamp() {
        guard let ramp, let session else { return }
        rampDone.insert(ramp.exercise.id)
        rampTicks = []
        if !isDemo { UserDefaults.standard.set(Array(rampDone), forKey: Self.rampKey(session.id)) }
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

    /// 5 s steps, 5 s to 30 min; locked while the timer runs.
    func adjustSeconds(by delta: Int) {
        guard holdStartedAt == nil else { return }
        draftSeconds = min(1800, max(5, draftSeconds + delta))
    }

    /// "Add weight" on a bodyweight lift: starts at 5 kg (a backpack or a vest).
    func addWeight() {
        draftWeight = 5
    }

    func finish() async {
        guard let session, !finishing else { return }
        finishing = true
        defer { finishing = false }
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/\(session.id)/finish", body: Data("{}".utf8)))
        onEnd?(.finish)
        await close()
        phase = .summary(SummaryLogic.local(session))
        if !unsynced { await loadSummary(of: session) }
    }

    /// The server's recap: last time, new bests and next targets. Keeps the local one if it fails.
    private func loadSummary(of session: StrengthSession) async {
        guard let summary = try? await client().getLive(
            "/strength/workouts/sessions/\(session.id)/summary", as: StrengthSummary.self
        ) else { return }
        if case .summary = phase { phase = .summary(summary) }
    }

    /// Done on the recap.
    func dismissSummary() {
        phase = .closed
    }

    func abandon() async {
        guard let session else { return }
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/\(session.id)/abandon", body: nil))
        onEnd?(.discard)
        await close()
        phase = .closed
    }

    private func close() async {
        store.clear()
        RestAlarm.cancel()
        StrengthActivity.end()
        // Flush before closing so Today's reload doesn't still see the workout as open.
        unsynced = !(await queue.flush(with: client()))
    }

    /// Picks up sets logged on the web while this screen is open. Skipped while this phone has
    /// writes the server hasn't seen, and dropped if one started while the request was out.
    func refresh() async {
        guard !isDemo else { return }
        let started = edits
        guard phase == .ready, queue.pending.isEmpty, let id = session?.id,
              let live = try? await client().getLive("/strength/workouts/sessions/\(id)", as: StrengthSession.self),
              edits == started, phase == .ready, queue.pending.isEmpty, live != session
        else { return }
        if live.isActive {
            show(live)
        } else {
            // Finished or discarded on the web.
            endedElsewhere(finished: live.status == "completed")
        }
    }

    /// Replays queued writes, then trusts the server's copy (its progression and position).
    private func sync() async {
        edits += 1
        guard !isDemo else { return }
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

    #if DEBUG
    /// A canned workout for simulator screenshots (`StrengthDemo`).
    func applyDemo(session: StrengthSession, history: [LiftHistory], kit: GymKit, hints: [String: String], rampDone: Set<Int>, ticks: Set<Int>) {
        isDemo = true
        self.history = Dictionary(history.map { ($0.exerciseName, $0) }, uniquingKeysWith: { first, _ in first })
        self.kit = kit
        self.hints = hints
        self.rampDone = rampDone
        rampTicks = ticks
        self.session = session
        resetDrafts()
        phase = .ready
    }
    #endif

    private func resetDrafts() {
        guard let session, let current = StrengthLogic.current(in: session) else { return }
        holdTask?.cancel()
        holdTask = nil
        holdStartedAt = nil
        draftWeight = StrengthLogic.carriedWeight(for: current.set, in: current.exercise)
        draftReps = current.set.targetReps
        draftSeconds = current.set.targetSeconds ?? 0
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
    let actualSeconds: Int?
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
