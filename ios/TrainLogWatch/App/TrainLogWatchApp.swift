import HealthKit
import SwiftUI
import WatchKit

@main
struct TrainLogWatchApp: App {
    @WKApplicationDelegateAdaptor private var delegate: WatchAppDelegate

    init() {
        PhoneLink.shared.activate()
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

    var body: some View {
        NavigationStack {
            switch screen {
            case .start: StartView(model: start, onStrength: open, onRehab: open)
            case .ready:
                ReadyView(pending: pending, starting: startRequested, onStart: {
                    startRequested = true
                    tracker.send(.start)
                }, onCancel: {
                    tracker.discard()
                    close()
                })
            default: destination(screen)
            }
        }
        .tint(.volt)
        .onChange(of: tracker.phoneStarts) { Task { await getReady() } }
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
        strength.onEnd = { [tracker] in tracker.send($0) }
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
        routine.onCommand = { [tracker] in tracker.send($0) }
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
        for _ in 0..<15 where screen == .ready && pending == nil {
            tracker.send(.sync)
            try? await Task.sleep(for: .seconds(1))
        }
    }

    /// The phone started the workout (Start on either device), or it was already running there:
    /// the clock starts here too and the same screen opens.
    private func begin(_ open: @escaping () -> Void) {
        guard screen == .ready, !beginning else { return }
        beginning = true
        Task {
            await tracker.begin()
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
        Task { await start.load() }
    }
}

/// A workout open on the phone, linked and waiting: Start here starts it on both.
private struct ReadyView: View {
    let pending: WatchWire.Pending?
    let starting: Bool
    let onStart: () -> Void
    let onCancel: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Image(systemName: "iphone")
                    .font(.system(size: 26, weight: .regular))
                    .foregroundStyle(Color.ride)
                WatchKicker(pending == nil ? "Linking with iPhone" : "Ready · paired with iPhone", color: .rideSoft)
                    .padding(.top, 8)
                WatchTitle(pending?.title ?? "Waiting", size: 24)
                    .multilineTextAlignment(.center)
                    .padding(.top, 4)
                if let detail = pending?.detail {
                    Text(detail).font(WatchFont.body(11)).foregroundStyle(Color.muted).padding(.top, 3)
                }
                Button(starting ? "Starting…" : "Start", action: onStart)
                    .buttonStyle(VoltButtonStyle())
                    .disabled(pending == nil || starting)
                    .padding(.top, 12)
                Button("Not now", action: onCancel)
                    .buttonStyle(DarkButtonStyle())
                    .padding(.top, 6)
            }
            .frame(maxWidth: .infinity)
        }
        .navigationBarBackButtonHidden()
    }
}
