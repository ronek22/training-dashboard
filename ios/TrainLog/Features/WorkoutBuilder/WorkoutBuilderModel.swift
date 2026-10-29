import Foundation
import Observation

/// One lift in the workout being built. Weight nil means bodyweight.
struct DraftExercise: Identifiable, Codable, Sendable, Equatable {
    var id = UUID()
    var name: String
    var sets: Int
    var reps: Int
    var weightKg: Double?
    var restSeconds: Int
    var notes: String?

    static let defaultRest = 90

    init(name: String, sets: Int = 3, reps: Int = 10, weightKg: Double? = nil, restSeconds: Int = defaultRest, notes: String? = nil) {
        self.name = name
        self.sets = min(max(sets, 1), 20)
        self.reps = min(max(reps, 1), 100)
        self.weightKg = weightKg.flatMap { $0 > 0 ? $0 : nil }
        self.restSeconds = restSeconds
        self.notes = notes
    }

    /// Last session's sets, reps and weight, so most picks need no editing.
    init(_ suggestion: ExerciseSuggestion) {
        self.init(
            name: suggestion.exerciseName,
            sets: suggestion.suggestedSetCount ?? 3,
            reps: suggestion.suggestedReps ?? 10,
            weightKg: suggestion.suggestedWeightKg
        )
    }
}

/// The workout being built: a template's fields, kept on disk until saved.
struct WorkoutDraft: Codable, Sendable, Equatable {
    var templateId: Int?
    var name: String
    var notes: String?
    var exercises: [DraftExercise]

    var input: TemplateInput {
        TemplateInput(
            name: name.trimmingCharacters(in: .whitespaces).isEmpty ? BuilderFormat.defaultName() : name.trimmingCharacters(in: .whitespaces),
            notes: notes.flatMap { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : $0 },
            exercises: exercises.map {
                .init(exerciseName: $0.name, setCount: $0.sets, targetReps: $0.reps, targetWeightKg: $0.weightKg,
                      restSeconds: $0.restSeconds, notes: $0.notes.flatMap { $0.isEmpty ? nil : $0 })
            }
        )
    }

    init(templateId: Int? = nil, name: String = "", notes: String? = nil, exercises: [DraftExercise] = []) {
        self.templateId = templateId
        self.name = name
        self.notes = notes
        self.exercises = exercises
    }

    init(_ template: TemplateDetail) {
        self.init(templateId: template.id, name: template.name, notes: template.notes, exercises: template.exercises.map {
            DraftExercise(name: $0.exerciseName, sets: $0.setCount, reps: $0.targetReps, weightKg: $0.targetWeightKg,
                          restSeconds: $0.restSeconds ?? DraftExercise.defaultRest, notes: $0.notes)
        })
    }

    /// A finished session as a template: working sets per lift, the most common reps, the middle weight.
    init(session: StrengthSession, name: String) {
        self.init(name: name, exercises: session.exercises.compactMap { exercise in
            let done = exercise.workingSets.filter(\.isCompleted)
            let sets = done.isEmpty ? exercise.workingSets : done
            guard !sets.isEmpty else { return nil }
            let reps = BuilderFormat.mode(sets.map { $0.actualReps ?? $0.targetReps }) ?? 10
            let weights = sets.compactMap { $0.actualWeightKg ?? $0.targetWeightKg }.filter { $0 > 0 }.sorted()
            return DraftExercise(name: exercise.exerciseName, sets: sets.count, reps: reps,
                                 weightKg: weights.isEmpty ? nil : weights[weights.count / 2],
                                 restSeconds: sets[0].restSeconds, notes: exercise.notes)
        })
    }
}

@MainActor
@Observable
final class WorkoutBuilderModel {
    var draft: WorkoutDraft {
        didSet { if draft != oldValue { storeDraft() } }
    }
    private(set) var original: WorkoutDraft
    /// Your exercise history, most done first.
    var suggestions: [ExerciseSuggestion] = []
    /// Server matches for the search box.
    private(set) var searchResults: [ExerciseSuggestion] = []
    var nudgeDismissed = false
    private(set) var saving = false
    private(set) var error: String?

    private let client: () -> APIClient
    private let queue: WriteQueue
    private let defaults: UserDefaults

    init(draft: WorkoutDraft, client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), defaults: UserDefaults = .standard) {
        self.client = client
        self.queue = queue
        self.defaults = defaults
        original = draft
        // Unsaved edits from a closed app come back.
        self.draft = Self.storedDraft(for: draft.templateId, in: defaults) ?? draft
    }

    var isDirty: Bool { draft != original }
    var isNew: Bool { draft.templateId == nil }
    var canSave: Bool { !draft.exercises.isEmpty && !saving }

    var summary: MuscleSummary { MuscleSummary(draft.exercises.map { ($0.name, $0.sets) }) }
    var setCount: Int { draft.exercises.reduce(0) { $0 + $1.sets } }
    var durationMinutes: Int { BuilderFormat.minutes(draft.exercises) }

    // MARK: Loading

    static func templatePath(_ id: Int) -> String { "/strength/workouts/templates/\(id)" }
    static let suggestionsPath = "/strength/workouts/exercise-suggestions?limit=50"

    func loadSuggestions() async {
        if let loaded = try? await client().get(Self.suggestionsPath, as: [ExerciseSuggestion].self) {
            suggestions = loaded.value
        }
    }

    func search(_ text: String) async {
        let query = text.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else {
            searchResults = []
            return
        }
        let encoded = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let path = "/strength/workouts/exercise-suggestions?limit=20&q=\(encoded)"
        if let loaded = try? await client().getLive(path, as: [ExerciseSuggestion].self) {
            searchResults = loaded
        } else {
            let needle = BuilderFormat.normalized(query)
            searchResults = suggestions.filter { $0.normalizedName.contains(needle) }
        }
    }

    func suggestion(named name: String) -> ExerciseSuggestion? {
        let key = BuilderFormat.normalized(name)
        return (suggestions + searchResults).first { $0.normalizedName == key }
    }

    // MARK: Ranking

    struct Section: Equatable {
        let title: String
        let missing: Bool
        let items: [ExerciseSuggestion]
    }

    /// "For this workout": what it's missing first (core), then more for its two biggest muscles.
    var rankedSections: [Section] {
        let summary = summary
        var sections: [Section] = []
        var used = Set(draft.exercises.map { BuilderFormat.normalized($0.name) })
        func pick(_ muscles: Set<Muscle>, limit: Int) -> [ExerciseSuggestion] {
            let items = suggestions.filter { suggestion in
                !used.contains(suggestion.normalizedName)
                    && !Set(MuscleRules.classify(suggestion.exerciseName)?.primary ?? []).isDisjoint(with: muscles)
            }
            .prefix(limit)
            used.formUnion(items.map(\.normalizedName))
            return Array(items)
        }
        if !summary.hasCore {
            let core = pick(Muscle.Group.core.muscles, limit: 3)
            if !core.isEmpty { sections.append(Section(title: "Missing · Core", missing: true, items: core)) }
        }
        for count in summary.counts.filter({ $0.primary > 0 && !$0.muscle.isCore }).prefix(2) {
            let items = pick([count.muscle], limit: 3)
            if !items.isEmpty { sections.append(Section(title: "More for \(count.muscle.label)", missing: false, items: items)) }
        }
        let rest = suggestions.filter { !used.contains($0.normalizedName) }
        if !rest.isEmpty { sections.append(Section(title: "Most done", missing: false, items: Array(rest.prefix(12)))) }
        return sections
    }

    /// Lifts that work the same main muscles, for Swap.
    func replacements(for exercise: DraftExercise) -> [ExerciseSuggestion] {
        let used = Set(draft.exercises.map { BuilderFormat.normalized($0.name) })
        let muscles = Set(MuscleRules.classify(exercise.name)?.primary ?? [])
        let candidates = suggestions.filter { !used.contains($0.normalizedName) }
        guard !muscles.isEmpty else { return candidates }
        return candidates.filter { !Set(MuscleRules.classify($0.exerciseName)?.primary ?? []).isDisjoint(with: muscles) }
    }

    func filtered(by group: Muscle.Group) -> [ExerciseSuggestion] {
        suggestions.filter { !Set(MuscleRules.classify($0.exerciseName)?.primary ?? []).isDisjoint(with: group.muscles) }
    }

    /// One gentle nudge when the workout has no core work: your most done core lift.
    var coreNudge: ExerciseSuggestion? {
        guard !nudgeDismissed, draft.exercises.count >= 2, !summary.hasCore else { return nil }
        return rankedSections.first(where: \.missing)?.items.first
    }

    // MARK: Editing

    func add(_ picks: [ExerciseSuggestion]) {
        draft.exercises.append(contentsOf: picks.map(DraftExercise.init))
    }

    func addNew(named name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        draft.exercises.append(DraftExercise(name: trimmed))
    }

    /// Swap keeps sets, reps and rest; the weight comes from the new lift's history.
    func swap(_ id: DraftExercise.ID, to suggestion: ExerciseSuggestion) {
        guard let index = draft.exercises.firstIndex(where: { $0.id == id }) else { return }
        draft.exercises[index].name = suggestion.exerciseName
        draft.exercises[index].weightKg = suggestion.suggestedWeightKg.flatMap { $0 > 0 ? $0 : nil }
        draft.exercises[index].notes = nil
    }

    func duplicate(_ id: DraftExercise.ID) {
        guard let index = draft.exercises.firstIndex(where: { $0.id == id }) else { return }
        var copy = draft.exercises[index]
        copy.id = UUID()
        draft.exercises.insert(copy, at: index + 1)
    }

    /// Returns what Undo needs to put it back.
    func remove(_ id: DraftExercise.ID) -> (DraftExercise, Int)? {
        guard let index = draft.exercises.firstIndex(where: { $0.id == id }) else { return nil }
        return (draft.exercises.remove(at: index), index)
    }

    func restore(_ removed: (DraftExercise, Int)) {
        draft.exercises.insert(removed.0, at: min(removed.1, draft.exercises.count))
    }

    func move(from source: IndexSet, to destination: Int) {
        draft.exercises.move(fromOffsets: source, toOffset: destination)
    }

    // MARK: Saving

    enum SaveResult: Equatable {
        /// Saved on the Mac; the template's id.
        case saved(Int)
        /// The Mac is out of reach; the save goes out with the next queued write.
        case queued
    }

    func save() async -> SaveResult? {
        saving = true
        defer { saving = false }
        let method = draft.templateId == nil ? "POST" : "PUT"
        let path = draft.templateId.map(Self.templatePath) ?? "/strength/workouts/templates"
        guard let body = try? APIClient.encoder.encode(draft.input) else { return nil }
        do {
            let saved = try await client().send(method, path, body: body, as: SavedTemplate.self)
            finish()
            return .saved(saved.id)
        } catch APIError.unreachable {
            queue.append(.init(method: method, path: path, body: body))
            finish()
            return .queued
        } catch {
            self.error = "Couldn't save: \(error.localizedDescription)"
            return nil
        }
    }

    func discard() {
        defaults.removeObject(forKey: Self.draftKey(draft.templateId))
    }

    private func finish() {
        error = nil
        discard()
        original = draft
    }

    private struct SavedTemplate: Decodable { let id: Int }

    // MARK: Draft on disk

    private static func draftKey(_ templateId: Int?) -> String { "builderDraft.\(templateId.map(String.init) ?? "new")" }

    private static func storedDraft(for templateId: Int?, in defaults: UserDefaults) -> WorkoutDraft? {
        defaults.data(forKey: draftKey(templateId)).flatMap { try? JSONDecoder().decode(WorkoutDraft.self, from: $0) }
    }

    private func storeDraft() {
        let key = Self.draftKey(draft.templateId)
        if draft == original {
            defaults.removeObject(forKey: key)
        } else if let data = try? JSONEncoder().encode(draft) {
            defaults.set(data, forKey: key)
        }
    }
}

enum BuilderFormat {
    /// Same estimate as the backend's `estimated_duration_minutes`: 45 s a set plus rest between sets.
    static func minutes(_ exercises: [DraftExercise]) -> Int {
        let seconds = exercises.reduce(0) { $0 + $1.sets * 45 + max(0, $1.sets - 1) * $1.restSeconds }
        return Int((Double(seconds) / 60).rounded())
    }

    static func normalized(_ name: String) -> String {
        String(name.lowercased().unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }.map(Character.init))
    }

    static func mode(_ values: [Int]) -> Int? {
        let counts = Dictionary(values.map { ($0, 1) }, uniquingKeysWith: +)
        return counts.max { ($0.value, -$0.key) < ($1.value, -$1.key) }?.key
    }

    /// "34", "33.5", "BW".
    static func weight(_ kg: Double?) -> String {
        guard let kg, kg > 0 else { return "BW" }
        return kg.rounded() == kg ? String(Int(kg)) : String(format: "%.1f", kg)
    }

    /// "1:30".
    static func rest(_ seconds: Int) -> String {
        "\(seconds / 60):" + String(format: "%02d", seconds % 60)
    }

    /// "Workout 29 Oct" when a new workout is saved without a name.
    static func defaultName(_ date: Date = .now) -> String {
        "Workout " + date.formatted(.dateTime.day().month(.abbreviated))
    }

    /// Next letter in a "Workout A, Workout B" series, plus the usual splits.
    static func nameIdeas(existing: [String]) -> [String] {
        let letters = existing.compactMap { name -> Character? in
            let parts = name.split(separator: " ")
            guard parts.count >= 2, parts[0].lowercased() == "workout", parts[1].count == 1, let letter = parts[1].first, letter.isLetter else { return nil }
            return Character(letter.uppercased())
        }
        var ideas: [String] = []
        if let last = letters.max(), let scalar = last.unicodeScalars.first, let next = UnicodeScalar(scalar.value + 1), last < "Z" {
            ideas.append("Workout \(Character(next))")
        }
        let taken = Set(existing.map { $0.lowercased() })
        ideas += ["Upper · Pull", "Upper · Push", "Full body", "Hotel room"].filter { !taken.contains($0.lowercased()) }
        return Array(ideas.prefix(3))
    }

    /// "Last 3 × 10 @ 25 kg · 6 days ago · 21 sessions".
    static func history(_ suggestion: ExerciseSuggestion, today: Date = .now) -> String {
        var parts: [String] = []
        if let sets = suggestion.suggestedSetCount, let reps = suggestion.suggestedReps {
            let load = suggestion.suggestedWeightKg.flatMap { $0 > 0 ? " @ \(weight($0)) kg" : nil } ?? ""
            parts.append("\(sets) × \(reps)\(load)")
        }
        if let ago = ago(suggestion.lastPerformedAt, today: today) { parts.append(ago) }
        if let count = suggestion.sessionCount, count > 1 { parts.append("\(count) sessions") }
        return parts.isEmpty ? "Never logged" : parts.joined(separator: " · ")
    }

    static func ago(_ timestamp: String?, today: Date = .now) -> String? {
        guard let timestamp, timestamp.count >= 10, let day = FoodFormat.parse(String(timestamp.prefix(10))) else { return nil }
        let days = max(0, Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: day), to: Calendar.current.startOfDay(for: today)).day ?? 0)
        switch days {
        case 0: return "today"
        case 1: return "yesterday"
        case ..<14: return "\(days) days ago"
        case ..<60: return "\(days / 7) weeks ago"
        default:
            let sameYear = Calendar.current.isDate(day, equalTo: today, toGranularity: .year)
            return sameYear ? day.formatted(.dateTime.month(.abbreviated)) : day.formatted(.dateTime.month(.abbreviated).year())
        }
    }
}
