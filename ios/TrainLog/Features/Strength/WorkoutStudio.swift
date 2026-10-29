import Observation
import SwiftUI

/// Workout Studio: start any saved workout, planned for today or not, and build or edit them
/// (Features/WorkoutBuilder).
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

    func detail(_ id: Int) async -> TemplateDetail? {
        try? await client().get(WorkoutBuilderModel.templatePath(id), as: TemplateDetail.self).value
    }

    func delete(_ id: Int) async -> Bool {
        do {
            try await client().send("DELETE", WorkoutBuilderModel.templatePath(id))
            templates.removeAll { $0.id == id }
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

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
    @State private var creating = false
    @State private var building: BuilderLaunch?
    /// Opened once the New workout sheet has gone.
    @State private var pendingDraft: WorkoutDraft?
    @State private var deleting: StrengthTemplateSummary?
    @State private var saved: SavedToast?

    private struct BuilderLaunch: Identifiable {
        let id = UUID()
        let draft: WorkoutDraft
    }

    private struct SavedToast: Equatable {
        let name: String
        let templateId: Int?
    }

    private var today: String { PlanModel.todayISO }

    var body: some View {
        List {
            Group {
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
            .listRowInsets(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .scrollIndicators(.hidden)
        .overlay(alignment: .bottom) {
            if let saved { savedToast(saved) }
        }
        .task { await model.load(planned: planned) }
        .task(id: saved) {
            guard saved != nil else { return }
            try? await Task.sleep(for: .seconds(6))
            withAnimation(.snappy) { saved = nil }
        }
        .sheet(isPresented: $creating, onDismiss: {
            if let draft = pendingDraft {
                pendingDraft = nil
                building = BuilderLaunch(draft: draft)
            }
        }) {
            NewWorkoutSheet(templates: model.templates) { pendingDraft = $0 }
                .presentationDetents([.large])
                .presentationBackground(Color.card)
                .presentationCornerRadius(34)
        }
        .fullScreenCover(item: $building) { launch in
            WorkoutBuilderView(model: WorkoutBuilderModel(draft: launch.draft)) { result, name in
                if case .saved(let id) = result {
                    saved = SavedToast(name: name, templateId: id)
                } else {
                    saved = SavedToast(name: name, templateId: nil)
                }
                Task { await model.load(planned: planned) }
            }
        }
        .confirmationDialog("Delete \(deleting?.name ?? "this workout")?", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            Button("Delete workout", role: .destructive) {
                if let template = deleting {
                    Task { _ = await model.delete(template.id) }
                }
            }
        } message: {
            Text("Past sessions stay in your history.")
        }
    }

    private func edit(_ template: StrengthTemplateSummary, copy: Bool = false) {
        Task {
            guard let detail = await model.detail(template.id) else { return }
            var draft = WorkoutDraft(detail)
            if copy {
                draft.templateId = nil
                draft.name = "\(detail.name) copy"
            }
            building = BuilderLaunch(draft: draft)
        }
    }

    private func savedToast(_ toast: SavedToast) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark")
                .font(.system(size: 12, weight: .heavy))
                .foregroundStyle(Color.mobility)
                .frame(width: 28, height: 28)
                .background(Color.mobility.opacity(0.18), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text("Saved “\(toast.name)”").font(AppFont.body(14, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                Text(toast.templateId == nil ? "Saves to the Mac when it's back" : "Synced to the Mac")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
            }
            Spacer()
            if let id = toast.templateId {
                Button("Start now") {
                    onPick(id)
                    dismiss()
                }
                .font(AppFont.body(14, weight: .semibold))
                .foregroundStyle(Color.volt)
                .frame(minHeight: 44)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Color.raised, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Color.outline))
        .shadow(color: .black.opacity(0.45), radius: 14, y: 6)
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Button("Close") { dismiss() }
                    .font(AppFont.body(16))
                    .foregroundStyle(Color.inkSoft)
                    .frame(minHeight: 44)
                Spacer()
                Button {
                    creating = true
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(Color.volt)
                        .frame(width: 36, height: 36)
                        .background(Color(hex: 0x191D27), in: Circle())
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("New workout")
            }
            Kicker("Any day", color: .strength)
            Text("WORKOUT STUDIO").font(AppFont.title(34)).foregroundStyle(Color.ink)
            Text("Pick one to see its brief. Swipe to edit, or + to build a new one.")
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
            HStack(alignment: .center, spacing: 12) {
                thumbnail(template)
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
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            Button {
                deleting = template
            } label: {
                Label("Delete", systemImage: "trash")
            }
            .tint(Color(hex: 0xFF5A6E))
            Button {
                edit(template)
            } label: {
                Label("Edit", systemImage: "pencil")
            }
            .tint(Color.ride)
        }
        .contextMenu {
            Button { edit(template) } label: { Label("Edit", systemImage: "pencil") }
            Button { edit(template, copy: true) } label: { Label("Copy", systemImage: "plus.square.on.square") }
            Button(role: .destructive) { deleting = template } label: { Label("Delete", systemImage: "trash") }
        }
    }

    /// The workout's muscles on whichever side shows more of them.
    private func thumbnail(_ template: StrengthTemplateSummary) -> some View {
        let summary = MuscleSummary((template.exercises ?? []).map { ($0.exerciseName, 1) })
        return MuscleSilhouette(side: summary.bestSide, primary: summary.primary, secondary: summary.secondary, background: .inset)
            .frame(width: 26, height: 54)
            .frame(width: 44, height: 64)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.cardBorder))
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(model.error == nil ? "No workouts yet" : "Not synced yet")
            Text(model.error == nil
                 ? "Tap + to build your first workout."
                 : "Can't reach the Mac. Start the backend and try again.")
                .font(AppFont.body(14))
                .foregroundStyle(Color.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
        }
        .card()
    }
}
