import SwiftUI

@main
struct TrainLogApp: App {
    init() {
        // Must run during launch so HealthKit can wake the app in the background for new samples.
        HealthSync.shared.startObserving()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .preferredColorScheme(.dark)
        }
    }
}

enum AppTab: Hashable {
    case today, plan, food, activities
}

struct RootView: View {
    @State private var tab: AppTab = .today
    @State private var showQuickLog = false
    @State private var strength: StrengthLaunch?
    @State private var todayRefresh = 0
    @State private var activityDetailOpen = false
    @State private var planDetailOpen = false
    @State private var settingsOpen = false
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            Color.bg.ignoresSafeArea()
            switch tab {
            case .today: TodayView(showingDetail: $settingsOpen, onStartStrength: { strength = StrengthLaunch(templateId: $0) }, refresh: todayRefresh)
            case .plan: PlanView(showingDetail: $planDetailOpen, onStartStrength: { strength = StrengthLaunch(templateId: $0) })
            case .food: FoodView()
            case .activities: ActivitiesView(showingDetail: $activityDetailOpen)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            // Detail pages are pushed with their own back button, as in the artboard.
            if !(tab == .activities && activityDetailOpen) && !(tab == .plan && planDetailOpen) && !(tab == .today && settingsOpen) {
                TabBar(selection: $tab, onPlus: { showQuickLog = true })
            }
        }
        .sheet(isPresented: $showQuickLog, onDismiss: { todayRefresh += 1 }) {
            QuickLogSheet()
                .presentationDetents([.large])
                .presentationBackground(Color.card)
        }
        // Rolls the dinner nudges a week ahead.
        .task { await Reminders.apply() }
        .task(id: scenePhase) {
            if scenePhase == .active {
                async let health: Void = HealthSync.shared.sync()
                await CacheWarmer.warm()
                await health
            }
        }
        .fullScreenCover(item: $strength, onDismiss: { todayRefresh += 1 }) { launch in
            StrengthSessionView(templateId: launch.templateId)
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
        _ = await (plan, activities, food, dinners, templates, history, health)
    }
}

/// Opens the strength session screen; a nil template resumes the active workout.
struct StrengthLaunch: Identifiable {
    let id = UUID()
    let templateId: Int?
}

/// Bottom bar from the artboard: four tabs around one volt + that opens the quick log sheet.
struct TabBar: View {
    @Binding var selection: AppTab
    let onPlus: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            item(.today, "Today", "clock")
            item(.plan, "Plan", "calendar")
            Button(action: onPlus) {
                // Food has its own volt action (Snap meal), so the + steps back there.
                Image(systemName: "plus")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(selection == .food ? Color.ink : Color.bg)
                    .frame(width: 52, height: 52)
                    .background(selection == .food ? Color.raised : Color.volt, in: Circle())
            }
            .frame(maxWidth: .infinity)
            .padding(.top, -4)
            .accessibilityLabel("Quick log")
            item(.food, "Food", "fork.knife")
            item(.activities, "Activities", "waveform.path.ecg")
        }
        .padding(.horizontal, 10)
        .padding(.top, 8)
        .frame(maxWidth: .infinity)
        .background {
            Color.inset.opacity(0.94)
                .overlay(alignment: .top) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
                .ignoresSafeArea(edges: .bottom)
        }
    }

    private func item(_ tab: AppTab, _ title: String, _ icon: String) -> some View {
        Button {
            selection = tab
        } label: {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.system(size: 21, weight: .medium)).frame(height: 24)
                Text(title).font(AppFont.body(10, weight: .semibold))
            }
            .foregroundStyle(selection == tab ? Color.volt : Color.faint)
            .frame(maxWidth: .infinity, minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
