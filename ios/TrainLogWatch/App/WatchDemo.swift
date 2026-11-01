#if DEBUG
import Foundation

/// `-watchDemo YES`: a sample day and workout with every write switched off, for simulator
/// screenshots without touching the real server. `-watchDemoStage effort|rest|list|controls|done|hold`
/// opens that screen straight away. Also fills the Watch widgets with the artboard's day.
enum WatchDemo {
    static var enabled: Bool { UserDefaults.standard.bool(forKey: "watchDemo") }
    static var stage: String? { UserDefaults.standard.string(forKey: "watchDemoStage") }

    /// The artboard's day for the Watch widgets (Smart Stack and faces).
    static func seedWidgets() {
        guard enabled, let data = try? JSONEncoder().encode(WidgetSnapshot.watchPreview) else { return }
        WidgetStore.store(data)
    }

    static let today = WatchToday(
        date: "2026-10-31",
        today: .init(title: "Workout B", durationMin: 45, status: "planned", strength: .init(
            templateId: 3, name: "Workout B", exercises: [
                .init(name: "Lat Pulldown", sets: 3, reps: 10, weightKg: 52),
                .init(name: "Dumbbell Row", sets: 3, reps: 10, weightKg: 34),
                .init(name: "Face Pull", sets: 3, reps: 15, weightKg: 15),
                .init(name: "Back Extension", sets: 3, reps: 12, weightKg: nil),
                .init(name: "Plank", sets: 3, reps: 1, weightKg: nil, seconds: 45),
            ]
        ))
    )

    static let rehab = GuidedSession(
        key: "rehab", title: "Knee rehab", watchWorkout: "Flexibility", restSeconds: 20, issues: ["Knee"],
        exercises: [
            .init(issueId: 1, issueTitle: "Knee", index: 0, name: "Wall sit", cue: "Knees at 90°, pain ≤ 3/10",
                  dose: "3 × 45 s", sets: 3, perSide: false, reps: nil, seconds: 45, range: nil),
            .init(issueId: 1, issueTitle: "Knee", index: 1, name: "Step-down", cue: "Slow, knee over toes",
                  dose: "3 × 10", sets: 3, perSide: true, reps: 10, seconds: nil, range: nil),
        ],
        durationMin: 8
    )

    static func session() -> StrengthSession {
        var id = 100
        func sets(_ count: Int, reps: Int, kg: Double?, rest: Int, done: Int, seconds: Int? = nil) -> [StrengthSession.WorkoutSet] {
            (1...count).map { order in
                id += 1
                let isDone = order <= done
                return StrengthSession.WorkoutSet(
                    id: id, setOrder: order, targetReps: reps, targetWeightKg: kg, restSeconds: rest,
                    actualReps: isDone ? reps : nil, actualWeightKg: isDone ? kg : nil,
                    status: isDone ? "completed" : "pending", setType: "working", effort: isDone ? "solid" : nil,
                    targetSeconds: seconds
                )
            }
        }
        let hold = stage == "hold"
        return StrengthSession(
            id: 999, templateId: 3, templateName: "Workout B", status: "active", startedAt: "2026-10-31T19:00:00",
            completedAt: nil, currentExerciseOrder: hold ? 5 : 2, currentSetOrder: hold ? 1 : 2,
            exercises: [
                .init(id: 1, exerciseOrder: 1, exerciseName: "Lat Pulldown", notes: nil, sets: sets(3, reps: 10, kg: 52, rest: 90, done: 3)),
                .init(id: 2, exerciseOrder: 2, exerciseName: "Dumbbell Row", notes: nil, sets: sets(3, reps: 10, kg: 34, rest: 90, done: 1)),
                .init(id: 3, exerciseOrder: 3, exerciseName: "Face Pull", notes: nil, sets: sets(3, reps: 15, kg: 15, rest: 60, done: 0)),
                .init(id: 4, exerciseOrder: 4, exerciseName: "Back Extension", notes: nil, sets: sets(3, reps: 12, kg: nil, rest: 60, done: 0)),
                .init(id: 5, exerciseOrder: 5, exerciseName: "Plank", notes: nil, sets: sets(3, reps: 1, kg: nil, rest: 30, done: 0, seconds: 45)),
            ]
        )
    }

    static let last: [String: StrengthTemplate.Last] = [
        "Dumbbell Row": .init(date: "2026-10-27", weightKg: 33.5, reps: 10, setCount: 3),
        "Lat Pulldown": .init(date: "2026-10-27", weightKg: 52, reps: 10, setCount: 3),
    ]
}

import SwiftUI
import WidgetKit

/// `-watchDemoStage widgets`: the Watch widgets drawn at their sizes, since the simulator can't
/// open the Smart Stack or the face editor. `widgetsDone` / `widgetsRest` / `widgetsEvening` show
/// the other states.
struct WidgetGalleryDemo: View {
    let stage: String

    private var entry: GlanceEntry {
        var snapshot = WidgetSnapshot.watchPreview
        var date = Date.now
        switch stage {
        case "widgetsDone":
            snapshot.today = snapshot.today.map {
                var done = WidgetSnapshot.Today(date: $0.date, title: $0.title, sport: $0.sport, durationMin: 52, isDone: true,
                                                readiness: "green", streakDays: 5, weekDoneMin: 219, weekPlannedMin: 370, weekBySport: [])
                done.tomorrow = $0.tomorrow
                done.week = $0.week
                done.rehab = $0.rehab
                return done
            }
        case "widgetsRest":
            snapshot.today = snapshot.today.map {
                var rest = WidgetSnapshot.Today(date: $0.date, title: nil, sport: "rest", durationMin: nil, isDone: false,
                                                readiness: "green", streakDays: 4, weekDoneMin: 219, weekPlannedMin: 370, weekBySport: [])
                rest.tomorrow = .init(sport: "strength", durationMin: 50)
                rest.week = $0.week
                return rest
            }
        case "widgetsEvening":
            date = Calendar.current.date(bySettingHour: 19, minute: 5, second: 0, of: .now) ?? .now
            snapshot.food = snapshot.food.map { .init(date: $0.date, eatenKcal: 1540, targetKcal: 2780, proteinG: 84, proteinTargetG: 140) }
        default: break
        }
        return GlanceEntry(date: date, snapshot: snapshot, relevance: nil)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 6) {
                card { TodayGlance(entry: entry, forced: .accessoryRectangular) }
                card { RehabGlance(entry: entry, forced: .accessoryRectangular) }
                card { FoodGlance(entry: entry, forced: .accessoryRectangular) }
                card { WeekGlance(entry: entry, forced: .accessoryRectangular) }
                HStack(spacing: 4) {
                    circle { TodayGlance(entry: entry, forced: .accessoryCircular) }
                    circle { WeekGlance(entry: entry, forced: .accessoryCircular) }
                    circle { FoodGlance(entry: entry, forced: .accessoryCircular) }
                }
                HStack(spacing: 4) {
                    circle { RehabGlance(entry: entry, forced: .accessoryCircular) }
                    Text(WatchGlance.inline(entry.today)).font(.system(size: 13, weight: .semibold)).lineLimit(1)
                }
            }
        }
    }

    private func card(@ViewBuilder _ content: () -> some View) -> some View {
        content()
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 20))
    }

    private func circle(@ViewBuilder _ content: () -> some View) -> some View {
        content().frame(width: 52, height: 52)
    }
}
#endif
