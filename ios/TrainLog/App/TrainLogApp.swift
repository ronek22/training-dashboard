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

    var body: some View {
        ZStack {
            Color.bg.ignoresSafeArea()
            switch tab {
            case .today: TodayView(onStartStrength: { strength = StrengthLaunch(templateId: $0) }, refresh: todayRefresh)
            case .plan: Placeholder(title: "Plan")
            case .food: Placeholder(title: "Food")
            case .activities: Placeholder(title: "Activities")
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            TabBar(selection: $tab, onPlus: { showQuickLog = true })
        }
        .sheet(isPresented: $showQuickLog) {
            Placeholder(title: "Log")
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
                Image(systemName: "plus")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(Color.bg)
                    .frame(width: 52, height: 52)
                    .background(Color.volt, in: Circle())
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

/// Screens that aren't built yet.
struct Placeholder: View {
    let title: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(AppFont.title(44)).foregroundStyle(Color.ink)
            Text("Coming next.").font(AppFont.body(14)).foregroundStyle(Color.muted)
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.bg)
    }
}
