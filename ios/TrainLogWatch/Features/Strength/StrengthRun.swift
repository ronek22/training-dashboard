import Foundation
import Observation
import WatchKit

/// One strength session on the wrist: set → effort → rest → next set. The Watch's copy of the
/// session is the truth while it runs; every change is applied here first (`StrengthLogic`, same
/// rules as the phone) and sent to the server through the iPhone's write queue.
@MainActor
@Observable
final class StrengthRun {
    enum Stage: Equatable {
        case set
        /// The set just logged waits for Easy · Good · Hard; the rest timer already runs.
        case effort(setId: Int)
        case rest
        /// Every set is done; the summary's waiting for Finish.
        case allDone
    }

    enum Field { case weight, reps }

    private(set) var session: StrengthSession
    private(set) var stage: Stage = .set
    var focus: Field = .weight
    private(set) var draftWeight: Double?
    private(set) var draftReps = 0
    private(set) var draftSeconds = 0
    /// The hold timer is running since this moment.
    private(set) var holdStartedAt: Date?
    private(set) var restEndsAt: Date?
    private(set) var restTotal = 0
    /// "Set 2 · 34 × 10": what the effort screen asks about.
    private(set) var lastLogged: String?
    /// Last session's heaviest set per lift, from the template.
    private(set) var lastByName: [String: StrengthTemplate.Last] = [:]
    private(set) var addingSet = false

    private let link: PhoneLink
    private let store: RunStore
    private var restTask: Task<Void, Never>?
    private var effortTask: Task<Void, Never>?
    private var holdTask: Task<Void, Never>?

    init(session: StrengthSession, link: PhoneLink = .shared, store: RunStore = RunStore()) {
        self.session = session
        self.link = link
        self.store = store
        store.save(session)
        resetDrafts()
        if session.exercises.allSatisfy(\.isDone) { stage = .allDone }
    }

    // MARK: Derived

    var current: (exercise: StrengthSession.Exercise, set: StrengthSession.WorkoutSet)? {
        StrengthLogic.current(in: session)
    }

    var kicker: String {
        guard let current else { return session.templateName }
        return WatchStrength.kicker(session, exercise: current.exercise, set: current.set)
    }

    var totals: WatchStrength.Totals { WatchStrength.totals(session) }

    var last: StrengthTemplate.Last? {
        current.flatMap { lastByName[$0.exercise.exerciseName] }
    }

    /// What comes after the rest: "Set 3 · 34 × 10", or the next lift's name.
    var upNext: String? {
        guard let current, !session.exercises.allSatisfy(\.isDone) else { return nil }
        let load = StrengthFormat.load(weight: draftWeight, reps: draftReps, seconds: current.set.isTimed ? draftSeconds : nil)
        let label = StrengthLogic.label(for: current.set, in: current.exercise)
        return current.exercise.id == justLoggedExercise ? "\(label) · \(load)" : "\(current.exercise.exerciseName) · \(load)"
    }

    private var justLoggedExercise: Int?

    // MARK: Loading

    /// The "vs last" numbers on the set screen.
    func loadHistory() async {
        #if DEBUG
        if WatchDemo.enabled {
            lastByName = WatchDemo.last
            return
        }
        #endif
        guard lastByName.isEmpty, let templateId = session.templateId,
              let template = try? await WatchAPI.get("/strength/workouts/templates/\(templateId)", as: StrengthTemplate.self)
        else { return }
        lastByName = Dictionary(
            template.value.exercises.compactMap { exercise in exercise.next?.last.map { (exercise.exerciseName, $0) } },
            uniquingKeysWith: { first, _ in first }
        )
    }

    // MARK: Editing the set

    /// One crown detent on the focused field: 0.5 kg or 1 rep (5 s on a hold).
    func turn(_ steps: Int) {
        guard steps != 0, holdStartedAt == nil else { return }
        if current?.set.isTimed == true {
            draftSeconds = min(1800, max(5, draftSeconds + steps * 5))
            return
        }
        switch focus {
        case .weight: draftWeight = StrengthLogic.step(draftWeight, by: steps)
        case .reps: draftReps = min(100, max(0, draftReps + steps))
        }
    }

    // MARK: Logging

    func logSet(seconds: Int? = nil) {
        guard let current else { return }
        holdTask?.cancel()
        holdTask = nil
        holdStartedAt = nil
        let set = current.set
        let held = set.isTimed ? seconds ?? draftSeconds : nil
        let reps = set.isTimed ? 1 : draftReps
        let weight = draftWeight
        let label = StrengthLogic.label(for: set, in: current.exercise)
        session = StrengthLogic.complete(session, setId: set.id, reps: reps, weightKg: weight, effort: nil, seconds: held)
        store.save(session)
        justLoggedExercise = current.exercise.id
        lastLogged = "\(label) · " + StrengthFormat.load(weight: weight, reps: reps, seconds: held)
        WKInterfaceDevice.current().play(.success)

        let body = try? WatchAPI.encoder.encode(Completion(actualReps: reps, actualWeightKg: weight, actualSeconds: held))
        link.enqueue("POST", "/strength/workouts/sessions/\(session.id)/sets/\(set.id)/complete", body: body)

        resetDrafts()
        startRest(set.restSeconds)
        stage = .effort(setId: set.id)
        // Not tapping keeps the set without an effort, like skipping it on the phone.
        effortTask?.cancel()
        effortTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(10))
            guard !Task.isCancelled else { return }
            self?.rate(nil)
        }
    }

    func rate(_ effort: SetEffort?) {
        guard case .effort(let setId) = stage else { return }
        effortTask?.cancel()
        effortTask = nil
        if let effort {
            if let index = session.exercises.firstIndex(where: { $0.sets.contains { $0.id == setId } }),
               let setIndex = session.exercises[index].sets.firstIndex(where: { $0.id == setId }) {
                session.exercises[index].sets[setIndex].effort = effort.rawValue
                store.save(session)
            }
            let body = try? WatchAPI.encoder.encode(["effort": effort.rawValue])
            link.enqueue("PUT", "/strength/workouts/sessions/\(session.id)/sets/\(setId)/effort", body: body)
            WKInterfaceDevice.current().play(.click)
        }
        if session.exercises.allSatisfy(\.isDone) {
            skipRest()
            stage = .allDone
        } else {
            stage = restEndsAt == nil ? .set : .rest
        }
    }

    // MARK: Holds

    func startHold() {
        guard current?.set.isTimed == true, holdStartedAt == nil else { return }
        skipRest()
        holdStartedAt = .now
        let seconds = draftSeconds
        WKInterfaceDevice.current().play(.start)
        holdTask = Task { [weak self] in
            if seconds > 10 {
                try? await Task.sleep(for: .seconds(seconds - 10))
                guard !Task.isCancelled else { return }
                WKInterfaceDevice.current().play(.click)
                try? await Task.sleep(for: .seconds(10))
            } else {
                try? await Task.sleep(for: .seconds(seconds))
            }
            guard !Task.isCancelled, let self else { return }
            WKInterfaceDevice.current().play(.stop)
            self.holdTask = nil
            self.logSet(seconds: seconds)
        }
    }

    func stopHold() {
        guard let holdStartedAt else { return }
        logSet(seconds: min(draftSeconds, Int(Date.now.timeIntervalSince(holdStartedAt).rounded())))
    }

    // MARK: Rest

    private func startRest(_ seconds: Int) {
        restTask?.cancel()
        guard seconds > 0 else {
            restEndsAt = nil
            return
        }
        restTotal = seconds
        let ends = Date.now.addingTimeInterval(TimeInterval(seconds))
        restEndsAt = ends
        scheduleRestEnd(ends)
    }

    func addRest(_ seconds: Int) {
        guard let restEndsAt else { return }
        let ends = restEndsAt.addingTimeInterval(TimeInterval(seconds))
        self.restEndsAt = ends
        restTotal += seconds
        scheduleRestEnd(ends)
    }

    func skipRest() {
        restTask?.cancel()
        restTask = nil
        restEndsAt = nil
        if stage == .rest { stage = .set }
    }

    /// The app keeps running while the workout does, so a plain task fires on time, wrist down too.
    private func scheduleRestEnd(_ ends: Date) {
        restTask?.cancel()
        restTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(0, ends.timeIntervalSinceNow)))
            guard !Task.isCancelled, let self else { return }
            // Three taps: time to lift.
            for _ in 0..<3 {
                WKInterfaceDevice.current().play(.notification)
                try? await Task.sleep(for: .milliseconds(450))
            }
            self.restEndsAt = nil
            self.restTask = nil
            if self.stage == .rest { self.stage = .set }
        }
    }

    // MARK: Moving around

    func jump(to exercise: StrengthSession.Exercise) {
        guard session.isActive else { return }
        let setOrder = WatchStrength.jumpTarget(exercise)
        session.currentExerciseOrder = exercise.exerciseOrder
        session.currentSetOrder = setOrder
        store.save(session)
        resetDrafts()
        if stage == .allDone, !exercise.isDone { stage = .set }
        let body = try? WatchAPI.encoder.encode(["exercise_order": exercise.exerciseOrder, "set_order": setOrder])
        link.enqueue("POST", "/strength/workouts/sessions/\(session.id)/position", body: body)
    }

    func skipExercise() {
        guard let current, let next = WatchStrength.nextExercise(after: current.exercise, in: session) else { return }
        jump(to: next)
    }

    /// One more working set of the current lift. Needs the server's answer (the set's id).
    func addSet() async -> String? {
        guard let exercise = current?.exercise ?? session.exercises.last, !addingSet else { return nil }
        addingSet = true
        defer { addingSet = false }
        do {
            await link.flush()
            let updated = try await WatchAPI.send("POST", "/strength/workouts/sessions/\(session.id)/exercises/\(exercise.id)/sets", as: StrengthSession.self)
            session = updated
            store.save(updated)
            if stage == .allDone { stage = .set }
            resetDrafts()
            return nil
        } catch {
            return error.localizedDescription
        }
    }

    // MARK: Ending

    func finish() {
        link.enqueue("POST", "/strength/workouts/sessions/\(session.id)/finish", body: Data("{}".utf8))
        close()
    }

    func discard() {
        link.enqueue("POST", "/strength/workouts/sessions/\(session.id)/abandon")
        close()
    }

    private func close() {
        restTask?.cancel()
        effortTask?.cancel()
        holdTask?.cancel()
        store.clear()
    }

    #if DEBUG
    /// Puts the demo on one screen for a screenshot.
    func demo(_ stage: String) {
        switch stage {
        case "effort":
            logSet()
            effortTask?.cancel()
        case "rest":
            logSet()
            rate(nil)
        case "done":
            while let current, !session.exercises.allSatisfy(\.isDone) {
                session = StrengthLogic.complete(session, setId: current.set.id, reps: current.set.targetReps,
                                                 weightKg: current.set.targetWeightKg, effort: .solid,
                                                 seconds: current.set.targetSeconds)
            }
            self.stage = .allDone
        default: break
        }
    }
    #endif

    private func resetDrafts() {
        guard let current else { return }
        holdTask?.cancel()
        holdTask = nil
        holdStartedAt = nil
        draftWeight = StrengthLogic.carriedWeight(for: current.set, in: current.exercise)
        draftReps = current.set.targetReps
        draftSeconds = current.set.targetSeconds ?? 0
        focus = .weight
    }
}

private struct Completion: Encodable {
    let actualReps: Int
    let actualWeightKg: Double?
    let actualSeconds: Int?
}

/// The running session on the Watch's disk, so a relaunch mid-workout carries on.
struct RunStore: Sendable {
    var file: URL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appending(path: RunStore.fileName)

    #if DEBUG
    /// The demo never leaves a session behind for a real launch to resume.
    private static var fileName: String { WatchDemo.enabled ? "watch-demo-session.json" : "watch-strength-session.json" }
    #else
    private static let fileName = "watch-strength-session.json"
    #endif

    func load() -> StrengthSession? {
        (try? Data(contentsOf: file)).flatMap { try? JSONDecoder.snakeCase.decode(StrengthSession.self, from: $0) }
    }

    func save(_ session: StrengthSession) {
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? JSONEncoder.snakeCase.encode(session).write(to: file, options: .atomic)
    }

    func clear() {
        try? FileManager.default.removeItem(at: file)
    }
}
