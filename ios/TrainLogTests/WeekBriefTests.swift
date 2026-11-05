import Foundation
import Testing
@testable import TrainLog

struct WeekBriefTests {
    /// `GET /plans/week-brief?week_start=2026-11-09` on 5 Nov: knee protected, Base week 1, slots A · C for D · B.
    private let briefJSON = """
    {"week_start": "2026-11-09", "headline": "Base wk 1/5 · 3.5 h rides · Z2 only · 3 lifts · knee protected",
     "lines": [
      {"priority": "safety", "priority_label": "Safety", "text": "Left outside of left knee, probably ITBS: no lower-body lifts, rides easy and flat with a pain check (go if 0-2/10 at rest)", "source": "Recovery, pain 1/10", "key": "injury:2"},
      {"priority": "anchor", "priority_label": "Anchor", "text": "Lift three times per week: Workout A · Upper Press, Workout C · Wide Shoulders (for Workout D · Lower + Core), Workout B · Upper Pull", "source": "Anchor goal", "key": "goal:4"},
      {"priority": "block", "priority_label": "Block", "text": "Rides about 3.5 h: 3× Z2, no sweet spot or VO2", "source": "Winter arc: Base wk 1/5", "key": "arc"},
      {"priority": "outcome", "priority_label": "Outcome", "text": "Build climb power: 210 W for 15 min: waits for a quality block (Base has none)", "source": "Goal, after the block", "key": "goal:6"},
      {"priority": "habit", "priority_label": "Habit", "text": "Long ride Sat/Sun", "source": "Athlete settings", "key": "long_days"},
      {"priority": "habit", "priority_label": "Habit", "text": "Key sessions Mon/Tue/Wed, not Sun", "source": "Plan follow-through", "key": "key_days"}],
     "block": {"block_id": 1, "label": "Base", "focus": "base", "focus_label": "Base", "week_start": "2026-11-09", "week_number": 1,
      "weeks_in_block": 5, "weeks_left": 4, "lighter": false, "ride_hours": 3.5, "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "key_types": ["z2"]},
     "lifts": {"mode": "slots", "slots": [
      {"slot": "Upper 1", "template_id": "strength-a", "workout_template_id": 2, "label": "Workout A · Upper Press", "focus_area": "upper", "swapped_from": null, "reason": null},
      {"slot": "Lower", "template_id": "strength-c", "label": "Workout C · Wide Shoulders", "focus_area": "upper", "swapped_from": "Workout D · Lower + Core", "reason": "Knee protected"},
      {"slot": "Upper 2", "template_id": "strength-b", "label": "Workout B · Upper Pull", "focus_area": "upper", "swapped_from": null, "reason": null}], "next": null},
     "protected_areas": ["knee"], "priority": ["Safety", "Anchor", "Block", "Outcome", "Habit"]}
    """

    private func brief() throws -> WeekBrief {
        try APIClient.decoder.decode(WeekBrief.self, from: Data(briefJSON.utf8))
    }

    /// Mon A done, Tue Z2 70 done, Wed C planned, Sat long Z2 90, Sun Z2 50.
    private func week() throws -> WeeklyPlan {
        let json = """
        {"week_start": "2026-11-09", "title": "Base wk 1/5", "focus": "Three upper lifts", "days": [
         {"date": "2026-11-09", "session_type": "strength", "title": "Workout A · Upper Press", "template_label": "Workout A · Upper Press", "target_duration_min": 55, "comparison": {"status": "matched"}},
         {"date": "2026-11-10", "session_type": "ride", "workout_intent": "easy", "title": "Z2 endurance ride 70 min", "target_duration_min": 70, "comparison": {"status": "matched"}},
         {"date": "2026-11-11", "session_type": "strength", "title": "Workout C · Wide Shoulders", "template_label": "Workout C · Wide Shoulders", "target_duration_min": 55},
         {"date": "2026-11-12", "session_type": "recovery", "title": "Rehab: left knee", "target_duration_min": 25},
         {"date": "2026-11-13", "session_type": "strength", "title": "Workout B · Upper Pull", "template_label": "Workout B · Upper Pull", "target_duration_min": 55},
         {"date": "2026-11-14", "session_type": "ride", "workout_intent": "long", "title": "Long Z2 ride 90 min", "target_duration_min": 90},
         {"date": "2026-11-15", "session_type": "ride", "workout_intent": "easy", "title": "Easy Z2 ride 50 min", "target_duration_min": 50}]}
        """
        return try APIClient.decoder.decode(WeeklyPlan.self, from: Data(json.utf8))
    }

    @Test func decodesTheBrief() throws {
        let brief = try brief()
        #expect(brief.lines.map(\.priority) == ["safety", "anchor", "block", "outcome", "habit", "habit"])
        #expect(brief.lifts.slots.map(\.slot) == ["Upper 1", "Lower", "Upper 2"])
        #expect(brief.lifts.slots[1].swappedFrom == "Workout D · Lower + Core")
        #expect(brief.block?.rideHours == 3.5)
        #expect(WeekBriefFormat.moreCount(brief) == 3)
        #expect(WeekBriefFormat.sheetTitle(brief) == "Base wk 1 of 5")
    }

    @Test func cardShowsSafetyThenSlotsThenRides() throws {
        let rules = WeekBriefFormat.rules(try brief(), week: try week(), today: "2026-11-11")
        #expect(rules.map(\.kind) == [.safety, .anchor, .block])
        #expect(rules[0].lead == "Left outside of left knee")
        #expect(rules[0].text.hasPrefix("no lower-body lifts"))
        #expect(rules[1].kicker == "Lift 3× · anchor")
        #expect(rules[1].slots == [
            .init(code: "A", name: "Upper Press", swapped: false, done: true, workoutTemplateId: 2),
            .init(code: "C", name: "for D · knee", swapped: true, done: false),
            .init(code: "B", name: "Upper Pull", swapped: false, done: false),
        ])
        #expect(rules[2].kicker == "Base · rides")
        #expect(rules[2].text == "3× Z2 · 3.5 h · no SS / VO2")
        #expect(rules[2].rides.map(\.minutes) == [70, 90, 50])
        #expect(rules[2].rides.map(\.done) == [true, false, false])
    }

    @Test func rideTextNamesQualityAndLighterWeeks() {
        let block = WeekBrief.Block(label: "Sweet-spot build", weekNumber: 3, weeksInBlock: 6, lighter: true, rideHours: 2.6,
                                    rideMix: .init(z2: 2, sweetSpot: 1, vo2: 0))
        #expect(WeekBriefFormat.rideText(block) == "1× SS · 2× Z2 · 2.6 h · lighter")
    }

    @Test func rotationAnchorStaysText() throws {
        var brief = try brief()
        brief = WeekBrief(weekStart: brief.weekStart, headline: "", lines: [brief.lines[1]], lifts: .init(mode: "rotation", next: "Workout B · Upper Pull"))
        let rule = try #require(WeekBriefFormat.rules(brief, week: try week(), today: "2026-11-11").first)
        #expect(rule.slots.isEmpty)
        #expect(rule.lead == "Lift three times per week")
    }

    @Test func ruleReasonsReadAsOneLine() {
        #expect(WeekBriefFormat.reason("Week brief: knee protected, so no hard rides") == "Knee protected, so no hard rides")
        #expect(WeekBriefFormat.reason("Winter arc: Base has no sweet spot rides, so this one is Z2") == "Base has no sweet spot rides, so this one is Z2")
        #expect(WeekBriefFormat.reason("Weekly lifts: Lower (Knee protected: Workout C · Wide Shoulders instead of Workout D · Lower + Core)")
                == "Lower slot: C for D, knee protected")
        #expect(WeekBriefFormat.reason("Weekly lifts: Upper 1") == nil)
        #expect(WeekBriefFormat.reason(nil) == nil)
    }

    @Test func compactsWeeklyGoalWording() {
        #expect(WeekBriefFormat.compact("Lift three times per week") == "Lift 3×")
        #expect(WeekBriefFormat.code("Workout C · Wide Shoulders") == "C")
        #expect(WeekBriefFormat.title("Workout C · Wide Shoulders") == "Wide Shoulders")
    }
}
