import HealthKit
import SwiftUI
import WatchKit

@main
struct TrainLogWatchApp: App {
    @WKApplicationDelegateAdaptor private var delegate: WatchAppDelegate

    init() {
        PhoneLink.shared.activate()
        #if DEBUG
        WatchDemo.seedWidgets()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            WatchRoot()
        }
    }
}

final class WatchAppDelegate: NSObject, WKApplicationDelegate {
    /// watchOS relaunches the app when it quit mid-workout; pick the HealthKit session back up.
    func handleActiveWorkoutRecovery() {
        Task { @MainActor in await WorkoutTracker.shared.recover() }
    }

    /// A workout opened on the iPhone woke the app (`HKHealthStore.startWatchApp`).
    func handle(_ workoutConfiguration: HKWorkoutConfiguration) {
        let activity = workoutConfiguration.activityType
        Task { @MainActor in await WorkoutTracker.shared.prepareFromPhone(activity) }
    }
}

/// Start screen → a running session → its summary. A workout opened on the phone wakes the app on
/// a ready screen (linked, nothing recording); Start on either device starts both.
struct WatchRoot: View {
    /// Whole screens swapped at the root: a running workout has no back button to slip out by.
    enum Screen: Hashable {
        case start
        /// A workout open on the phone, not started yet.
        case ready
        case strength
        case rehab
        case strengthSummary
        case rehabSummary
    }

    @State private var screen = Screen.start
    @State private var start = StartModel()
    @State private var run: StrengthRun?
    @State private var rehab: RehabRun?
    @State private var summary: WorkoutTracker.Summary?
    @State private var tracker = WorkoutTracker.shared
    @State private var link = PhoneLink.shared
    @State private var demoPage = StrengthScreen.Page.main
    /// A rehab routine the phone runs, and its exercises, as the phone sent them.
    @State private var phoneRehab: WatchWire.Rehab?
    @State private var phoneRoutine: GuidedSession?
    /// What the phone has open, for the ready screen.
    @State private var pending: WatchWire.Pending?
    /// Start pressed here; waiting for the phone to start it.
    @State private var startRequested = false
    /// The clock is starting; later copies from the phone go to the screen it opens.
    @State private var beginning = false
    /// Nothing came from the phone while the ready screen waited.
    @State private var readyFailed = false

    var body: some View {
        #if DEBUG
        if WatchDemo.enabled, let stage = WatchDemo.stage, stage.hasPrefix("widgets") {
            WidgetGalleryDemo(stage: stage)
        } else {
            root
        }
        #else
        root
        #endif
    }

    private var root: some View {
        NavigationStack {
            switch screen {
            case .start: StartView(model: start, onStrength: open, onRehab: open)
            case .ready:
                ReadyView(pending: pending, heartRate: tracker.heartRate, starting: startRequested, failed: readyFailed, onStart: {
                    startRequested = true
                    // Both ways: a second Start does nothing on the phone.
                    tracker.send(.start)
                    link.command(.start)
                    link.event("Start pressed")
                }, onRetry: {
                    Task { await askPhone() }
                }, onCancel: {
                    tracker.discard()
                    close()
                })
            default: destination(screen)
            }
        }
        .tint(.volt)
        .onChange(of: tracker.phoneStarts) { Task { await getReady() } }
        // A workout from the phone without the mirrored link: keep in step over WatchConnectivity.
        .task(id: screen) {
            guard screen == .strength || screen == .rehab else { return }
            while !Task.isCancelled, tracker.startedByPhone, !tracker.mirrored {
                if let live = await link.leading() { received(live) }
                try? await Task.sleep(for: .seconds(3))
            }
        }
        .task {
            tracker.onRemote = { received($0) }
            #if DEBUG
            if WatchDemo.enabled, let stage = WatchDemo.stage {
                if stage == "ready" {
                    pending = .init(kind: .strength, title: "Workout B", detail: "5 exercises · ~45 min")
                    screen = .ready
                    return
                }
                tracker.demo(heartRate: stage == "rest" ? 118 : 128, startedMinutesAgo: 18.7)
                let demo = StrengthRun(session: WatchDemo.session())
                await demo.loadHistory()
                demo.demo(stage)
                run = demo
                demoPage = stage == "list" ? .list : stage == "controls" ? .controls : .main
                screen = stage == "rehab" ? .start : .strength
                if stage == "rehab" { open(WatchDemo.rehab) }
                if stage == "summary" {
                    summary = .init(duration: 2770, averageHeartRate: 118, maxHeartRate: 156, activeKcal: 312, saved: true)
                    demo.demo("done")
                    screen = .strengthSummary
                }
                return
            }
            #endif
            // Relaunched mid-session: straight back into it, on the recovered HealthKit workout
            // rather than a new one.
            await tracker.recover()
            if screen == .start, let saved = RunStore().load(), saved.isActive {
                show(saved)
                if !tracker.running { await tracker.start(WatchWorkoutType.strength(templateId: saved.templateId)) }
            }
        }
    }

    @ViewBuilder
    private func destination(_ screen: Screen) -> some View {
        switch screen {
        case .start, .ready:
            EmptyView()
        case .strength:
            if let run {
                StrengthScreen(run: run, tracker: tracker, page: demoPage) { summary, _ in
                    self.summary = summary
                    self.screen = summary == nil ? .start : .strengthSummary
                }
            }
        case .rehab:
            if let rehab {
                RehabScreen(run: rehab, tracker: tracker) { summary in
                    self.summary = summary
                    self.screen = summary == nil ? .start : .rehabSummary
                }
            }
        case .strengthSummary:
            if let run {
                StrengthSummaryView(title: run.session.templateName, totals: run.totals, summary: summary,
                                    pendingWrites: link.pendingWrites, onDone: close)
            }
        case .rehabSummary:
            if let rehab {
                RehabSummaryView(title: rehab.session.title, steps: rehab.steps.count, summary: summary, onDone: close)
            }
        }
    }

    // MARK: Opening

    private func open(_ session: StrengthSession) {
        show(session)
        #if DEBUG
        if WatchDemo.enabled {
            tracker.demo(heartRate: 128, startedMinutesAgo: 0)
            return
        }
        #endif
        Task { await tracker.start(WatchWorkoutType.strength(templateId: session.templateId)) }
    }

    /// The strength screen for `session`; changes go to the phone's screen when it shows the same one.
    private func show(_ session: StrengthSession) {
        let strength = StrengthRun(session: session)
        strength.onShare = { [tracker] in tracker.share(strength: $0) }
        strength.onEnd = { [tracker, link] command in
            // Both ways: closing twice does nothing on the phone.
            tracker.send(command)
            link.command(command)
        }
        run = strength
        screen = .strength
    }

    private func open(_ session: GuidedSession) {
        let routine = RehabRun(session: session)
        // The phone follows along and can press Next, Back and Pause.
        routine.onChange = { [tracker] in tracker.share(rehab: $0) }
        rehab = routine
        screen = .rehab
        #if DEBUG
        if WatchDemo.enabled {
            tracker.demo(heartRate: 96, startedMinutesAgo: 4)
            return
        }
        #endif
        Task { await tracker.start(WatchWorkoutType.rehab(session.watchWorkout)) }
    }

    /// A rehab routine running on the phone: this screen mirrors it and steers it.
    private func follow(_ session: GuidedSession, at state: WatchWire.Rehab) {
        let routine = RehabRun(session: session, following: true)
        // One way only: Next twice would skip a step.
        routine.onCommand = { [tracker, link] command in
            if tracker.mirrored { tracker.send(command) } else { link.command(command) }
        }
        routine.apply(state)
        rehab = routine
        screen = .rehab
    }

    // MARK: Opened on the phone

    /// The phone opened a workout and woke this app: show the ready screen and ask the phone what
    /// it has open (repeated until it answers, since the link takes a moment to come up).
    private func getReady() async {
        guard screen == .start else { return }
        pending = nil
        startRequested = false
        screen = .ready
        link.event("Woken by iPhone")
        await askPhone()
    }

    /// Asks the phone what it has open, over the mirrored link and WatchConnectivity both, until
    /// it starts (the first update opens the screen) or 45 s pass without an answer.
    private func askPhone() async {
        readyFailed = false
        var heard = pending != nil
        for _ in 0..<45 where screen == .ready {
            tracker.send(.sync)
            if let live = await link.leading() { received(live) }
            if !heard, pending != nil {
                heard = true
                link.event("Got the workout from iPhone")
            }
            try? await Task.sleep(for: .seconds(1))
        }
        guard screen == .ready, pending == nil else { return }
        readyFailed = true
        link.event("Nothing from iPhone after 45 s")
    }

    /// The phone started the workout (Start on either device), or it was already running there:
    /// the clock starts here too and the same screen opens.
    private func begin(_ open: @escaping () -> Void) {
        guard screen == .ready, !beginning else { return }
        beginning = true
        Task {
            await tracker.begin()
            link.event(tracker.mirrored ? "Recording started" : "Recording started, without the mirrored link")
            open()
            beginning = false
        }
    }

    // MARK: From the phone

    private func received(_ live: WatchWire.Live) {
        if var state = live.rehab {
            if let data = state.session {
                phoneRoutine = try? JSONDecoder().decode(GuidedSession.self, from: data)
                state.session = nil
            }
            phoneRehab = state
            if screen == .ready, !state.finished, !state.discarded {
                if let routine = phoneRoutine {
                    begin { follow(routine, at: state) }
                } else {
                    tracker.send(.sync)
                }
            } else if let rehab, rehab.following {
                rehab.apply(state)
                if rehab.discardedOnPhone {
                    tracker.discard()
                    close()
                }
            }
        }
        if let pending = live.pending { self.pending = pending }
        if let strength = live.strength {
            if screen == .ready, let session = try? JSONDecoder().decode(StrengthSession.self, from: strength.session), session.isActive {
                begin { show(session) }
            } else {
                run?.adopt(strength)
            }
        }
        guard let command = live.command else { return }
        switch (command, screen) {
        case (.discard, .ready):
            // Closed on the phone before Start: nothing was recorded.
            tracker.discard()
            close()
        case (.finish, .strength):
            run?.closeFromPhone()
            Task {
                summary = await tracker.finish()
                screen = .strengthSummary
            }
        case (.discard, .strength):
            run?.closeFromPhone()
            tracker.discard()
            close()
        case (_, .rehab):
            rehab?.handle(command)
        default:
            break
        }
    }

    private func close() {
        screen = .start
        run = nil
        rehab = nil
        summary = nil
        phoneRehab = nil
        phoneRoutine = nil
        pending = nil
        startRequested = false
        readyFailed = false
        Task { await start.load() }
    }
}

/// A workout open on the phone, linked and waiting: Start here starts it on both.
private struct ReadyView: View {
    let pending: WatchWire.Pending?
    let heartRate: Double?
    let starting: Bool
    let failed: Bool
    let onStart: () -> Void
    let onRetry: () -> Void
    let onCancel: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Image(systemName: "iphone")
                    .font(.system(size: 26, weight: .regular))
                    .foregroundStyle(failed ? Color.muted : Color.ride)
                WatchKicker(kicker, color: failed ? .muted : .rideSoft)
                    .padding(.top, 8)
                WatchTitle(pending?.title ?? (failed ? "Couldn't link" : "Waiting"), size: 24)
                    .multilineTextAlignment(.center)
                    .padding(.top, 4)
                if let detail = pending?.detail {
                    Text(detail).font(WatchFont.body(11)).foregroundStyle(Color.muted).padding(.top, 3)
                }
                HeartRateLabel(bpm: heartRate, trend: nil)
                    .padding(.top, 6)
                if failed {
                    Button("Try again", action: onRetry)
                        .buttonStyle(VoltButtonStyle())
                        .padding(.top, 10)
                } else {
                    Button(starting ? "Starting…" : "Start", action: onStart)
                        .buttonStyle(VoltButtonStyle())
                        .disabled(pending == nil || starting)
                        .padding(.top, 10)
                }
                Button("Not now", action: onCancel)
                    .buttonStyle(DarkButtonStyle())
                    .padding(.top, 6)
            }
            .frame(maxWidth: .infinity)
        }
        .navigationBarBackButtonHidden()
    }

    private var kicker: String {
        if failed { return "Keep your iPhone close" }
        return pending == nil ? "Linking with iPhone" : "Ready · paired with iPhone"
    }
}
