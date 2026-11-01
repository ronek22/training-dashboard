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
}

/// Start screen → a running session → its summary.
struct WatchRoot: View {
    /// Whole screens swapped at the root: a running workout has no back button to slip out by.
    enum Screen: Hashable {
        case start
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

    var body: some View {
        NavigationStack {
            switch screen {
            case .start: StartView(model: start, onStrength: open, onRehab: open)
            default: destination(screen)
            }
        }
        .tint(.volt)
        .task {
            #if DEBUG
            if WatchDemo.enabled, let stage = WatchDemo.stage {
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
                run = StrengthRun(session: saved)
                screen = .strength
                if !tracker.running { await tracker.start(start.activityType(for: saved)) }
            }
        }
    }

    @ViewBuilder
    private func destination(_ screen: Screen) -> some View {
        switch screen {
        case .start:
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

    private func open(_ session: StrengthSession) {
        run = StrengthRun(session: session)
        screen = .strength
        #if DEBUG
        if WatchDemo.enabled {
            tracker.demo(heartRate: 128, startedMinutesAgo: 0)
            return
        }
        #endif
        Task { await tracker.start(start.activityType(for: session)) }
    }

    private func open(_ session: GuidedSession) {
        let run = RehabRun(session: session)
        // The phone follows along and can press Next, Back and Pause.
        run.onChange = { [tracker] in tracker.share(rehab: $0) }
        tracker.onCommand = { [weak run] in run?.handle($0) }
        rehab = run
        screen = .rehab
        #if DEBUG
        if WatchDemo.enabled {
            tracker.demo(heartRate: 96, startedMinutesAgo: 4)
            return
        }
        #endif
        Task { await tracker.start(Self.activityType(rehab: session.watchWorkout)) }
    }

    private func close() {
        screen = .start
        run = nil
        rehab = nil
        summary = nil
        tracker.onCommand = nil
        Task { await start.load() }
    }

    /// The backend names the Apple Workout to use (`watch_workout`); rehab defaults to recovery.
    static func activityType(rehab name: String?) -> HKWorkoutActivityType {
        switch name?.lowercased() ?? "" {
        case let value where value.contains("flexibility"): .flexibility
        case let value where value.contains("core"): .coreTraining
        case let value where value.contains("mind"): .mindAndBody
        case let value where value.contains("walk"): .walking
        case let value where value.contains("strength"): .functionalStrengthTraining
        default: .preparationAndRecovery
        }
    }
}
