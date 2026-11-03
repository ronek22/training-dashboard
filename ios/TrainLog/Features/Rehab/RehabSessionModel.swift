import Foundation
import Observation
import UIKit

/// Follow-along rehab, the phone side of the web's `/guided/rehab`: straight sets, one step at a
/// time. Holds and rests count down and move on by themselves; rep steps wait for Done. Passing an
/// exercise's last step ticks it on the Recovery routine, and finishing saves the session so the
/// Watch workout that syncs for it is labelled as rehab. Writes queue when the Mac is unreachable.
///
/// When the routine runs in TrainLog on the Watch, the phone follows it instead (`follow`): the
/// Watch keeps the timers and sends the ticks and the completion; the buttons here steer it.
/// Started here, it's the other way round: every change goes to `onChange` for the Watch to show,
/// and the Watch's buttons come back through `handle`.
@MainActor
@Observable
final class RehabSessionModel {
    enum Phase: Equatable {
        case loading
        case intro
        case running
        case done
        /// Every exercise due today is already ticked.
        case empty
        case failed(String)
    }

    enum SaveState: Equatable {
        case idle, saving, saved, queued, failed
    }

    private(set) var phase: Phase = .loading
    private(set) var session: GuidedSession?
    private(set) var steps: [RehabStep] = []
    private(set) var index = 0
    /// When the current timed step ends; nil on rep steps and while paused.
    private(set) var endsAt: Date?
    /// Seconds left on a paused timed step.
    private(set) var pausedLeft: Int?
    private(set) var startedAt: Date?
    private(set) var finishedAt: Date?
    private(set) var saveState: SaveState = .idle
    /// Pain after the session, per issue id.
    private(set) var pain: [Int: Int] = [:]
    /// Mirroring the routine running on the Watch.
    private(set) var following = false
    /// Sends a button press to the Watch while following.
    var remote: ((WatchWire.Command) -> Void)?
    /// Where the routine is now, for the Watch while it runs here.
    var onChange: ((WatchWire.Rehab) -> Void)?
    /// The routine as JSON, sent to the Watch with the first update.
    private var sessionData: Data?

    private var ticked: Set<RehabStep.Completes> = []
    /// The last write sent; each new one waits for it, so ticks land before the completion.
    private var lastWrite: Task<SaveState, Never>?
    private let client: () -> APIClient
    private let queue: WriteQueue
    private let today: String

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), today: String = PlanModel.todayISO) {
        self.client = client
        self.queue = queue
        self.today = today
    }

    var current: RehabStep? { steps.indices.contains(index) ? steps[index] : nil }

    /// The next exercise step, skipping rests.
    var upNext: RehabStep? {
        steps.dropFirst(index + 1).first { $0.kind == .exercise }
    }

    var progress: Double {
        if phase == .done { return 1 }
        return steps.isEmpty ? 0 : Double(index) / Double(steps.count)
    }

    /// Issues worked today, for the pain check at the end.
    var issues: [(id: Int, title: String)] {
        var seen = Set<Int>()
        return (session?.exercises ?? []).compactMap { exercise in
            guard let id = exercise.issueId, seen.insert(id).inserted else { return nil }
            return (id, exercise.issueTitle ?? "Rehab")
        }
    }

    // MARK: Loading

    func load() async {
        let api = client()
        await queue.flush(with: api)
        let result: Result<GuidedSession, Error>
        do {
            result = .success(try await api.getLive("/guided-sessions/rehab", as: GuidedSessionEnvelope.self).session)
        } catch {
            result = .failure(error)
        }
        // The Watch's routine showed up meanwhile: it wins.
        guard !following else { return }
        switch result {
        case .success(let loaded): prepare(loaded)
        case .failure(APIError.status(404)): phase = .empty
        case .failure(let error): phase = .failed(error.localizedDescription)
        }
    }

    func prepare(_ loaded: GuidedSession) {
        session = loaded
        steps = RehabFormat.steps(loaded)
        phase = steps.isEmpty ? .empty : .intro
    }

    // MARK: Following the Watch

    /// The Watch's routine moved (or the phone just attached). The first call needs the Watch's
    /// copy of the routine, so the steps line up with its index.
    func follow(_ state: WatchWire.Rehab, session loaded: GuidedSession?) {
        if !following {
            guard let loaded else { return }
            session = loaded
            steps = RehabFormat.steps(loaded)
            following = true
        }
        guard !steps.isEmpty else { return }
        startedAt = state.startedAt
        index = min(max(0, state.index), steps.count - 1)
        endsAt = state.endsAt
        pausedLeft = state.pausedLeft
        if state.finished {
            if phase != .done { finishedAt = .now }
            phase = .done
            saveState = .saved
        } else {
            phase = .running
        }
    }

    // MARK: Running

    func start() {
        startedAt = .now
        phase = .running
        sessionData = session.flatMap { try? JSONEncoder().encode($0) }
        begin(0)
        Haptics.thud()
        publish(withSession: true)
    }

    /// A button pressed on the Watch, while the routine runs here.
    func handle(_ command: WatchWire.Command) {
        guard !following else { return }
        // Start on the Watch's ready screen starts it here, for both.
        if command == .start, phase == .intro { return start() }
        guard phase == .running else { return }
        switch command {
        case .start: break
        case .next: next()
        case .back: back()
        case .pause: togglePause()
        case .finish: finish()
        case .discard: Task { await discard() }
        case .sync: publish(withSession: true)
        }
    }

    private func publish(withSession: Bool = false, discarded: Bool = false) {
        guard !following, let startedAt else { return }
        onChange?(WatchWire.Rehab(
            session: withSession ? sessionData : nil, startedAt: startedAt, index: index, endsAt: endsAt,
            pausedLeft: pausedLeft, finished: phase == .done, discarded: discarded
        ))
    }

    /// Done on a rep step, or ends a timed one early.
    func next() {
        if following {
            remote?(.next)
            return
        }
        guard let step = current else { return }
        if let completes = step.completes { tick(completes) }
        if index + 1 >= steps.count {
            finish()
        } else {
            begin(index + 1)
            Haptics.tick()
        }
    }

    /// The timer of step `stepIndex` ran out. Ignored when the step already moved on.
    func timerEnded(_ stepIndex: Int) {
        guard !following, phase == .running, stepIndex == index, let endsAt, endsAt <= .now else { return }
        next()
    }

    func back() {
        if following {
            remote?(.back)
            return
        }
        guard index > 0 else { return }
        begin(index - 1)
    }

    func togglePause() {
        if following {
            remote?(.pause)
            return
        }
        if let left = pausedLeft {
            endsAt = .now.addingTimeInterval(TimeInterval(left))
            pausedLeft = nil
        } else if let endsAt {
            pausedLeft = max(1, Int(endsAt.timeIntervalSinceNow.rounded(.up)))
            self.endsAt = nil
            RestAlarm.cancel()
        }
        publish()
    }

    /// Books the "time's up" notification while the phone is locked mid-timer.
    func scheduleAlarm() {
        // Following: the Watch taps the wrist when the timer's up.
        guard !following, phase == .running, let endsAt, let step = current else { return }
        let title = step.kind == .rest ? "Rest over · go" : "Hold done"
        RestAlarm.schedule(at: endsAt, title: title, next: upNext.map { "Next: \($0.name)" })
    }

    private func begin(_ stepIndex: Int) {
        index = stepIndex
        pausedLeft = nil
        endsAt = steps[stepIndex].seconds.map { .now.addingTimeInterval(TimeInterval($0)) }
        publish()
    }

    private func tick(_ completes: RehabStep.Completes) {
        guard ticked.insert(completes).inserted else { return }
        let body = try? APIClient.encoder.encode(RehabTick(day: today, index: completes.index, done: true))
        enqueue(.init(method: "PUT", path: "/recovery/issues/\(completes.issueId)/ticks", body: body))
    }

    // MARK: Finishing

    /// Leaving without saving: unticks what this session ticked, after the ticks themselves went out.
    func discard() async {
        endsAt = nil
        pausedLeft = nil
        RestAlarm.cancel()
        for completes in ticked {
            let body = try? APIClient.encoder.encode(RehabTick(day: today, index: completes.index, done: false))
            enqueue(.init(method: "PUT", path: "/recovery/issues/\(completes.issueId)/ticks", body: body))
        }
        ticked = []
        publish(discarded: true)
        _ = await lastWrite?.value
    }

    func finish() {
        guard let startedAt else { return }
        finishedAt = .now
        endsAt = nil
        pausedLeft = nil
        phase = .done
        RestAlarm.cancel()
        Reminders.note { $0.rehabLeft = 0 }
        Haptics.success()
        let completion = GuidedCompletion(
            sessionKey: session?.key ?? "rehab",
            startedAt: ISO8601DateFormatter().string(from: startedAt),
            elapsedSeconds: Int(Date.now.timeIntervalSince(startedAt)),
            completedSteps: steps.count
        )
        let body = try? APIClient.encoder.encode(completion)
        saveState = .saving
        // The server snapshots what was ticked today, so this goes after the ticks.
        let write = enqueue(.init(method: "POST", path: "/guided-sessions/complete", body: body))
        Task { saveState = await write.value }
        publish()
    }

    func checkIn(issueId: Int, pain value: Int) async {
        pain[issueId] = value
        let body = try? APIClient.encoder.encode(RecoveryCheckin(pain: value, didPlan: true, note: "Rehab routine done (guided on iPhone)"))
        _ = await enqueue(.init(method: "POST", path: "/recovery/issues/\(issueId)/checkins", body: body)).value
    }

    @discardableResult
    private func enqueue(_ write: WriteQueue.Write) -> Task<SaveState, Never> {
        let previous = lastWrite
        let task = Task { _ = await previous?.value; return await send(write) }
        lastWrite = task
        return task
    }

    /// Tries the write now; queues it behind anything already waiting when the Mac is unreachable.
    private func send(_ write: WriteQueue.Write) async -> SaveState {
        let api = client()
        if !queue.pending.isEmpty {
            queue.append(write)
            return await queue.flush(with: api) ? .saved : .queued
        }
        do {
            try await api.send(write.method, write.path, body: write.body)
            return .saved
        } catch APIError.unreachable {
            queue.append(write)
            return .queued
        } catch {
            return .failed
        }
    }
}
