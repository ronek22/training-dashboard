import ActivityKit
import Foundation

/// Mirrors the strength session screen into its Live Activity (TrainLogWidgets/StrengthLiveActivity):
/// one activity per open workout, updated on every set and position change, ended on finish.
enum StrengthActivity {
    @MainActor
    static func show(_ session: StrengthSession, restEndsAt: Date?, restSeconds: Int) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled,
              let state = state(for: session, restEndsAt: restEndsAt, restSeconds: restSeconds)
        else { return }
        let attributes = StrengthActivityAttributes(
            sessionId: session.id,
            workout: shortName(session.templateName),
            startedAt: StrengthFormat.parseMoment(session.startedAt) ?? .now
        )
        Task { await apply(state, attributes: attributes) }
    }

    /// Ends every strength activity: the workout was finished, discarded, or isn't open anywhere.
    @MainActor
    static func end() {
        Task { await endAll(except: nil) }
    }

    private static func apply(_ state: StrengthActivityAttributes.ContentState, attributes: StrengthActivityAttributes) async {
        await endAll(except: attributes.sessionId)
        // Goes stale when the rest runs out, which flips the timer to "Rest done · go".
        let content = ActivityContent(state: state, staleDate: state.restEnd)
        if let activity = Activity<StrengthActivityAttributes>.activities.first(where: { $0.attributes.sessionId == attributes.sessionId }) {
            if activity.content.state != state { await activity.update(content) }
        } else {
            _ = try? Activity.request(attributes: attributes, content: content)
        }
    }

    /// Also drops a duplicate that two quick updates racing to request one can leave behind.
    private static func endAll(except sessionId: Int?) async {
        var kept = false
        for activity in Activity<StrengthActivityAttributes>.activities {
            if activity.attributes.sessionId == sessionId, !kept {
                kept = true
            } else {
                await activity.end(nil, dismissalPolicy: .immediate)
            }
        }
    }

    /// "Workout B" from "Workout B · Back + Arms": the island and lock screen have room for one part.
    static func shortName(_ templateName: String) -> String {
        templateName.components(separatedBy: " · ").first ?? templateName
    }

    /// What the activity shows for a session (unit-tested). A rest already over is dropped.
    static func state(
        for session: StrengthSession, restEndsAt: Date?, restSeconds: Int, now: Date = .now
    ) -> StrengthActivityAttributes.ContentState? {
        guard let current = StrengthLogic.current(in: session) else { return nil }
        let exercises = session.exercises.sorted { $0.exerciseOrder < $1.exerciseOrder }
        let sets = session.exercises.flatMap(\.sets)
        let restEnd = restEndsAt.flatMap { $0 > now ? $0 : nil }
        return .init(
            exercise: current.exercise.exerciseName,
            setLabel: StrengthLogic.label(for: current.set, in: current.exercise),
            load: StrengthFormat.load(
                weight: StrengthLogic.carriedWeight(for: current.set, in: current.exercise),
                reps: current.set.targetReps
            ),
            exerciseNumber: (exercises.firstIndex { $0.id == current.exercise.id } ?? 0) + 1,
            exerciseCount: exercises.count,
            setsDone: sets.filter(\.isCompleted).count,
            setsTotal: sets.count,
            restStart: restEnd.map { $0.addingTimeInterval(-TimeInterval(restSeconds)) },
            restEnd: restEnd,
            allSetsDone: session.exercises.allSatisfy(\.isDone)
        )
    }
}
