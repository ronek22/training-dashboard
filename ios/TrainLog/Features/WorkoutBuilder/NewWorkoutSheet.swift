import SwiftUI

/// Name a new workout and pick what it starts from, so it's rarely a blank page.
struct NewWorkoutSheet: View {
    let templates: [StrengthTemplateSummary]
    let onStart: (WorkoutDraft) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var choice: Choice = .empty
    @State private var sessions: [StrengthSession] = []
    @State private var sessionID: Int?
    @State private var templateID: Int?
    @State private var groups: Set<Muscle.Group> = []
    @State private var working = false
    @State private var error: String?
    @FocusState private var nameFocused: Bool

    private let client: () -> APIClient = { .current }

    enum Choice { case repeatSession, copy, muscles, empty }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    nav
                    Kicker("Name").padding(.top, 10)
                    nameField.padding(.top, 8)
                    nameIdeas.padding(.top, 10)
                    Kicker("Start from").padding(.top, 22)
                    VStack(spacing: 8) {
                        if !sessions.isEmpty {
                            option(.repeatSession, "Repeat a session", "Keep the lifts and sets you actually did") { sessionPicker }
                        }
                        if !templates.isEmpty {
                            option(.copy, "Copy a workout", "Start from one you have and change it") { templatePicker }
                        }
                        option(.muscles, "Pick muscles", "Get the lifts you do most for them, with last session's sets") { musclePicker }
                        option(.empty, "Start empty", "Add exercises one by one") { EmptyView() }
                    }
                    .padding(.top, 10)
                    if let error {
                        Text(error).font(AppFont.body(12)).foregroundStyle(Color.danger).padding(.top, 10)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 20)
            }
            .scrollIndicators(.hidden)
            Button {
                Task { await start() }
            } label: {
                if working { ProgressView().tint(Color.bg) } else { Text("Continue") }
            }
            .buttonStyle(VoltButtonStyle())
            .disabled(working || (choice == .muscles && groups.isEmpty))
            .opacity(choice == .muscles && groups.isEmpty ? 0.4 : 1)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .background(Color.card)
        .task { await loadSessions() }
    }

    private var nav: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minHeight: 44)
            Spacer()
            Text("New workout").font(AppFont.body(16, weight: .semibold)).foregroundStyle(Color.ink)
            Spacer()
            Color.clear.frame(width: 56, height: 1)
        }
        .padding(.top, 12)
    }

    private var nameField: some View {
        TextField("", text: $name, prompt: Text(BuilderFormat.defaultName()).foregroundStyle(Color.faint))
            .font(AppFont.body(17, weight: .semibold))
            .foregroundStyle(Color.ink)
            .textInputAutocapitalization(.words)
            .focused($nameFocused)
            .submitLabel(.done)
            .padding(.horizontal, 12)
            .frame(height: 48)
            .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(nameFocused ? Color.volt.opacity(0.5) : Color.cardBorder))
    }

    private var nameIdeas: some View {
        HStack(spacing: 6) {
            ForEach(BuilderFormat.nameIdeas(existing: templates.map(\.name)), id: \.self) { idea in
                Button(idea) { name = idea }
                    .font(AppFont.body(12, weight: .semibold))
                    .foregroundStyle(Color.inkSoft)
                    .padding(.horizontal, 12)
                    .frame(height: 30)
                    .overlay(Capsule().strokeBorder(Color.outline))
                    .frame(minHeight: 44)
                    .buttonStyle(.plain)
            }
        }
    }

    private func option<Detail: View>(_ value: Choice, _ title: String, _ detail: String, @ViewBuilder extra: () -> Detail) -> some View {
        let selected = choice == value
        // The picker sits outside the button so its own taps (a Menu, chips) still work.
        return VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation(.snappy(duration: 0.2)) { choice = value }
            } label: {
                HStack(alignment: .top, spacing: 12) {
                    Circle()
                        .strokeBorder(selected ? Color.volt : Color.dim, lineWidth: selected ? 7 : 2)
                        .frame(width: 22, height: 22)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title).font(AppFont.body(15, weight: .semibold)).foregroundStyle(Color.ink)
                        Text(detail).font(AppFont.body(12)).foregroundStyle(Color.muted).fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(selected ? .isSelected : [])
            if selected { extra().padding(.leading, 34) }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(selected ? Color.volt.opacity(0.05) : Color.inset, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(selected ? Color.volt : Color.cardBorder))
    }

    private var sessionPicker: some View {
        let session = sessions.first { $0.id == sessionID } ?? sessions.first
        return Menu {
            ForEach(sessions, id: \.id) { item in
                Button(sessionTitle(item)) { sessionID = item.id }
            }
        } label: {
            if let session { pickedRow(sessionTitle(session), sessionLifts(session), summary: MuscleSummary(session.exercises.map { ($0.exerciseName, $0.workingSets.count) })) }
        }
    }

    private var templatePicker: some View {
        let template = templates.first { $0.id == templateID } ?? templates.first
        return Menu {
            ForEach(templates) { item in
                Button(item.name) { templateID = item.id }
            }
        } label: {
            if let template {
                pickedRow(template.name, StudioFormat.meta(template),
                          summary: MuscleSummary((template.exercises ?? []).map { ($0.exerciseName, 1) }))
            }
        }
    }

    private func pickedRow(_ title: String, _ detail: String, summary: MuscleSummary) -> some View {
        HStack(spacing: 10) {
            MuscleSilhouette(side: summary.bestSide, primary: summary.primary, secondary: summary.secondary, background: .inset)
                .frame(width: 22, height: 46)
                .frame(width: 34, height: 50)
                .background(Color.inset, in: RoundedRectangle(cornerRadius: 9))
                .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(Color.cardBorder))
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(AppFont.body(13, weight: .semibold)).foregroundStyle(Color.ink).lineLimit(1)
                Text(detail).font(AppFont.body(12)).foregroundStyle(Color.muted).lineLimit(2).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 4)
            Text("Change").font(AppFont.body(13)).foregroundStyle(Color.inkSoft)
        }
        .padding(10)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.cardBorder))
    }

    private var musclePicker: some View {
        let columns = [GridItem(.adaptive(minimum: 84), spacing: 6)]
        return LazyVGrid(columns: columns, alignment: .leading, spacing: 6) {
            ForEach(Muscle.Group.allCases, id: \.self) { group in
                let on = groups.contains(group)
                Button {
                    if on { groups.remove(group) } else { groups.insert(group) }
                } label: {
                    Text(group.rawValue)
                        .font(AppFont.body(13, weight: .semibold))
                        .foregroundStyle(on ? Color(hex: 0xFF9AC6) : .inkSoft)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(on ? Color.strength.opacity(0.14) : .clear, in: Capsule())
                        .overlay(Capsule().strokeBorder(on ? Color.strength : .outline))
                        .frame(minHeight: 44)
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .sensoryFeedback(.selection, trigger: on)
            }
        }
    }

    // MARK: Data

    private func sessionTitle(_ session: StrengthSession) -> String {
        let day = FoodFormat.parse(String(session.startedAt.prefix(10)))?.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated))
        return [day, session.templateName].compactMap { $0 }.joined(separator: " · ")
    }

    private func sessionLifts(_ session: StrengthSession) -> String {
        let names = session.exercises.map(\.exerciseName)
        let shown = names.prefix(3).joined(separator: ", ") + (names.count > 3 ? " +\(names.count - 3)" : "")
        let sets = session.exercises.reduce(0) { $0 + $1.workingSets.filter(\.isCompleted).count }
        return "\(shown) · \(sets) sets"
    }

    private func loadSessions() async {
        let loaded = try? await client().get("/strength/workouts/sessions?limit=12", as: [StrengthSession].self)
        sessions = (loaded?.value ?? []).filter { $0.status == "completed" && !$0.exercises.isEmpty }
        if !sessions.isEmpty { choice = .repeatSession }
    }

    private func start() async {
        working = true
        defer { working = false }
        let typed = name.trimmingCharacters(in: .whitespaces)
        let draft: WorkoutDraft
        switch choice {
        case .repeatSession:
            guard let session = sessions.first(where: { $0.id == sessionID }) ?? sessions.first else { return }
            draft = WorkoutDraft(session: session, name: typed.isEmpty ? session.templateName : typed)
        case .copy:
            guard let id = templateID ?? templates.first?.id else { return }
            do {
                let template = try await client().get(WorkoutBuilderModel.templatePath(id), as: TemplateDetail.self).value
                var copy = WorkoutDraft(template)
                copy.templateId = nil
                copy.name = typed.isEmpty ? "\(template.name) copy" : typed
                draft = copy
            } catch {
                self.error = "Can't load that workout from the Mac."
                return
            }
        case .muscles:
            let suggestions = (try? await client().get(WorkoutBuilderModel.suggestionsPath, as: [ExerciseSuggestion].self).value) ?? []
            draft = WorkoutDraft(name: typed, exercises: BuilderFormat.picks(for: groups, from: suggestions))
        case .empty:
            draft = WorkoutDraft(name: typed)
        }
        onStart(draft)
        dismiss()
    }
}

extension BuilderFormat {
    /// Pick muscles: your two most done lifts per group, in the order the groups are listed.
    static func picks(for groups: Set<Muscle.Group>, from suggestions: [ExerciseSuggestion], perGroup: Int = 2) -> [DraftExercise] {
        var used = Set<String>()
        var picks: [DraftExercise] = []
        for group in Muscle.Group.allCases where groups.contains(group) {
            let matches = suggestions.filter {
                !used.contains($0.normalizedName)
                    && !Set(MuscleRules.classify($0.exerciseName)?.primary ?? []).isDisjoint(with: group.muscles)
            }
            for suggestion in matches.prefix(perGroup) {
                used.insert(suggestion.normalizedName)
                picks.append(DraftExercise(suggestion))
            }
        }
        return picks
    }
}
