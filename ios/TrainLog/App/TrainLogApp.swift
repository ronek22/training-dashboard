import SwiftUI

@main
struct TrainLogApp: App {
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

    var body: some View {
        ZStack {
            Color.bg.ignoresSafeArea()
            switch tab {
            case .today: TodayView(onStartStrength: { strength = StrengthLaunch(templateId: $0) }, refresh: todayRefresh)
            case .plan: PlanView(showingDetail: $planDetailOpen, onStartStrength: { strength = StrengthLaunch(templateId: $0) })
            case .food: FoodView()
            case .activities: ActivitiesView(showingDetail: $activityDetailOpen)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            // Detail pages are pushed with their own back button, as in the artboard.
            if !(tab == .activities && activityDetailOpen) && !(tab == .plan && planDetailOpen) {
                TabBar(selection: $tab, onPlus: { showQuickLog = true })
            }
        }
        .sheet(isPresented: $showQuickLog, onDismiss: { todayRefresh += 1 }) {
            QuickLogSheet()
                .presentationDetents([.large])
                .presentationBackground(Color.card)
        }
        .fullScreenCover(item: $strength, onDismiss: { todayRefresh += 1 }) { launch in
            StrengthSessionView(templateId: launch.templateId)
        }
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
