import SwiftUI

/// Pick lifts from your own history, ranked for this workout. In swap mode one tap replaces a lift.
struct AddExercisesSheet: View {
    let model: WorkoutBuilderModel
    /// Set when swapping: the list shows lifts for the same muscles and one tap picks.
    var swapping: DraftExercise?
    let onAdd: (_ picks: [ExerciseSuggestion], _ newName: String?) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var filter: Filter = .forWorkout
    @State private var picks: [ExerciseSuggestion] = []

    enum Filter: Hashable {
        case forWorkout, mostDone
        case group(Muscle.Group)

        var label: String {
            switch self {
            case .forWorkout: "For this workout"
            case .mostDone: "Most done"
            case .group(let group): group.rawValue
            }
        }
    }

    private var filters: [Filter] { [.forWorkout, .mostDone] + Muscle.Group.allCases.map(Filter.group) }

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 10) {
                nav
                searchField
                if swapping == nil && query.isEmpty { chips }
            }
            .padding(.horizontal, 18)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(sections, id: \.title) { section in
                        if let title = section.title.nonEmpty {
                            Text(title.uppercased())
                                .font(AppFont.body(10, weight: .bold))
                                .tracking(1.4)
                                .foregroundStyle(section.missing ? Color.warning : .faint)
                                .padding(.top, 16)
                                .padding(.bottom, 2)
                        }
                        ForEach(Array(section.items.enumerated()), id: \.element.id) { index, item in
                            row(item, missing: section.missing, divider: index > 0)
                        }
                    }
                    if let name = newName {
                        createRow(name)
                    }
                    if sections.allSatisfy(\.items.isEmpty) && newName == nil {
                        Text(model.suggestions.isEmpty ? "Loading your exercises…" : "Nothing logged for this yet.")
                            .font(AppFont.body(14))
                            .foregroundStyle(Color.muted)
                            .padding(.top, 24)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 20)
            }
            .scrollIndicators(.hidden)
            .scrollDismissesKeyboard(.immediately)
            if swapping == nil && !picks.isEmpty { tray }
        }
        .background(Color.card)
        .task(id: query) {
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await model.search(query)
        }
    }

    // MARK: Parts

    private var nav: some View {
        HStack {
            Button("Cancel") { dismiss() }
                .font(AppFont.body(16))
                .foregroundStyle(Color.inkSoft)
                .frame(minHeight: 44)
            Spacer()
            Text(swapping == nil ? "Add exercises" : "Swap \(swapping?.name ?? "")")
                .font(AppFont.body(16, weight: .semibold))
                .foregroundStyle(Color.ink)
                .lineLimit(1)
            Spacer()
            Color.clear.frame(width: 56, height: 1)
        }
        .padding(.top, 12)
    }

    private var searchField: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass").font(.system(size: 14, weight: .semibold)).foregroundStyle(Color.muted)
            TextField("", text: $query, prompt: Text(searchPrompt).foregroundStyle(Color.faint))
                .font(AppFont.body(15))
                .foregroundStyle(Color.ink)
                .autocorrectionDisabled()
                .submitLabel(.search)
            if !query.isEmpty {
                Button { query = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(Color.faint)
                }
                .accessibilityLabel("Clear search")
            }
        }
        .padding(.horizontal, 12)
        .frame(height: 42)
        .background(Color.inset, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.cardBorder))
    }

    private var searchPrompt: String { "Search your exercises" }

    private var chips: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 6) {
                ForEach(filters, id: \.self) { item in
                    let selected = item == filter
                    Button {
                        withAnimation(.snappy(duration: 0.2)) { filter = item }
                    } label: {
                        Text(item.label)
                            .font(AppFont.body(13, weight: .semibold))
                            .foregroundStyle(selected ? Color.ink : .inkSoft)
                            .padding(.horizontal, 12)
                            .frame(height: 32)
                            .background(selected ? Color.raised : .clear, in: Capsule())
                            .overlay(Capsule().strokeBorder(selected ? Color.raised : .outline))
                            .frame(minHeight: 44)
                            .contentShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .scrollIndicators(.hidden)
        .contentMargins(.horizontal, 0)
    }

    private func row(_ item: ExerciseSuggestion, missing: Bool, divider: Bool) -> some View {
        let picked = picks.contains { $0.id == item.id }
        let muscles = MuscleRules.classify(item.exerciseName)?.primary ?? []
        return Button {
            if swapping != nil {
                onAdd([item], nil)
                dismiss()
            } else if picked {
                picks.removeAll { $0.id == item.id }
            } else {
                picks.append(item)
            }
        } label: {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.exerciseName)
                        .font(AppFont.body(15, weight: .semibold))
                        .foregroundStyle(Color.ink)
                        .multilineTextAlignment(.leading)
                    HStack(spacing: 4) {
                        MuscleTags(muscles: Array(muscles.prefix(2)), color: missing ? .warning : Color(hex: 0xFF7AB5))
                        Text(BuilderFormat.history(item))
                            .font(AppFont.body(12))
                            .foregroundStyle(Color.muted)
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 8)
                if swapping != nil {
                    Image(systemName: "arrow.left.arrow.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Color.inkSoft)
                        .frame(width: 32, height: 32)
                        .overlay(Circle().strokeBorder(Color.outline, lineWidth: 1.5))
                } else {
                    Image(systemName: picked ? "checkmark" : "plus")
                        .font(.system(size: 13, weight: .heavy))
                        .foregroundStyle(picked ? Color.bg : .inkSoft)
                        .frame(width: 32, height: 32)
                        .background(picked ? Color.strength : .clear, in: Circle())
                        .overlay(Circle().strokeBorder(picked ? Color.strength : .outline, lineWidth: 1.5))
                        .contentTransition(.symbolEffect(.replace))
                }
            }
            .padding(.vertical, 10)
            .frame(minHeight: 56)
            .overlay(alignment: .top) {
                if divider { Rectangle().fill(Color.cardBorder).frame(height: 1) }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .sensoryFeedback(.selection, trigger: picked)
        .accessibilityAddTraits(picked ? .isSelected : [])
    }

    private func createRow(_ name: String) -> some View {
        Button {
            onAdd([], name)
            dismiss()
        } label: {
            HStack(spacing: 12) {
                Image(systemName: "plus")
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(Color.volt)
                    .frame(width: 32, height: 32)
                    .overlay(Circle().strokeBorder(Color.volt.opacity(0.5), lineWidth: 1.5))
                VStack(alignment: .leading, spacing: 3) {
                    Text("Create “\(name)” as a new exercise")
                        .font(AppFont.body(15, weight: .semibold))
                        .foregroundStyle(Color.volt)
                    Text("Starts at 3 × 10, no weight")
                        .font(AppFont.body(12))
                        .foregroundStyle(Color.muted)
                }
                Spacer()
            }
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.top, 8)
    }

    private var tray: some View {
        let added = picks.map(DraftExercise.init)
        let sets = added.reduce(0) { $0 + $1.sets }
        return VStack(spacing: 12) {
            HStack(spacing: 6) {
                ScrollView(.horizontal) {
                    HStack(spacing: 6) {
                        ForEach(picks) { pick in
                            Button {
                                picks.removeAll { $0.id == pick.id }
                            } label: {
                                Text("\(pick.exerciseName) ×")
                                    .font(AppFont.body(12, weight: .semibold))
                                    .foregroundStyle(Color(hex: 0xFF9AC6))
                                    .padding(.horizontal, 10)
                                    .frame(height: 30)
                                    .background(Color.strength.opacity(0.14), in: Capsule())
                                    .overlay(Capsule().strokeBorder(Color.strength))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Remove \(pick.exerciseName)")
                        }
                    }
                }
                .scrollIndicators(.hidden)
                Text("+\(sets) sets · ~\(BuilderFormat.minutes(added)) min")
                    .font(AppFont.body(12))
                    .foregroundStyle(Color.muted)
                    .fixedSize()
            }
            Button(picks.count == 1 ? "Add 1 exercise" : "Add \(picks.count) exercises") {
                onAdd(picks, nil)
                dismiss()
            }
            .buttonStyle(VoltButtonStyle())
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 8)
        .background(Color.card)
        .overlay(alignment: .top) { Rectangle().fill(Color.cardBorder).frame(height: 1) }
        .sensoryFeedback(.success, trigger: picks.count)
    }

    // MARK: Data

    private var sections: [WorkoutBuilderModel.Section] {
        if !query.trimmingCharacters(in: .whitespaces).isEmpty {
            return [.init(title: "", missing: false, items: model.searchResults)]
        }
        if let swapping {
            let items = model.replacements(for: swapping)
            let muscles = MuscleRules.classify(swapping.name)?.primary.map(\.label).joined(separator: " · ")
            return [.init(title: muscles.map { "Same muscles · \($0)" } ?? "Your exercises", missing: false, items: items)]
        }
        switch filter {
        case .forWorkout: return model.rankedSections
        case .mostDone: return [.init(title: "", missing: false, items: model.suggestions)]
        case .group(let group): return [.init(title: "", missing: false, items: model.filtered(by: group))]
        }
    }

    /// Offered when the typed name isn't one you've logged.
    private var newName: String? {
        let name = query.trimmingCharacters(in: .whitespaces)
        guard swapping == nil, name.count >= 2 else { return nil }
        let key = BuilderFormat.normalized(name)
        return model.searchResults.contains { $0.normalizedName == key } ? nil : name
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
