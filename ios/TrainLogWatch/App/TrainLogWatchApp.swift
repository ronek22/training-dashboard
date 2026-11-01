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

    /// A workout started on the iPhone opened the app (`HKHealthStore.startWatchApp`).
    func handle(_ workoutConfiguration: HKWorkoutConfiguration) {
        let activity = workoutConfiguration.activityType
        Task { @MainActor in await WorkoutTracker.shared.startFromPhone(activity) }
    }
}

/// Start screen → a running session → its summary. A workout started on the phone goes through
/// the hand-off screen first and joins the phone's session.
struct WatchRoot: View {
    /// Whole screens swapped at the root: a running workout has no back button to slip out by.
    enum Screen: Hashable {
        case start
        /// Started on the phone: finding its session.
        case joining
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

    var body: some View {
        NavigationStack {
            switch screen {
            case .start: StartView(model: start, onStrength: open, onRehab: open)
            case .joining: JoiningView()
            default: destination(screen)
            }
        }
        .tint(.volt)
        .onChange(of: tracker.phoneStarts) { Task { await join() } }
        .task {
            tracker.onRemote = { received($0) }
            #if DEBUG
            if WatchDemo.enabled, let stage = WatchDemo.stage {
                if stage == "joining" {
                    screen = .joining
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
        case .start, .joining:
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

    // MARK: Started on the phone

    /// The phone started a workout and opened this app: find what it runs (a rehab routine it
    /// sends, or its strength session on the server) and show it. Gives up after about 12 s and
    /// drops the Health workout, so nothing records without a session behind it.
    private func join() async {
        guard screen == .start || screen == .joining else { return }
        screen = .joining
        for attempt in 0..<24 {
            if let state = phoneRehab, let routine = phoneRoutine, !state.finished, !state.discarded {
                return follow(routine, at: state)
            }
            if attempt % 4 == 0 {
                // Ask the phone for whatever it leads, routine included.
                tracker.send(.sync)
                if let active = try? await WatchAPI.get("/strength/workouts/sessions/active", as: StrengthSession?.self),
                   !active.stale, let session = active.value, session.isActive {
                    return show(session)
                }
            }
            try? await Task.sleep(for: .milliseconds(500))
        }
        guard screen == .joining else { return }
        tracker.discard()
        screen = .start
    }

    // MARK: From the phone

    private func received(_ live: WatchWire.Live) {
        if var state = live.rehab {
            if let data = state.session {
                phoneRoutine = try? JSONDecoder().decode(GuidedSession.self, from: data)
                state.session = nil
            }
            phoneRehab = state
            if let rehab, rehab.following {
                rehab.apply(state)
                if rehab.discardedOnPhone {
                    tracker.discard()
                    close()
                }
            }
        }
        if let strength = live.strength { run?.adopt(strength) }
        guard let command = live.command else { return }
        switch (command, screen) {
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
        Task { await start.load() }
    }
}

/// About a second while the Watch joins a workout started on the phone.
private struct JoiningView: View {
    var body: some View {
        VStack(spacing: 0) {
            Image(systemName: "iphone")
                .font(.system(size: 30, weight: .regular))
                .foregroundStyle(Color.ride)
            WatchKicker("Started on iPhone", color: .rideSoft)
                .padding(.top, 10)
            WatchTitle("Joining", size: 26)
                .padding(.top, 4)
            HStack(spacing: 6) {
                Image(systemName: "heart.fill").foregroundStyle(Color.heart)
                Text("Recording heart rate").font(WatchFont.body(12, weight: .semibold)).foregroundStyle(Color.muted)
            }
            .font(.system(size: 12))
            .padding(.top, 14)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .navigationBarBackButtonHidden()
    }
}
