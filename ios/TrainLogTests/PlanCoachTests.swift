import Foundation
import Testing
@testable import TrainLog

struct PlanCoachTests {
    private func day(_ date: String, _ type: String, _ title: String, _ minutes: Int?, status: String = "not_completed_yet") -> PlanDay {
        PlanDay(sessionId: date, date: date, label: nil, sessionType: type, workoutIntent: nil, workoutIntentLabel: nil,
                templateLabel: nil, title: title, details: nil, check: nil, steps: nil, cues: nil, fallback: nil,
                targetDurationMin: minutes, targetDistanceKm: nil, cyclingWorkoutName: nil,
                comparison: PlanDay.Comparison(status: status, label: nil, completedActivities: nil), rehab: nil)
    }

    /// Week 45 as it was on 3 Nov: Mon done, Tue today.
    private var week45: WeeklyPlan {
        WeeklyPlan(weekStart: "2026-11-02", title: nil, focus: nil, days: [
            day("2026-11-02", "recovery", "Rehab: left knee", 25, status: "matched"),
            day("2026-11-03", "strength", "Bodyweight upper + core (short, travel day)", 25),
            day("2026-11-04", "strength", "Workout A · Upper Chest", 45),
            day("2026-11-05", "ride", "Easy spin (knee-gated) + rehab", 40),
            day("2026-11-06", "strength", "Workout B · Back + Arms", 50),
            day("2026-11-07", "strength", "Workout C · Wide Shoulders", 45),
            day("2026-11-08", "ride", "Sweet spot 3 × 10 min (knee-gated)", 70),
        ])
    }

    @Test func decodesJobAndStatus() throws {
        let job = try APIClient.decoder.decode(CoachPlanJob.self, from: Data("""
        {"job_id": "abc", "kind": "weekly_plan", "status": "succeeded", "message": "The weekly plan was saved.",
         "summary": "Three lifts.", "week_start": "2026-11-09", "created_at": "x"}
        """.utf8))
        #expect(job.jobId == "abc" && job.status == "succeeded" && job.summary == "Three lifts." && job.weekStart == "2026-11-09")
        let status = try APIClient.decoder.decode(CoachPlanStatus.self, from: Data(#"{"available": false, "detail": "down"}"#.utf8))
        #expect(!status.available && status.detail == "down")
    }

    @Test func encodesRevisionWithoutEmptyTargetDate() throws {
        let week = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(CoachRevisionRequest(weekStart: "2026-11-02", feedback: "Less", targetDate: nil))) as? [String: String]
        #expect(week == ["week_start": "2026-11-02", "feedback": "Less"])
        let day = try JSONSerialization.jsonObject(with: APIClient.encoder.encode(CoachRevisionRequest(weekStart: "2026-11-02", feedback: "Less", targetDate: "2026-11-06"))) as? [String: String]
        #expect(day?["target_date"] == "2026-11-06")
    }

    @Test func offersNextWeekOnceThisOneIsSaved() {
        #expect(PlanCoachFormat.unplannedStart(["2026-10-26", "2026-11-02"], today: "2026-11-03") == "2026-11-09")
        #expect(PlanCoachFormat.unplannedStart(["2026-11-02", "2026-11-09"], today: "2026-11-03") == nil)
        // Nothing covers this week: plan this week first.
        #expect(PlanCoachFormat.unplannedStart(["2026-10-19"], today: "2026-11-03") == "2026-11-02")
        #expect(PlanCoachFormat.unplannedStart([], today: "2026-11-08") == "2026-11-02")
    }

    @Test func editableDaysSkipThePastAndDoneToday() {
        #expect(PlanCoachFormat.editableDates(week45, today: "2026-11-03").first == "2026-11-03")
        #expect(PlanCoachFormat.range(PlanCoachFormat.editableDates(week45, today: "2026-11-03")) == "Tue – Sun")
        let doneToday = WeeklyPlan(weekStart: week45.weekStart, title: nil, focus: nil,
                                   days: week45.days.map { $0.date == "2026-11-03" ? day($0.date, "strength", $0.title, 25, status: "matched") : $0 })
        #expect(PlanCoachFormat.range(PlanCoachFormat.editableDates(doneToday, today: "2026-11-03")) == "Wed – Sun")
        #expect(PlanCoachFormat.editableDates(week45, today: "2026-11-09").isEmpty)
    }

    @Test func tappingADayStartsAndRemovesItsLine() {
        var note = PlanCoachFormat.toggleDay("", date: "2026-11-12")
        #expect(note == "Thu: ")
        note += "deadline"
        note = PlanCoachFormat.toggleDay(note, date: "2026-11-14")
        #expect(note == "Thu: deadline\nSat: ")
        #expect(PlanCoachFormat.mentioned(note, in: ["2026-11-12", "2026-11-13", "2026-11-14"]) == ["2026-11-12", "2026-11-14"])
        // A day with words stays; an empty one goes.
        #expect(PlanCoachFormat.toggleDay(note, date: "2026-11-12") == note)
        #expect(PlanCoachFormat.toggleDay(note, date: "2026-11-14") == "Thu: deadline")
        #expect(PlanCoachFormat.adding("Keep Friday free", to: "Thu: deadline") == "Thu: deadline\nKeep Friday free")
    }

    @Test func stageDropsTheCoachLead() {
        #expect(PlanCoachFormat.stage("The coach is reviewing your training context.") == "Reviewing your training context")
        #expect(PlanCoachFormat.stage("Weekly planning is queued.") == "Queued on the Mac")
        #expect(PlanCoachFormat.stage(nil) == "The coach is working")
    }

    @Test func changesListOnlyDaysThatDiffer() {
        var after = week45.days
        after[4] = day("2026-11-06", "recovery", "Rehab: left knee", 20)
        after.remove(at: 5)
        let changes = PlanCoachFormat.changes(before: week45.days, after: after)
        #expect(changes == [
            .init(date: "2026-11-06", was: "Workout B · Back + Arms · 50 min", now: "Rehab: left knee · 20 min"),
            .init(date: "2026-11-07", was: "Workout C · Wide Shoulders · 45 min", now: nil),
        ])
        #expect(PlanCoachFormat.changes(before: week45.days, after: week45.days).isEmpty)
    }

    @Test func mixAndWeekLine() {
        #expect(PlanCoachFormat.mix(week45.days).map(\.label) == ["4 lifts", "2 rides", "rehab"])
        #expect(PlanCoachFormat.weekLine(week45) == "4 lifts · 2 rides · rehab · 5h 00")
    }

    @Test func resultRingsChangedDaysAndFadesPastOnes() {
        var after = week45.days
        after[4] = day("2026-11-06", "recovery", "Rehab: left knee", 20)
        let changed = WeeklyPlan(weekStart: week45.weekStart, title: nil, focus: nil, days: after)
        let result = PlanCoachFormat.result(.refine(week: "2026-11-02"), before: week45.days, after: changed,
                                            today: "2026-11-03", summary: "  ", seconds: 140)
        #expect(result.changes.map(\.date) == ["2026-11-06"])
        #expect(result.days.map(\.style) == [.past, .today, .normal, .normal, .changed, .normal, .normal])
        #expect(result.summary == nil)
        #expect(PlanCoachFormat.clock(result.seconds) == "2:20")
    }

    @Test func taskRoundTripsForResume() throws {
        let task = PlanCoachTask.day(week: "2026-11-02", date: "2026-11-06")
        let back = try JSONDecoder().decode(PlanCoachTask.self, from: JSONEncoder().encode(task))
        #expect(back == task && back.week == "2026-11-02")
    }
}
