import Foundation

extension StrengthSessionModel {
    /// The session screen's model, or with `-strengthDemo set|warmup|history` a canned Workout D
    /// for screenshots (frames in iOSLiftHistory.dc.html). The demo talks to a dead address and keeps
    /// its own queue and session files, so nothing reaches the Mac or the live workout.
    static func launch(templateId: Int?, oneTime: TemplateInput?) -> StrengthSessionModel {
        #if DEBUG
        if let stage = UserDefaults.standard.string(forKey: "strengthDemo") {
            return demo(stage)
        }
        #endif
        return StrengthSessionModel(templateId: templateId, oneTime: oneTime)
    }

    #if DEBUG
    static var demoStage: String? { UserDefaults.standard.string(forKey: "strengthDemo") }

    static func demo(_ stage: String) -> StrengthSessionModel {
        let scratch = FileManager.default.temporaryDirectory
        let model = StrengthSessionModel(
            templateId: nil,
            client: { APIClient(baseURL: "http://127.0.0.1:9") },
            queue: WriteQueue(file: scratch.appending(path: "demo-write-queue.json")),
            store: SessionStore(file: scratch.appending(path: "demo-strength-session.json"))
        )
        let session = StrengthDemo.session()
        let squat = session.exercises[0].id
        model.applyDemo(
            session: session,
            history: StrengthDemo.history,
            kit: StrengthDemo.kit,
            hints: ["Back Squat": "Travel today: holding 77.5 kg on every lift. Match last time."],
            rampDone: stage == "warmup" ? [] : [squat],
            ticks: stage == "warmup" ? [0] : []
        )
        return model
    }
    #endif
}

#if DEBUG
enum StrengthDemo {
    /// Live on 3 Nov: the 10 kg bar and plates from the Athlete page.
    static let kit = GymKit(barWeightKg: 10, plates: [
        .init(kg: 20, count: 2), .init(kg: 5, count: 4), .init(kg: 2.5, count: 4), .init(kg: 1.25, count: 8),
    ])

    static func session(now: Date = .now) -> StrengthSession {
        var nextId = 900
        func sets(_ count: Int, reps: Int, kg: Double?, seconds: Int? = nil, rest: Int = 150) -> [StrengthSession.WorkoutSet] {
            (1...count).map { order in
                nextId += 1
                return .init(id: nextId, setOrder: order, targetReps: reps, targetWeightKg: kg, restSeconds: rest,
                             actualReps: nil, actualWeightKg: nil, status: "pending", setType: "working", effort: nil,
                             targetSeconds: seconds, actualSeconds: nil)
            }
        }
        let lifts: [(String, [StrengthSession.WorkoutSet])] = [
            ("Back Squat", sets(3, reps: 6, kg: 77.5)),
            ("Romanian Deadlift", sets(3, reps: 8, kg: 77.5)),
            ("Dumbbell Bulgarian Split Squat", sets(3, reps: 8, kg: 16, rest: 90)),
            ("Standing Dumbbell Calf Raise", sets(3, reps: 12, kg: 24, rest: 60)),
            ("Hanging Leg Raise", sets(3, reps: 10, kg: nil, rest: 60)),
            ("Plank", sets(3, reps: 1, kg: nil, seconds: 45, rest: 60)),
        ]
        let started = ISO8601DateFormatter().string(from: now.addingTimeInterval(-760))
        return StrengthSession(
            id: -1, templateId: 5, templateName: "Workout D · Lower + Core", status: "active", startedAt: started,
            completedAt: nil, currentExerciseOrder: 1, currentSetOrder: 1,
            exercises: lifts.enumerated().map { index, lift in
                .init(id: 800 + index, exerciseOrder: index + 1, exerciseName: lift.0, notes: nil, sets: lift.1)
            }
        )
    }

    /// Live Back Squat history on 3 Nov; the efforts before Oct 15 are made up.
    static let history: [LiftHistory] = {
        func session(_ date: String, _ kg: Double, _ reps: [Int], _ efforts: [String?]) -> LiftHistory.Session {
            .init(date: date, sets: zip(reps, efforts).map { .init(reps: $0, weightKg: kg, seconds: nil, effort: $1) },
                  topLoadKg: kg, bestReps: reps.max(), bestSeconds: nil)
        }
        return [
            LiftHistory(exerciseName: "Back Squat", sessionCount: 14, sessions: [
                session("2026-10-15", 77.5, [6, 6, 6], [nil, "solid", "solid"]),
                session("2026-09-22", 75, [6, 6, 6], ["solid", "solid", nil]),
                session("2026-09-10", 60, [6, 6], [nil, nil]),
                session("2026-09-02", 80, [6, 6, 6], ["solid", "grinding", "grinding"]),
            ], best: .init(date: "2026-02-19", weightKg: 80, reps: 8, seconds: nil)),
            LiftHistory(exerciseName: "Plank", sessionCount: 2, sessions: [
                .init(date: "2026-10-31", sets: [.init(reps: 1, weightKg: nil, seconds: 40, effort: nil)],
                      topLoadKg: nil, bestReps: 1, bestSeconds: 40),
            ], best: .init(date: "2026-10-31", weightKg: nil, reps: 1, seconds: 40)),
        ]
    }()
}
#endif
