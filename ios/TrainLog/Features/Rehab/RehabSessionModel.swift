import Foundation
import Observation
import UIKit

/// Follow-along rehab, the phone side of the web's `/guided/rehab`: straight sets, one step at a
/// time. Holds and rests count down and move on by themselves; rep steps wait for Done. Passing an
/// exercise's last step ticks it on the Recovery routine, and finishing saves the session so the
/// Watch workout that syncs for it is labelled as rehab. Writes queue when the Mac is unreachable.
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
        do {
            prepare(try await api.getLive("/guided-sessions/rehab", as: GuidedSessionEnvelope.self).session)
        } catch APIError.status(404) {
            phase = .empty
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func prepare(_ loaded: GuidedSession) {
        session = loaded
        steps = RehabFormat.steps(loaded)
        phase = steps.isEmpty ? .empty : .intro
    }

    // MARK: Running

    func start() {
        startedAt = .now
        phase = .running
        begin(0)
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    /// Done on a rep step, or ends a timed one early.
    func next() {
        guard let step = current else { return }
        if let completes = step.completes { tick(completes) }
        if index + 1 >= steps.count {
            finish()
        } else {
            begin(index + 1)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
    }

    /// The timer of step `stepIndex` ran out. Ignored when the step already moved on.
    func timerEnded(_ stepIndex: Int) {
        guard phase == .running, stepIndex == index, let endsAt, endsAt <= .now else { return }
        next()
    }

    func back() {
        guard index > 0 else { return }
        begin(index - 1)
    }

    func togglePause() {
        if let left = pausedLeft {
            endsAt = .now.addingTimeInterval(TimeInterval(left))
            pausedLeft = nil
        } else if let endsAt {
            pausedLeft = max(1, Int(endsAt.timeIntervalSinceNow.rounded(.up)))
            self.endsAt = nil
            RestAlarm.cancel()
        }
    }

    /// Books the "time's up" notification while the phone is locked mid-timer.
    func scheduleAlarm() {
        guard phase == .running, let endsAt, let step = current else { return }
        let title = step.kind == .rest ? "Rest over · go" : "Hold done"
        RestAlarm.schedule(at: endsAt, title: title, next: upNext.map { "Next: \($0.name)" })
    }

    private func begin(_ stepIndex: Int) {
        index = stepIndex
        pausedLeft = nil
        endsAt = steps[stepIndex].seconds.map { .now.addingTimeInterval(TimeInterval($0)) }
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
        UINotificationFeedbackGenerator().notificationOccurred(.success)
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
