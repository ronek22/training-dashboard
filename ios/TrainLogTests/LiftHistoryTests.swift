import Foundation
import Testing
@testable import TrainLog

struct LiftHistoryTests {
    /// The Athlete page's equipment on 3 Nov: 10 kg bar, one pair of 20s, small plates.
    private let kit = GymKit(barWeightKg: 10, plates: [
        .init(kg: 20, count: 2), .init(kg: 5, count: 4), .init(kg: 2.5, count: 4), .init(kg: 1.25, count: 8),
    ])

    private let json = """
    [{"exercise_name": "Back Squat", "session_count": 14,
      "sessions": [
        {"date": "2026-10-15", "sets": [
          {"reps": 6, "weight_kg": 77.5, "seconds": null, "effort": null},
          {"reps": 6, "weight_kg": 77.5, "seconds": null, "effort": "solid"},
          {"reps": 6, "weight_kg": 77.5, "seconds": null, "effort": "solid"}],
         "top_load_kg": 77.5, "best_reps": 6, "best_seconds": null},
        {"date": "2026-09-10", "sets": [{"reps": 6, "weight_kg": 60.0, "seconds": null, "effort": null}],
         "top_load_kg": 60.0, "best_reps": 6, "best_seconds": null}],
      "best": {"date": "2026-02-19", "weight_kg": 80.0, "reps": 8, "seconds": null}},
     {"exercise_name": "Plank", "session_count": 1,
      "sessions": [{"date": "2026-10-31", "sets": [{"reps": 1, "weight_kg": null, "seconds": 40, "effort": null}],
                    "top_load_kg": null, "best_reps": 1, "best_seconds": 40}],
      "best": {"date": "2026-10-31", "weight_kg": null, "reps": 1, "seconds": 40}}]
    """

    private func decoded() throws -> [LiftHistory] {
        try APIClient.decoder.decode([LiftHistory].self, from: Data(json.utf8))
    }

    @Test func decodesAndWritesTheLastTimeLine() throws {
        let lifts = try decoded()
        let squat = lifts[0]
        #expect(LiftLogic.metric(of: squat) == .load)
        let line = try #require(LiftLogic.lastLine(squat))
        #expect(line.top == "77.5 × 6")
        #expect(line.rest == "3 sets · Oct 15")
        #expect(LiftLogic.setsLine(squat.sessions[0]) == "77.5 kg × 6 · 6 · 6")
        #expect(LiftLogic.feel(squat.sessions[0]) == "Good")
        // Oldest first for the chart.
        #expect(LiftLogic.plotted(squat).map(\.date) == ["2026-09-10", "2026-10-15"])
        let best = try #require(LiftLogic.bestLine(squat, target: 77.5))
        #expect(best.best == "80 kg × 8")
        #expect(best.tail == "on Feb 19 · 2.5 kg above today")

        let plank = lifts[1]
        #expect(LiftLogic.metric(of: plank) == .seconds)
        #expect(LiftLogic.lastLine(plank)?.top == "40 s")
        #expect(LiftLogic.lastLine(plank)?.rest == "1 hold · Oct 31")
    }

    @Test func platesUseWhatYouOwnWithTheFewestPlates() {
        #expect(LiftLogic.fit(77.5, kit: kit) == .plates([20, 5, 5, 2.5, 1.25]))
        #expect(LiftLogic.fit(50, kit: kit) == .plates([20]))
        #expect(LiftLogic.fit(10, kit: kit) == .bar)
        #expect(LiftLogic.fit(8, kit: kit) == .belowBar)
        #expect(LiftLogic.fit(78, kit: kit) == .off(lower: 77.5, upper: 80))
        // 20 + 2×5 + 2×2.5 + 4×1.25 a side is all there is.
        #expect(LiftLogic.totals(kit).last == 90)
        #expect(LiftLogic.fit(95, kit: kit) == .off(lower: 90, upper: nil))
        // Without a profile: the backend's standard 20 kg bar and plates.
        #expect(LiftLogic.fit(77.5, kit: .standard) == .plates([25, 2.5, 1.25]))
    }

    @Test func rampClimbsOnLoadablePlates() {
        let steps = LiftLogic.ramp(to: 77.5, kit: kit)
        #expect(steps.map(\.weight) == [10, 40, 55, 65])
        #expect(steps.map(\.reps) == [10, 5, 3, 2])
        #expect(steps[1].plates == [5, 5, 2.5, 2.5])
        #expect(steps[0].isBar)
        // Too light to bother.
        #expect(LiftLogic.ramp(to: 30, kit: kit).isEmpty)
    }

    @Test func barbellLiftsByName() {
        #expect(LiftLogic.isBarbell("Back Squat"))
        #expect(LiftLogic.isBarbell("Romanian Deadlift"))
        #expect(LiftLogic.isBarbell("Barbell Incline Bench Press"))
        #expect(LiftLogic.isBarbell("Bent Over Barbell Row"))
        #expect(!LiftLogic.isBarbell("Dumbbell Bench Press"))
        #expect(!LiftLogic.isBarbell("Dumbbell Bulgarian Split Squat"))
        #expect(!LiftLogic.isBarbell("Goblet Squat"))
    }

    @Test func historyPathAsksForEveryLiftOnce() {
        let path = LiftLogic.historyPath(for: ["Back Squat", "Plank", "Back Squat", "Push-ups + hold"])
        #expect(path == "/strength/workouts/exercise-history?name=Back%20Squat&name=Plank&name=Push-ups%20%2B%20hold")
        #expect(LiftLogic.historyPath(for: []) == nil)
    }

    @Test func plateWeightsKeepTheirHundredths() {
        #expect(LiftLogic.kg(1.25) == "1.25")
        #expect(LiftLogic.kg(33.75) == "33.75")
        #expect(LiftLogic.kg(20) == "20")
        #expect(LiftLogic.kg(2.5) == "2.5")
    }
}
