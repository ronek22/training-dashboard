import Foundation
import Testing
@testable import TrainLog

struct BodyMapTests {
    private let today = "2026-11-02"

    private func session(_ date: String, _ sport: String, minutes: Int? = 45, _ exercises: [(String, Int)] = []) -> PhoneBody.TrainingSession {
        PhoneBody.TrainingSession(date: date, sport: sport, title: nil, minutes: minutes,
                                  exercises: exercises.map { PhoneBody.Exercise(name: $0.0, sets: $0.1) })
    }

    private let knee = PhoneBody.Issue(id: 2, title: "Outside of left knee", side: "left", since: "2026-10-24", areas: ["knee"])

    @Test func decodesTrainingIssuesAndDebt() throws {
        let json = """
        {"date": "2026-11-02", "readiness": {"level": "red", "label": "Red", "factors": []},
         "vitals": {}, "load": {"fitness": 46, "fatigue": 31, "form": 15, "ratio": 0.67, "ratio_status": "recovery", "chart": []},
         "sleep_debt": {"hours": 7.6, "nights": 7, "need_h": 7.19, "status": "risk"},
         "training": [{"date": "2026-10-31", "sport": "strength", "title": "Bodyweight", "minutes": 32,
                       "exercises": [{"name": "Push-ups", "sets": 4}]}],
         "issues": [{"id": 2, "title": "Left knee", "side": "left", "since": "2026-10-24", "areas": ["knee"]}]}
        """
        let body = try APIClient.decoder.decode(PhoneBody.self, from: Data(json.utf8))
        #expect(body.sleepDebt?.needH == 7.19)
        #expect(body.training?.first?.exercises?.first?.sets == 4)
        #expect(body.issues?.first?.areas == ["knee"])
    }

    @Test func liftsInTheLast48HoursAreStillRecovering() {
        let summary = BodyMapSummary(training: [
            session("2026-11-01", "strength", [("Push-ups", 4)]),
            session("2026-10-30", "strength", [("Dumbbell Bicep Curl", 3)]),
        ], issues: [], today: today)
        #expect(summary.states[.chest] == .recovering)
        #expect(summary.states[.biceps] == .ready)
        #expect(summary.states[.quads] == .rested)
        #expect(summary.state(.chest) == .recovering)
        #expect(summary.state(.legs) == .rested)
    }

    @Test func ridesCountForTheLegsAndOnlyLongOnesTireThem() {
        let short = BodyMapSummary(training: [session("2026-11-02", "ride", minutes: 44)], issues: [], today: today)
        #expect(short.states[.quads] == .ready)
        let long = BodyMapSummary(training: [session("2026-11-01", "ride", minutes: 120)], issues: [], today: today)
        #expect(long.states[.quads] == .recovering)
        #expect(long.work.first { $0.area == .legs }?.sessions[.ride] == 1)
    }

    @Test func rehabCountsForTheInjuredAreaAndSessionsOlderThanAWeekDrop() {
        let summary = BodyMapSummary(training: [
            session("2026-11-01", "rehab"),
            session("2026-10-26", "strength", [("Barbell Incline Bench Press", 4)]),
        ], issues: [knee], today: today)
        #expect(summary.work.first { $0.area == .legs }?.sessions[.rehab] == 1)
        #expect(summary.states[.chest] == .rested)
        #expect(summary.sportCounts[.strength] == nil)
    }

    @Test func sentencesNameWhatIsFreshAndWhatIsProtected() {
        let summary = BodyMapSummary(training: [
            session("2026-11-01", "strength", [("Push-ups", 4)]),
            session("2026-10-29", "strength", [("Chin Up", 4), ("Dumbbell Lateral Raise", 3)]),
        ], issues: [knee], today: today)
        #expect(summary.headline == "Shoulders, arms and back are fresh.")
        #expect(summary.detail == "Chest needs another day. Left knee stays on rehab. Core and legs: nothing this week.")
        #expect(BodyMapSummary.issueDay(knee, today: today) == 10)
    }

    @Test func pinsSitOnTheAthletesSide() {
        let left = BodyMapSummary.pins(knee)
        #expect(left == [BodyPin(side: .front, point: CGPoint(x: 134, y: 302))])
        let back = PhoneBody.Issue(id: 3, title: "Back", side: nil, since: nil, areas: ["lower_back"])
        #expect(BodyMapSummary.pins(back).count == 1)
        let both = PhoneBody.Issue(id: 4, title: "Knees", side: "both", since: nil, areas: ["knee"])
        #expect(BodyMapSummary.pins(both).map(\.point.x).sorted() == [106, 134])
    }

    @Test func lightsOutLeavesTheNeedPlusPaybackBeforeWaking() {
        // 07:30 − 7.2 h − 30 min payback − 15 min to fall asleep = 23:33, down to the quarter.
        let target = BodyClockMath.lightsOut(wakeMinutes: 450, needH: 7.2, debtH: 7.6)
        #expect(BodyClockMath.clock(minutes: target) == "23:30")
        #expect(BodyClockMath.clock(minutes: BodyClockMath.lightsOut(wakeMinutes: 450, needH: 7.2, debtH: 0)) == "00:00")
        #expect(BodyClockMath.sleepHours(lightsOut: target, wakeMinutes: 450) == 7.75)
    }

    @Test func clockHoursWrapLastEvening() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Warsaw")!
        let day = try! Date("2026-11-02T12:00:00+01:00", strategy: .iso8601)
        let bedtime = try! Date("2026-11-01T23:30:00+01:00", strategy: .iso8601)
        #expect(BodyClockMath.hour(bedtime, day: day, calendar: calendar) == 23.5)
    }

    @Test func vitalNotesCallOutTheBestDayAndTheDirection() {
        let days = [42.6, 36.6, 39.6, 30.4, 36.8, 38.3, 56.4].enumerated().map { PhoneBody.Day(date: "d\($0.offset)", value: $0.element) }
        let hrv = PhoneBody.Vital(date: today, value: 56.4, baseline: 46.4, days: days)
        #expect(VitalNote.make(kind: .hrv, vital: hrv) == VitalNote(text: "▲ best this week", tone: .good))
        let rhr = PhoneBody.Vital(date: today, value: 77, baseline: 68.6,
                                  days: [68, 57, 59, 81, 79, 63, 77].map { PhoneBody.Day(date: "d", value: $0) })
        #expect(VitalNote.make(kind: .restingHr, vital: rhr) == VitalNote(text: "▲ +8 vs normal", tone: .bad))
        let flat = PhoneBody.Vital(date: today, value: 7.1, baseline: 7.0)
        #expect(VitalNote.make(kind: .sleep, vital: flat).text == "normal")
    }
}
