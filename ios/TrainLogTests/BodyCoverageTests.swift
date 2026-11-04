import Foundation
import Testing
@testable import TrainLog

struct BodyCoverageTests {
    private let today = "2026-11-05"  // Thursday

    private func group(_ key: String, _ done: Int, _ planned: Int = 0, _ status: String = "low") -> PhoneBody.CoverageGroup {
        PhoneBody.CoverageGroup(key: key, label: key.capitalized, doneSets: done, plannedSets: planned, status: status)
    }

    private func day(_ date: String, _ sets: [String: Int], state: String = "planned") -> PhoneBody.CoverageDay {
        PhoneBody.CoverageDay(date: date, title: "Lift", state: state, groupSets: sets)
    }

    private func summary(_ groups: [PhoneBody.CoverageGroup], _ days: [PhoneBody.CoverageDay], hasPlan: Bool = true,
                         training: [PhoneBody.TrainingSession] = []) -> CoverageSummary {
        CoverageSummary(coverage: PhoneBody.Coverage(weekStart: "2026-11-02", target: 8, hasPlan: hasPlan, groups: groups, days: days),
                        training: training, today: today)
    }

    @Test func decodesCoverage() throws {
        let json = """
        {"date": "2026-11-05", "readiness": {"level": "red", "label": "Red", "factors": []},
         "vitals": {}, "load": {"fitness": 46, "fatigue": 31, "form": 15, "ratio": 0.67, "ratio_status": "recovery", "chart": []},
         "coverage": {"week_start": "2026-11-02", "target": 8, "has_plan": true,
           "groups": [{"key": "legs", "label": "Legs", "done_sets": 0, "planned_sets": 0, "status": "protected"},
                      {"key": "chest", "label": "Chest", "done_sets": 3, "planned_sets": 5, "status": "in_range"}],
           "days": [{"date": "2026-11-06", "title": "Workout B", "state": "planned", "group_sets": {"back": 11, "chest": 3}}]}}
        """
        let body = try APIClient.decoder.decode(PhoneBody.self, from: Data(json.utf8))
        #expect(body.coverage?.hasPlan == true)
        #expect(body.coverage?.groups.last?.plannedSets == 5)
        #expect(body.coverage?.days.first?.groupSets["chest"] == 3)
    }

    @Test func olderServersWithoutCoverageStillDecode() throws {
        let json = """
        {"date": "2026-11-05", "readiness": {"level": "red", "label": "Red", "factors": []},
         "vitals": {}, "load": {"fitness": 46, "fatigue": 31, "form": 15, "ratio": 0.67, "ratio_status": "recovery", "chart": []}}
        """
        #expect(try APIClient.decoder.decode(PhoneBody.self, from: Data(json.utf8)).coverage == nil)
    }

    @Test func liveWeekSkipsTheProtectedKneeAndNamesBothDaysForChest() {
        let result = summary(
            [group("legs", 0, 0, "protected"), group("back", 3, 11), group("chest", 3, 5), group("shoulders", 18, 19, "high"), group("arms", 9, 11, "high")],
            [day("2026-11-04", ["chest": 7], state: "done"), day("2026-11-06", ["back": 11, "chest": 3]), day("2026-11-07", ["chest": 2, "shoulders": 15])]
        )
        // Back and chest both sit at 3; chest has less planned, so it's the real gap.
        #expect(result.headline == "Chest 3/8 · Tomorrow and Saturday close it.")
        #expect(result.rows.first?.hold == .protected)
        #expect(!result.isWin)
    }

    @Test func oneDayThatReachesTheTargetIsNamed() {
        let result = summary([group("legs", 0, 8), group("back", 9)], [day("2026-11-06", ["back": 4]), day("2026-11-07", ["legs": 8])])
        #expect(result.headline == "Legs 0/8 · Saturday’s lift can fix it.")
    }

    @Test func todayAndTomorrowReadAsWords() {
        let today = summary([group("legs", 0, 8)], [day("2026-11-05", ["legs": 8])])
        #expect(today.headline == "Legs 0/8 · Today’s lift can fix it.")
        let both = summary([group("legs", 0, 8)], [day("2026-11-06", ["legs": 4]), day("2026-11-08", ["legs": 4])])
        #expect(both.headline == "Legs 0/8 · Tomorrow and Sunday close it.")
    }

    @Test func daysThatFallShortSayHowFarTheyGet() {
        let result = summary([group("legs", 0, 3)], [day("2026-11-07", ["legs": 3])])
        #expect(result.headline == "Legs 0/8 · Saturday’s lift takes it to 3.")
        let none = summary([group("legs", 0)], [day("2026-11-07", ["back": 6])])
        #expect(none.headline == "Legs 0/8 · no planned lift trains it.")
    }

    @Test func noDaysLeftOrNoPlanGetASecondLine() {
        let late = summary([group("legs", 0), group("back", 10)], [day("2026-11-03", ["legs": 6], state: "missed")])
        #expect(late.headline == "Legs 0/8 · no lift days left this week.")
        #expect(late.detail == "Start next week with legs.")
        let unplanned = summary([group("legs", 0)], [], hasPlan: false)
        #expect(unplanned.headline == "Legs 0/8 · no lift planned yet.")
        #expect(unplanned.detail != nil)
    }

    @Test func everyGroupAtTargetIsAWin() {
        let all = summary([group("legs", 9), group("back", 12)], [])
        #expect(all.isWin)
        #expect(all.headline == "Every group hit 8. Week covered.")
        let hiking = summary([group("legs", 0, 0, "hiking"), group("back", 12)], [])
        #expect(hiking.isWin)
        #expect(hiking.headline == "Everything else hit 8. Week covered.")
    }

    @Test func mapCountsPrimarySetsLoggedSinceMonday() {
        let training = [
            PhoneBody.TrainingSession(date: "2026-11-03", sport: "strength", title: nil, minutes: 40,
                                      exercises: [PhoneBody.Exercise(name: "Dumbbell Lateral Raise", sets: 5), PhoneBody.Exercise(name: "Dumbbell Row", sets: 3)]),
            PhoneBody.TrainingSession(date: "2026-11-04", sport: "strength", title: nil, minutes: 40,
                                      exercises: [PhoneBody.Exercise(name: "Dumbbell Lateral Raise", sets: 3)]),
            // Last week doesn't count.
            PhoneBody.TrainingSession(date: "2026-10-30", sport: "strength", title: nil, minutes: 40,
                                      exercises: [PhoneBody.Exercise(name: "Back Squat", sets: 4)]),
        ]
        let sets = summary([group("legs", 0)], [], training: training).muscleSets
        #expect(sets[.shoulders] == 8)
        #expect(sets[.lats] == 3)
        #expect(sets[.biceps] == nil)  // a helper on rows, not a primary
        #expect(sets[.quads] == nil)
    }

    @Test func rampRunsFromGreyThroughPaleToFullPink() {
        #expect(CoverageRamp.rgb(0) == CoverageRamp.empty)
        #expect(CoverageRamp.rgb(1) == (0x5B, 0x35, 0x50))
        #expect(CoverageRamp.rgb(8) == (0xFF, 0x4D, 0x9A))
        #expect(CoverageRamp.rgb(18) == CoverageRamp.rgb(8))
        #expect(CoverageRamp.rgb(4).r < CoverageRamp.rgb(6).r)
    }
}
