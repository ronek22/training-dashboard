import Observation
import SwiftUI

/// Workout Studio: start any workout built on the Mac, planned for today or not.
/// Building workouts on the phone comes later; this only lists the saved templates.
@MainActor
@Observable
final class WorkoutStudioModel {
    private(set) var templates: [StrengthTemplateSummary] = []
    private(set) var loaded = false
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?

    private let client: () -> APIClient

    init(client: @escaping () -> APIClient = { .current }) {
        self.client = client
    }

    static let path = "/strength/workouts/templates"

    func load(planned: Int?) async {
        do {
            let result = try await client().get(Self.path, as: [StrengthTemplateSummary].self)
            templates = StudioFormat.ordered(result.value, planned: planned)
            syncedAt = result.syncedAt
            offline = result.fromCache
            error = nil
        } catch {
            offline = !templates.isEmpty
            self.error = error.localizedDescription
        }
        loaded = true
    }
}

enum StudioFormat {
    /// Today's planned workout first, then the one that's waited longest; never-done ones last.
    static func ordered(_ templates: [StrengthTemplateSummary], planned: Int?) -> [StrengthTemplateSummary] {
        templates.enumerated().sorted { lhs, rhs in
            let (a, b) = (lhs.element, rhs.element)
            if (a.id == planned) != (b.id == planned) { return a.id == planned }
            switch (day(a.lastDoneAt), day(b.lastDoneAt)) {
            case let (x?, y?) where x != y: return x < y
            case (_?, nil): return true
            case (nil, _?): return false
            default: return lhs.offset < rhs.offset
            }
        }
        .map(\.element)
    }

    /// "4 lifts · 12 sets · ~34 min".
    static func meta(_ template: StrengthTemplateSummary) -> String {
        [
            template.exerciseCount.map { "\($0) \($0 == 1 ? "lift" : "lifts")" },
            template.setCount.map { "\($0) sets" },
            template.estimatedDurationMinutes.map { "~\($0) min" },
        ]
        .compactMap { $0 }
        .joined(separator: " · ")
    }

    /// "Back Squat, Bulgarian Split Squat, Hanging Leg Raise".
    static func lifts(_ template: StrengthTemplateSummary) -> String? {
        let names = (template.exercises ?? []).map(\.exerciseName)
        return names.isEmpty ? nil : names.joined(separator: ", ")
    }

    /// "Today", "Yesterday", "5 days ago", "3 weeks ago", "Not done yet".
    static func lastDone(_ startedAt: String?, today: String) -> String {
        guard let day = day(startedAt), let from = FoodFormat.parse(day), let to = FoodFormat.parse(today) else {
            return "Not done yet"
        }
        let days = max(0, Calendar.current.dateComponents([.day], from: from, to: to).day ?? 0)
        switch days {
        case 0: return "Today"
        case 1: return "Yesterday"
        case ..<14: return "\(days) days ago"
        default: return "\(days / 7) weeks ago"
        }
    }

    /// The local date part of a backend timestamp.
    private static func day(_ timestamp: String?) -> String? {
        guard let timestamp, timestamp.count >= 10 else { return nil }
        return String(timestamp.prefix(10))
    }
}

/// The sheet behind Today's dumbbell button. Picking a workout opens its brief.
struct WorkoutStudioSheet: View {
    /// The template today's plan names, shown first and tagged.
    let planned: Int?
    let onPick: (Int) -> Void
    @State private var model = WorkoutStudioModel()
    @Environment(\.dismiss) private var dismiss

    private var today: String { PlanModel.todayISO }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                header
                if model.offline, let syncedAt = model.syncedAt {
                    Text("Offline · last synced \(syncedAt.formatted(date: .omitted, time: .shortened))")
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.muted)
                        .padding(.horizontal, 4)
                }
                if !model.templates.isEmpty {
                    ForEach(model.templates) { template in
                        row(template)
                    }
                } else if model.loaded {
                    emptyCard
                } else {
                    ProgressView().tint(.muted).frame(maxWidth: .infinity, minHeight: 200)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .task { await model.load(planned: planned) }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Kicker("Any day", color: .strength)
                Spacer()
                Button("Close") { dismiss() }
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .frame(minHeight: 44)
            }
            Text("WORKOUT STUDIO").font(AppFont.title(34)).foregroundStyle(Color.ink)
            Text("Workouts built on the Mac. Pick one to see its brief before you start.")
                .font(AppFont.body(13))
                .foregroundStyle(Color.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 4)
        .padding(.top, 8)
        .padding(.bottom, 6)
    }

    private func row(_ template: StrengthTemplateSummary) -> some View {
        let isPlanned = template.id == planned
        return Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            onPick(template.id)
            dismiss()
        } label: {
            HStack(alignment: .top, spacing: 12) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.strength)
                    .frame(width: 4)
                    .frame(maxHeight: .infinity)
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(template.name)
                            .font(AppFont.body(16, weight: .bold))
                            .foregroundStyle(Color.ink)
                            .multilineTextAlignment(.leading)
                        Spacer(minLength: 4)
                        if isPlanned {
                            Pill(text: "Today", color: .strength)
                        }
                    }
                    Text(StudioFormat.meta(template))
                        .font(AppFont.body(12, weight: .medium))
                        .foregroundStyle(Color.inkSoft)
                    if let lifts = StudioFormat.lifts(template) {
                        Text(lifts)
                            .font(AppFont.body(12))
                            .foregroundStyle(Color.muted)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                    HStack(spacing: 4) {
                        Image(systemName: "clock.arrow.circlepath").font(.system(size: 11, weight: .semibold))
                        Text(StudioFormat.lastDone(template.lastDoneAt, today: today))
                            .font(AppFont.body(12, weight: .medium))
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold))
                    }
                    .foregroundStyle(Color.muted)
                    .padding(.top, 4)
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            .card(border: isPlanned ? Color.strength.opacity(0.35) : .cardBorder)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint("Opens the workout brief")
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(model.error == nil ? "No workouts yet" : "Not synced yet")
            Text(model.error == nil
                 ? "Build a workout on the Mac and it shows up here."
                 : "Can't reach the Mac. Start the backend and try again.")
                .font(AppFont.body(14))
                .foregroundStyle(Color.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
        }
        .card()
    }
}
