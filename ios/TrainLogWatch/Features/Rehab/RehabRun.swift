import Foundation
import Observation
import WatchKit

/// Today's rehab routine on the wrist: the phone's step list (`RehabFormat.steps`), holds and rests
/// that count themselves, ticks sent as each exercise is passed. Every change goes to `onChange`, so
/// the phone can follow along; the phone's buttons come back through `handle`.
///
/// Started on the phone, it follows instead (`following`): the phone runs the timers and sends the
/// ticks and the completion, `apply` moves this screen, and the buttons here go to `onCommand`.
/// The wrist still taps at 10 s left and at the end of each hold or rest.
@MainActor
@Observable
final class RehabRun {
    let session: GuidedSession
    let steps: [RehabStep]
    private(set) var index = 0
    private(set) var endsAt: Date?
    private(set) var pausedLeft: Int?
    private(set) var startedAt = Date.now
    private(set) var finished = false
    private(set) var discarded = false
    /// The phone discarded the routine it runs.
    private(set) var discardedOnPhone = false
    /// The routine runs on the phone; this screen mirrors it.
    let following: Bool
    /// Where the routine is now, for the phone (`WatchWire.Rehab`).
    var onChange: ((WatchWire.Rehab) -> Void)?
    /// A button pressed here, for the phone running the routine.
    var onCommand: ((WatchWire.Command) -> Void)?

    private var ticked: Set<RehabStep.Completes> = []
    private var timer: Task<Void, Never>?
    private let link: PhoneLink
    private let today: String
    /// The routine as JSON, sent with the first update and when the phone asks again.
    private let sessionData: Data?

    init(session: GuidedSession, following: Bool = false, link: PhoneLink = .shared, today: Date = .now) {
        self.session = session
        self.following = following
        self.steps = RehabFormat.steps(session)
        self.sessionData = try? JSONEncoder().encode(session)
        self.link = link
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        self.today = formatter.string(from: today)
    }

    var current: RehabStep? { steps.indices.contains(index) ? steps[index] : nil }

    var upNext: String? {
        guard let current, steps.indices.contains(index + 1) else { return nil }
        return RehabFormat.upNext(steps[index + 1], after: current)
    }

    /// Exercises (not rests) passed, for the segmented bar.
    var progress: Double { steps.isEmpty ? 1 : Double(index) / Double(steps.count) }

    func start() {
        guard !following else { return }
        startedAt = .now
        begin(0)
        WKInterfaceDevice.current().play(.start)
        publish(withSession: true)
    }

    /// A button pressed on the phone.
    func handle(_ command: WatchWire.Command) {
        guard !following, !finished, !discarded else { return }
        switch command {
        case .next: next()
        case .back: back()
        case .pause: togglePause()
        case .sync: publish(withSession: true)
        case .finish, .discard: break
        }
    }

    /// The phone's routine moved. Timers here only tap the wrist; the phone moves on.
    func apply(_ state: WatchWire.Rehab) {
        guard following, !finished, !discarded else { return }
        if state.discarded {
            timer?.cancel()
            discardedOnPhone = true
            return
        }
        startedAt = state.startedAt
        let moved = state.index != index
        index = steps.isEmpty ? 0 : min(max(0, state.index), steps.count - 1)
        pausedLeft = state.pausedLeft
        timer?.cancel()
        endsAt = nil
        if let ends = state.endsAt { schedule(ends) }
        if state.finished {
            timer?.cancel()
            endsAt = nil
            finished = true
            WKInterfaceDevice.current().play(.success)
        } else if moved {
            WKInterfaceDevice.current().play(.click)
        }
    }

    private func publish(withSession: Bool = false) {
        guard !following else { return }
        onChange?(WatchWire.Rehab(
            session: withSession ? sessionData : nil, startedAt: startedAt, index: index,
            endsAt: endsAt, pausedLeft: pausedLeft, finished: finished, discarded: discarded
        ))
    }

    /// Done on a rep step, or ends a timed one early.
    func next() {
        if following {
            onCommand?(.next)
            return
        }
        guard let step = current else { return }
        if let completes = step.completes, ticked.insert(completes).inserted {
            let body = try? WatchAPI.encoder.encode(Tick(day: today, index: completes.index, done: true))
            link.enqueue("PUT", "/recovery/issues/\(completes.issueId)/ticks", body: body)
        }
        if index + 1 >= steps.count {
            finish()
        } else {
            begin(index + 1)
        }
    }

    func back() {
        if following {
            onCommand?(.back)
            return
        }
        guard index > 0 else { return }
        begin(index - 1)
    }

    func togglePause() {
        if following {
            onCommand?(.pause)
            return
        }
        if let left = pausedLeft {
            pausedLeft = nil
            schedule(Date.now.addingTimeInterval(TimeInterval(left)))
        } else if let endsAt {
            pausedLeft = max(1, Int(endsAt.timeIntervalSinceNow.rounded(.up)))
            self.endsAt = nil
            timer?.cancel()
        }
        publish()
    }

    func finish() {
        guard !finished else { return }
        if following {
            // The phone saves it and sends the finished state back, which ends the workout here.
            onCommand?(.finish)
            return
        }
        timer?.cancel()
        endsAt = nil
        finished = true
        WKInterfaceDevice.current().play(.success)
        let completion = GuidedCompletion(
            sessionKey: session.key,
            startedAt: ISO8601DateFormatter().string(from: startedAt),
            elapsedSeconds: Int(Date.now.timeIntervalSince(startedAt)),
            completedSteps: index + 1
        )
        // The server snapshots what was ticked today, so this goes after the ticks (the outbox keeps order).
        link.enqueue("POST", "/guided-sessions/complete", body: try? WatchAPI.encoder.encode(completion))
        publish()
    }

    /// Leaving without saving: unticks what this session ticked.
    func discard() {
        timer?.cancel()
        if following {
            discarded = true
            onCommand?(.discard)
            return
        }
        for completes in ticked {
            let body = try? WatchAPI.encoder.encode(Tick(day: today, index: completes.index, done: false))
            link.enqueue("PUT", "/recovery/issues/\(completes.issueId)/ticks", body: body)
        }
        ticked = []
        discarded = true
        publish()
    }

    private func begin(_ stepIndex: Int) {
        index = stepIndex
        pausedLeft = nil
        timer?.cancel()
        endsAt = nil
        if let seconds = steps[stepIndex].seconds {
            schedule(Date.now.addingTimeInterval(TimeInterval(seconds)))
        }
        WKInterfaceDevice.current().play(.click)
        publish()
    }

    private func schedule(_ ends: Date) {
        endsAt = ends
        let step = index
        timer?.cancel()
        timer = Task { [weak self] in
            let left = ends.timeIntervalSinceNow
            if left > 10 {
                try? await Task.sleep(for: .seconds(left - 10))
                guard !Task.isCancelled else { return }
                WKInterfaceDevice.current().play(.click)
            }
            try? await Task.sleep(for: .seconds(max(0, ends.timeIntervalSinceNow)))
            guard !Task.isCancelled, let self, self.index == step, self.pausedLeft == nil else { return }
            WKInterfaceDevice.current().play(.stop)
            // Following: the phone moves on and tells this screen.
            if !self.following { self.next() }
        }
    }
}

private struct Tick: Encodable {
    let day: String
    let index: Int
    let done: Bool
}
