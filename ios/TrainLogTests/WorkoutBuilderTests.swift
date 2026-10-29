import Foundation
import Testing
@testable import TrainLog

struct WorkoutBuilderTests {
    private let suggestionsJSON = """
    [
      {"exercise_name": "Dumbbell Row", "normalized_name": "dumbbellrow", "last_performed_at": "2026-10-27T18:00:00+01:00",
       "session_count": 21, "suggested_set_count": 3, "suggested_reps": 10, "suggested_weight_kg": 33.6,
       "last_sets": [{"reps": 10, "weight_kg": 33.6, "is_warmup": false, "effort": "solid"}],
       "recent_sessions": [{"date": "2026-10-20", "weight_kg": 32.0}, {"date": "2026-10-27", "weight_kg": 33.6}]},
      {"exercise_name": "Barbell Curl", "normalized_name": "barbellcurl", "session_count": 18,
       "suggested_set_count": 3, "suggested_reps": 10, "suggested_weight_kg": 25},
      {"exercise_name": "Hanging Knee Raise", "normalized_name": "hangingkneeraise", "session_count": 9,
       "suggested_set_count": 3, "suggested_reps": 12, "suggested_weight_kg": null},
      {"exercise_name": "Lat Pulldown", "normalized_name": "latpulldown", "session_count": 7,
       "suggested_set_count": 3, "suggested_reps": 10, "suggested_weight_kg": 52},
      {"exercise_name": "Back Squat", "normalized_name": "backsquat", "session_count": 5}
    ]
    """

    private func suggestions() throws -> [ExerciseSuggestion] {
        try APIClient.decoder.decode([ExerciseSuggestion].self, from: Data(suggestionsJSON.utf8))
    }

    @MainActor
    private func model(_ exercises: [DraftExercise], suggestions: [ExerciseSuggestion] = []) -> WorkoutBuilderModel {
        // One shared suite, cleared each time, so test runs don't pile up preference files.
        let defaults = UserDefaults(suiteName: "WorkoutBuilderTests")!
        defaults.removePersistentDomain(forName: "WorkoutBuilderTests")
        let model = WorkoutBuilderModel(draft: WorkoutDraft(name: "Upper · Pull", exercises: exercises), defaults: defaults)
        model.suggestions = suggestions
        return model
    }

    // MARK: Muscles

    @Test func classifiesLikeTheWeb() {
        #expect(MuscleRules.classify("Dumbbell Row") == MuscleMapping(primary: [.upperBack, .lats], secondary: [.biceps, .shoulders]))
        #expect(MuscleRules.classify("Lying Leg Curl")?.primary == [.hamstrings])
        #expect(MuscleRules.classify("Barbell Curl")?.primary == [.biceps])
        #expect(MuscleRules.classify("Hanging Knee Raise")?.primary == [.abs])
        #expect(MuscleRules.classify("Pull-Up")?.primary == [.lats])
        #expect(MuscleRules.classify("Hamstring stretch") == nil)
        #expect(MuscleRules.classify("Clean and Press") == nil)
    }

    @Test func summaryCountsSetsPerMuscle() {
        let summary = MuscleSummary([("Dumbbell Row", 3), ("Lat Pulldown", 3), ("Barbell Curl", 2)])
        #expect(summary.counts.first?.muscle == .lats)
        #expect(summary.counts.first { $0.muscle == .lats }?.primary == 6)
        #expect(summary.counts.first { $0.muscle == .biceps } == .init(muscle: .biceps, primary: 2, secondary: 6))
        #expect(summary.primary.contains(.biceps) && summary.secondary.contains(.shoulders))
        #expect(!summary.hasCore)
        #expect(summary.bestSide == .back)
        #expect(MuscleSummary([("Bench Press", 3)]).bestSide == .front)
    }

    @Test func silhouettePathsParse() {
        #expect(!SVGPath.parse(SilhouettePaths.body).isEmpty)
        #expect(SilhouettePaths.front.allSatisfy { !SVGPath.parse($0.path).isEmpty })
        #expect(SilhouettePaths.back.compactMap(\.muscle).contains(.lats))
    }

    // MARK: Drafts

    @Test func suggestionPrefillsLastSession() throws {
        let row = DraftExercise(try suggestions()[0])
        #expect(row.sets == 3 && row.reps == 10 && row.weightKg == 33.6 && row.restSeconds == 90)
        #expect(try suggestions()[0].recentSessions?.last?.weightKg == 33.6)
        #expect(DraftExercise(try suggestions()[2]).weightKg == nil)
        #expect(DraftExercise(name: "X", sets: 40, reps: 0).sets == 20)
    }

    @Test func sessionBecomesATemplate() throws {
        let json = """
        {"id": 9, "template_id": null, "template_name": "Gym", "status": "completed", "started_at": "2026-10-27T18:00:00+01:00",
         "current_exercise_order": 1, "current_set_order": 1, "exercises": [
          {"id": 1, "exercise_order": 1, "exercise_name": "Dumbbell Row", "notes": null, "sets": [
            {"id": 1, "set_order": 0, "target_reps": 10, "target_weight_kg": 20, "rest_seconds": 60, "status": "completed", "set_type": "warmup", "actual_reps": 10, "actual_weight_kg": 20},
            {"id": 2, "set_order": 1, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90, "status": "completed", "actual_reps": 10, "actual_weight_kg": 34},
            {"id": 3, "set_order": 2, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90, "status": "completed", "actual_reps": 9, "actual_weight_kg": 32},
            {"id": 4, "set_order": 3, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90, "status": "completed", "actual_reps": 10, "actual_weight_kg": 34}]},
          {"id": 2, "exercise_order": 2, "exercise_name": "Skipped", "notes": null, "sets": []}]}
        """
        let session = try APIClient.decoder.decode(StrengthSession.self, from: Data(json.utf8))
        let draft = WorkoutDraft(session: session, name: "Upper · Pull")
        #expect(draft.exercises.count == 1)
        let row = draft.exercises[0]
        #expect(row.sets == 3 && row.reps == 10 && row.weightKg == 34 && row.restSeconds == 90)
    }

    @Test func inputEncodesTheBackendShape() throws {
        var draft = WorkoutDraft(templateId: 4, name: "  ", notes: " ", exercises: [DraftExercise(name: "Pull-up", sets: 3, reps: 6)])
        draft.exercises[0].notes = ""
        let body = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(draft.input)) as? [String: Any]
        #expect((body?["name"] as? String)?.hasPrefix("Workout ") == true)
        #expect(body?["notes"] == nil || body?["notes"] is NSNull)
        let exercise = (body?["exercises"] as? [[String: Any]])?.first
        #expect(exercise?["exercise_name"] as? String == "Pull-up")
        #expect(exercise?["set_count"] as? Int == 3 && exercise?["target_reps"] as? Int == 6 && exercise?["rest_seconds"] as? Int == 90)
    }

    @Test func templateDetailRoundTrips() throws {
        let json = """
        {"id": 4, "name": "Workout B", "notes": null, "exercises": [
          {"exercise_name": "Dumbbell Row", "set_count": 3, "target_reps": 10, "target_weight_kg": 34, "rest_seconds": 90, "notes": "pause"}]}
        """
        let draft = WorkoutDraft(try APIClient.decoder.decode(TemplateDetail.self, from: Data(json.utf8)))
        #expect(draft.templateId == 4)
        #expect(draft.exercises[0].weightKg == 34 && draft.exercises[0].notes == "pause")
    }

    // MARK: Model

    @Test @MainActor func durationMatchesTheBackend() {
        let model = model([DraftExercise(name: "Row", sets: 3, reps: 10, restSeconds: 90), DraftExercise(name: "Curl", sets: 2, reps: 10, restSeconds: 60)])
        // (3·45 + 2·90) + (2·45 + 1·60) = 465 s ≈ 8 min.
        #expect(model.durationMinutes == 8)
        #expect(model.setCount == 5)
    }

    @Test @MainActor func rankingPutsMissingCoreFirstAndSkipsWhatsIn() throws {
        let model = model([DraftExercise(name: "Dumbbell Row"), DraftExercise(name: "Lat Pulldown")], suggestions: try suggestions())
        let sections = model.rankedSections
        #expect(sections.first?.title == "Missing · Core")
        #expect(sections.first?.items.map(\.exerciseName) == ["Hanging Knee Raise"])
        #expect(!sections.flatMap(\.items).contains { $0.exerciseName == "Dumbbell Row" })
        #expect(model.coreNudge?.exerciseName == "Hanging Knee Raise")
        model.nudgeDismissed = true
        #expect(model.coreNudge == nil)
    }

    @Test @MainActor func swapKeepsSetsAndTakesTheNewWeight() throws {
        let model = model([DraftExercise(name: "Dumbbell Row", sets: 4, reps: 8, weightKg: 34, restSeconds: 120)], suggestions: try suggestions())
        let row = model.draft.exercises[0]
        #expect(model.replacements(for: row).map(\.exerciseName) == ["Lat Pulldown"])
        model.swap(row.id, to: try suggestions()[3])
        #expect(model.draft.exercises[0].name == "Lat Pulldown")
        #expect(model.draft.exercises[0].sets == 4 && model.draft.exercises[0].restSeconds == 120 && model.draft.exercises[0].weightKg == 52)
    }

    @Test @MainActor func removeUndoAndDirty() {
        let model = model([DraftExercise(name: "A"), DraftExercise(name: "B")])
        #expect(!model.isDirty)
        let removed = model.remove(model.draft.exercises[0].id)
        #expect(model.isDirty && model.draft.exercises.map(\.name) == ["B"])
        model.restore(removed!)
        #expect(model.draft.exercises.map(\.name) == ["A", "B"])
        #expect(!model.isDirty)
    }

    @Test func pickMusclesTakesMostDonePerGroup() throws {
        let picks = BuilderFormat.picks(for: [.back, .core], from: try suggestions())
        #expect(picks.map(\.name) == ["Dumbbell Row", "Lat Pulldown", "Hanging Knee Raise"])
    }

    // MARK: Format

    @Test func formats() {
        #expect(BuilderFormat.weight(34) == "34" && BuilderFormat.weight(33.5) == "33.5" && BuilderFormat.weight(nil) == "BW")
        #expect(BuilderFormat.rest(90) == "1:30" && BuilderFormat.rest(60) == "1:00")
        #expect(BuilderFormat.mode([10, 9, 10]) == 10)
        #expect(BuilderFormat.nameIdeas(existing: ["Workout A · Legs", "Workout B · Back"]).first == "Workout C")
        #expect(!BuilderFormat.nameIdeas(existing: ["Full body"]).contains("Full body"))
    }
}
