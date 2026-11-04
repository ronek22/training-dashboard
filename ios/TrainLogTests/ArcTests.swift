import Foundation
import Testing
@testable import TrainLog

struct ArcTests {
    /// `GET /plans/winter-arc` with an arc from Oct 19: Base 6 wk (lighter wk 4), Sweet-spot build 6 wk
    /// (lighter wks 3 and 6), then a week's break and VO2 touch 6 wk.
    private let arcJSON = """
    {"today": "2026-11-05", "start_date": "2026-10-19", "end_date": "2027-03-07", "status": "active",
     "current": null, "upcoming": null, "recent_ride_hours": 2.5, "focuses": [], "adjustment": {"suggestion": null, "last": null},
     "blocks": [
      {"id": 1, "start_date": "2026-10-19", "end_date": "2026-11-29", "weeks": 6, "focus": "base", "focus_label": "Base",
       "label": "Base", "weekly_hours": 3.0, "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "key_types": ["z2"],
       "lighter_every": 4, "lighter_weeks": ["2026-11-09"]},
      {"id": 2, "start_date": "2026-11-30", "end_date": "2027-01-10", "weeks": 6, "focus": "sweet_spot",
       "focus_label": "Sweet-spot build", "label": "", "weekly_hours": 3.5, "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 0},
       "key_types": ["sweet_spot"], "lighter_every": 3, "lighter_weeks": ["2026-12-14", "2027-01-04"]},
      {"id": 3, "start_date": "2027-01-18", "end_date": "2027-02-28", "weeks": 6, "focus": "vo2", "focus_label": "VO2 touch",
       "label": "VO2 touch", "weekly_hours": 3.5, "ride_mix": {"z2": 2, "sweet_spot": 1, "vo2": 1}, "key_types": ["vo2"],
       "lighter_every": 0, "lighter_weeks": []}
     ]}
    """

    /// The live active stall block on 5 Nov.
    private let stallJSON = """
    [{"id": 2, "exercise_name": "Dumbbell Upright Row", "applied_name": "Dumbbell Upright Row", "kind": "rep_scheme",
      "label": "Rep scheme", "text": "Switch to 3 × 12–15 at 18 kg for 3 weeks, last set close to failure.",
      "plan": {"weeks": 3, "sets": 3, "reps": 12, "reps_max": 15, "load_kg": 18.0, "swap_to": null, "cue": "last set close to failure"},
      "scope": "block", "status": "active", "started_on": "2026-10-12", "ends_on": "2026-11-02", "week": 3, "weeks": 3,
      "due": true, "session_id": 27, "stall": {"e1rm": 26.7}, "ended_on": null, "outcome": null}]
    """

    private func blocks() throws -> [WinterArc.Block] {
        try APIClient.decoder.decode(WinterArc.self, from: Data(arcJSON.utf8)).blocks
    }

    private func stall() throws -> StallBlock {
        try #require(try APIClient.decoder.decode([StallBlock].self, from: Data(stallJSON.utf8)).first)
    }

    @Test func decodesTheArc() throws {
        let blocks = try blocks()
        #expect(blocks.count == 3)
        #expect(blocks[0].rideMix == WinterArc.RideMix(z2: 3, sweetSpot: 0, vo2: 0))
        #expect(blocks[1].name == "Sweet-spot build")
        #expect(blocks[0].lighterWeeks == ["2026-11-09"])
    }

    @Test func decodesTheEmptyArc() throws {
        let empty = #"{"today": "2026-11-05", "blocks": [], "start_date": null, "status": "none"}"#
        #expect(try APIClient.decoder.decode(WinterArc.self, from: Data(empty.utf8)).blocks.isEmpty)
    }

    @Test func midBlockWithALighterWeekNext() throws {
        let strip = try #require(ArcFormat.strip(try blocks(), weekStart: "2026-11-02"))
        #expect(strip.lead == "Base")
        #expect(strip.detail == "week 3 of 6")
        #expect(strip.next == "Lighter week next")
        #expect(strip.tape.map(\.count) == [6, 6, 6])
        #expect(strip.tape[0].map(\.state) == [.past, .past, .current, .future, .future, .future])
        #expect(strip.tape[0][3].lighter)
    }

    @Test func lighterWeekPointsBackToFullHours() throws {
        let strip = try #require(ArcFormat.strip(try blocks(), weekStart: "2026-11-09"))
        #expect(strip.detail == "week 4 of 6 · lighter")
        #expect(strip.next == "Back to 3 h next")
    }

    @Test func ordinaryWeekCountsWhatsLeft() throws {
        #expect(ArcFormat.strip(try blocks(), weekStart: "2026-10-19")?.next == "5 weeks left")
        #expect(ArcFormat.strip(try blocks(), weekStart: "2026-11-16")?.next == "1 week left")
        #expect(ArcFormat.strip(try blocks(), weekStart: "2026-12-07")?.next == "Lighter week next")
    }

    @Test func lastWeekOfABlockNamesTheNextOne() throws {
        let strip = try #require(ArcFormat.strip(try blocks(), weekStart: "2026-11-23"))
        #expect(strip.detail == "week 6 of 6")
        #expect(strip.next == "Sweet-spot build next")
    }

    @Test func breakBetweenBlocks() throws {
        #expect(ArcFormat.strip(try blocks(), weekStart: "2027-01-04")?.next == "Break next")
        let gap = try #require(ArcFormat.strip(try blocks(), weekStart: "2027-01-11"))
        #expect(gap.lead.isEmpty)
        #expect(gap.detail == "VO2 touch starts Mon 18 Jan")
        #expect(gap.next == "6 wk")
    }

    @Test func beforeAndAfterTheArc() throws {
        let before = try #require(ArcFormat.strip(try blocks(), weekStart: "2026-10-05"))
        #expect(before.detail == "Winter arc starts Mon 19 Oct")
        #expect(before.next == "Base · 6 wk")
        #expect(before.tape.flatMap { $0 }.allSatisfy { $0.state == .future })
        #expect(ArcFormat.strip(try blocks(), weekStart: "2027-02-22")?.next == "Last week of the arc")
        #expect(ArcFormat.strip(try blocks(), weekStart: "2027-03-01") == nil)
    }

    @Test func noArcIsAQuietPlaceholder() {
        let strip = ArcFormat.strip([], weekStart: "2026-11-02")
        #expect(strip?.isPlaceholder == true)
        #expect(strip?.detail == "No winter arc yet · set one up on the Mac")
    }

    @Test func dueStallBlockOnThisWeek() throws {
        let line = try #require(ArcFormat.stall(try stall(), weekStart: "2026-11-02", today: "2026-11-05"))
        #expect(line == ArcFormat.StallLine(lift: "Upright row", detail: "3 weeks done · finish it next lift", filled: 3, total: 3))
    }

    @Test func stallBlockWeekByWeek() throws {
        let stall = try stall()
        #expect(ArcFormat.stall(stall, weekStart: "2026-10-12", today: "2026-11-05")?.detail == "rep scheme · week 1 of 3")
        #expect(ArcFormat.stall(stall, weekStart: "2026-10-19", today: "2026-11-05")?.filled == 2)
        #expect(ArcFormat.stall(stall, weekStart: "2026-10-05", today: "2026-11-05") == nil)
        #expect(ArcFormat.stall(stall, weekStart: "2026-11-09", today: "2026-11-05") == nil)
        // Mid-block, on this week: counted from today.
        let running = StallBlock(exerciseName: "Barbell Bench Press", label: "Rep scheme", text: nil, scope: "block",
                                 startedOn: "2026-10-26", endsOn: "2026-11-16", week: 2, weeks: 3, due: false)
        #expect(ArcFormat.stall(running, weekStart: "2026-11-02", today: "2026-11-05")
                == ArcFormat.StallLine(lift: "Bench", detail: "rep scheme · week 2 of 3", filled: 2, total: 3))
    }

    @Test func microDeloadIsNotABlock() {
        let deload = StallBlock(exerciseName: "Dumbbell Skullcrusher", label: "Micro-deload", text: nil, scope: "today",
                                startedOn: "2026-11-05", endsOn: "2026-11-05", week: 0, weeks: 0, due: false)
        #expect(ArcFormat.stall(deload, weekStart: "2026-11-02", today: "2026-11-05") == nil)
    }

    @Test func sheetRows() throws {
        let rows = ArcFormat.rows(try blocks(), weekStart: "2026-11-02")
        #expect(rows[0] == ArcFormat.BlockRow(title: "Base · week 3 of 6", mix: "3 Z2 rides · 3 h a week", lighter: "Lighter every 4th week",
                                              range: "Oct 19 – Nov 29", isCurrent: true, isPast: false))
        #expect(rows[1].mix == "2 Z2 + 2 sweet spot · 3.5 h a week")
        #expect(rows[2].lighter == nil)
        #expect(ArcFormat.span(try blocks()) == "Oct 19 – Feb 28 · 18 weeks")
        #expect(ArcFormat.stallDetail(try stall()) == "3 weeks done · keep it or go back at the next lift")
    }

    @Test func everyWeekIsEquallyWide() {
        let widths = ArcFormat.blockWidths([6, 6, 7], width: 361)
        let segment = (361 - 2 * 16 - 6 * 2) / 19.0
        #expect(abs(widths[0] - (segment * 6 + 10)) < 0.001)
        #expect(abs(widths.reduce(0, +) + 12 - 361) < 0.001)
    }

    @Test func demoStagesMatchTheBoard() {
        let today = "2026-11-05"
        let active = ArcFormat.demo("active", today: today)
        #expect(ArcFormat.strip(active.blocks, weekStart: "2026-11-02")?.detail == "week 3 of 6")
        #expect(active.stall?.due == true)
        #expect(ArcFormat.strip(ArcFormat.demo("lighter", today: today).blocks, weekStart: "2026-11-02")?.detail == "week 4 of 6 · lighter")
        #expect(ArcFormat.strip(ArcFormat.demo("last", today: today).blocks, weekStart: "2026-11-02")?.next == "Sweet-spot build next")
        #expect(ArcFormat.demo("none", today: today).blocks.isEmpty)
    }
}
