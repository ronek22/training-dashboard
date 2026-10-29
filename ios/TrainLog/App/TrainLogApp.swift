import SwiftUI
import UserNotifications

@main
struct TrainLogApp: App {
    init() {
        // Must run during launch so HealthKit can wake the app in the background for new samples.
        HealthSync.shared.startObserving()
        WorkoutSync.shared.startObserving()
        ServerRoute.shared.watchNetwork()
        UNUserNotificationCenter.current().delegate = NotificationRouter.shared
    }

    var body: some Scene {
        WindowGroup {
            Group {
                #if DEBUG
                // `-demoGallery YES` shows every rehab demo, to check the figures without a session.
                if UserDefaults.standard.bool(forKey: "demoGallery") {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 18) {
                            ForEach(ExerciseDemos.all, id: \.key) { demo in
                                Kicker(demo.title, color: .mobility)
                                ExerciseDemoView(demo: demo)
                            }
                        }
                        .padding(16)
                    }
                    .background(Color.bg)
                } else {
                    RootView()
                }
                #else
                RootView()
                #endif
            }
            .preferredColorScheme(.dark)
        }
        // Re-checks today before the evening nudges, so one for something done on the web stays quiet.
        .backgroundTask(.appRefresh(Reminders.refreshTaskID)) {
            Reminders.scheduleRefresh()
            await Reminders.refresh()
        }
    }
}

enum AppTab: Hashable {
    case today, plan, food, activities
}

struct RootView: View {
    @State private var tab: AppTab = .today
    @State private var strength: StrengthLaunch?
    @State private var todayRefresh = 0
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        // System tab bar: Liquid Glass on iOS 26, and every tab keeps its scroll and navigation state.
        TabView(selection: $tab) {
            Tab("Today", systemImage: "clock", value: .today) {
                TodayView(onStartStrength: { strength = StrengthLaunch(templateId: $0) }, refresh: todayRefresh)
            }
            Tab("Plan", systemImage: "calendar", value: .plan) {
                PlanView(onStartStrength: { strength = StrengthLaunch(templateId: $0) })
            }
            Tab("Food", systemImage: "fork.knife", value: .food) {
                FoodView()
            }
            Tab("Activities", systemImage: "waveform.path.ecg", value: .activities) {
                ActivitiesView()
            }
        }
        .tint(.volt)
        .task(id: scenePhase) {
            if scenePhase == .active {
                async let health: Void = HealthSync.shared.sync()
                async let workouts: Void = WorkoutSync.shared.sync()
                // Drops nudges for what's already done today and rolls the week ahead.
                async let reminders: Void = Reminders.refresh()
                await CacheWarmer.warm()
                await health
                await workouts
                await reminders
            } else if scenePhase == .background {
                Reminders.scheduleRefresh()
            }
        }
        .fullScreenCover(item: $strength, onDismiss: { todayRefresh += 1 }) { launch in
            StrengthSessionView(templateId: launch.templateId)
        }
        // Widgets and the strength Live Activity.
        .onOpenURL { url in
            guard url.scheme == "trainlog" else { return }
            switch url.host() {
            case "food": tab = .food
            case "plan": tab = .plan
            case "strength": if strength == nil { strength = StrengthLaunch(templateId: nil) }
            default: tab = .today
            }
        }
    }
}

/// Fills every tab's offline cache while the Mac is reachable, so tabs that weren't opened at home
/// still have something to show away from it. Skipped when the server is already known offline.
enum CacheWarmer {
    static func warm(_ api: APIClient = .current) async {
        guard !api.reachability.knownOffline else { return }
        let today = FoodFormat.iso(.now)
        async let plan = try? api.get(PlanModel.weeksPath, as: [WeeklyPlan].self)
        async let activities = try? api.get(ActivitiesModel.listPath, as: [ActivitySummary].self)
        async let food = try? api.get(FoodModel.dayPath(today), as: FoodDay.self)
        async let dinners = try? api.get(FoodModel.dinnersPath(today), as: DinnerWeek.self)
        async let templates = try? api.get("/strength/workouts/templates", as: [StrengthTemplateSummary].self)
        async let history = try? api.get(TrendsModel.historyPath, as: TrainingHistory.self)
        async let health = try? api.get(TrendsModel.healthPath, as: HealthSummary.self, timeout: 12)
        _ = await (plan, activities, dinners, templates, history, health)
        // The Food widgets, before the Food tab has been opened today.
        if let day = await food, !day.fromCache {
            WidgetStore.update { $0.food = .init(day.value, eaten: day.value.totals) }
        }
    }
}

/// Opens the strength session screen; a nil template resumes the active workout.
struct StrengthLaunch: Identifiable {
    let id = UUID()
    let templateId: Int?
}

extension View {
    /// Detail pages are pushed with their own back button, as in the artboard.
    func hidesTabBar() -> some View {
        toolbar(.hidden, for: .tabBar)
    }
}
