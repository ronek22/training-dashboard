import Foundation
import Testing
@testable import TrainLog

struct WinsTests {
    private let protein = PhoneToday.Protein(eatenG: 97, targetG: 130, hit: false)
    private let hit = PhoneToday.Protein(eatenG: 132, targetG: 130, hit: true)

    @Test func cleanDayNeedsTheRowAndTheWholeSession() {
        #expect(Wins.done(checkinDone: true, protein: hit, mainDone: true, rehabDone: true, sessionDone: true)
            == [.checkin, .protein, .main, .rehab, .clean])
        #expect(!Wins.done(checkinDone: true, protein: hit, mainDone: true, rehabDone: false, sessionDone: false).contains(.clean))
        #expect(!Wins.done(checkinDone: true, protein: protein, mainDone: true, rehabDone: true, sessionDone: true).contains(.clean))
        // Without a weigh-in there's no protein win to wait for.
        #expect(Wins.done(checkinDone: true, protein: nil, mainDone: false, rehabDone: false, sessionDone: true) == [.checkin, .clean])
    }

    @Test func pillSaysWhatsIn() {
        #expect(Wins.pillText(done: [], cleanThisWeek: 0) == nil)
        #expect(Wins.pillText(done: [.checkin, .main], cleanThisWeek: 0) == "Check-in")
        #expect(Wins.pillText(done: [.checkin, .protein], cleanThisWeek: 0) == "Check-in · Protein")
        #expect(Wins.pillText(done: [.checkin, .protein, .clean], cleanThisWeek: 2) == "All done · 2nd clean day this week")
        #expect(Wins.ordinal(1) == "1st")
        #expect(Wins.ordinal(3) == "3rd")
        #expect(Wins.ordinal(11) == "11th")
        #expect(Wins.proteinLabel(protein) == ("97", "/130 g protein"))
    }

    @Test func sessionStateFollowsTheCardsParts() {
        let json = #"{"title": "Workout", "status": "matched", "sport": "strength", "duration_min": 25}"#
        let done = try! APIClient.decoder.decode(PhoneToday.Session.self, from: Data(json.utf8))
        #expect(TodayFormat.sessionState(done, hasRehab: true, rehabLeft: 5) == (true, false, false))
        #expect(TodayFormat.sessionState(done, hasRehab: true, rehabLeft: 0) == (true, true, true))
        #expect(TodayFormat.sessionState(done, hasRehab: false, rehabLeft: 0) == (true, false, true))
        #expect(TodayFormat.sessionState(nil, hasRehab: false, rehabLeft: 0) == (false, false, true))
    }

    @Test func eachWinCelebratesOncePerDay() throws {
        let defaults = try #require(UserDefaults(suiteName: "wins-\(UUID())"))
        var ledger = WinLedger(defaults: defaults)
        #expect(ledger.claim([.checkin], on: "2026-11-03") == [.checkin])
        #expect(ledger.claim([.checkin], on: "2026-11-03").isEmpty)
        #expect(ledger.claim([.checkin, .protein], on: "2026-11-03") == [.protein])
        // A new day starts empty.
        #expect(ledger.claim([.checkin], on: "2026-11-04") == [.checkin])
    }

    @Test func countsCleanDaysInTheWeek() throws {
        let defaults = try #require(UserDefaults(suiteName: "wins-\(UUID())"))
        var ledger = WinLedger(defaults: defaults)
        _ = ledger.claim([.clean], on: "2026-11-01") // Sunday, last week
        _ = ledger.claim([.clean], on: "2026-11-02")
        _ = ledger.claim([.clean], on: "2026-11-04")
        #expect(ledger.cleanDays(weekOf: "2026-11-04") == 2)
        #expect(ledger.cleanDays(weekOf: "2026-11-01") == 1)
    }
}

struct MorningBriefTests {
    private func today(level: String = "red", checkin: Bool = false, sport: String = "strength", sick: Bool = false,
                       factors: String = #"[{"key": "hrv", "label": "HRV", "tone": "risk", "points": 2}, {"key": "resting_hr", "label": "Resting HR", "tone": "risk", "points": 2}, {"key": "sleep", "label": "Sleep", "tone": "steady", "points": 0}]"#) throws -> PhoneToday {
        let json = """
        {"date": "2026-11-03", "streak_days": 304,
         "readiness": {"level": "\(level)", "label": "x", "advice": null, "suggests_swap": false, "factors": \(factors)},
         "vitals": {"resting_hr": 77, "sleep_h": 7.6, "pain": null, "ranges": [{"key": "sleep", "value": 7.6, "date": "2026-11-02"}]},
         "checkin_done": \(checkin), "sick": \(sick ? #"{"label": "Cold", "day": 2}"# : "null"),
         "today": {"title": "Bodyweight upper + core", "session_type": "strength", "intent_label": "Upper-body strength",
                   "duration_min": 25, "status": "not_completed_yet", "sport": "\(sport)",
                   "purpose": "Keep the lift habit on the road.", "fallback": "Push-ups, pike push-ups and planks only."},
         "rehab": {"title": "Left knee", "done": 0, "total": 8, "duration_min": 27},
         "tomorrow": null, "week": [], "week_minutes": {"done": 0, "planned": 0, "by_sport": []}}
        """
        return try APIClient.decoder.decode(PhoneToday.self, from: Data(json.utf8))
    }

    @Test func redDayNamesTheOffSignalsAndTheShortVersion() throws {
        let message = MorningBrief.message(try today())
        #expect(message.title == "Upper-body strength · 25 min")
        #expect(message.body == "Slept 7.6 h, but HRV and resting HR are off, so keep it short. Short version: Push-ups, pike push-ups and planks only. Tap to check in.")
        #expect(message.link == "trainlog://checkin")
    }

    @Test func greenDayGivesThePurpose() throws {
        let message = MorningBrief.message(try today(level: "green", checkin: true, factors: "[]"))
        #expect(message.body == "Slept 7.6 h, good to go. Keep the lift habit on the road.")
        #expect(message.link == "trainlog://today")
    }

    @Test func amberCountsCautionToo() throws {
        let factors = #"[{"key": "sleep_debt", "label": "Sleep debt", "tone": "caution", "points": 1}]"#
        #expect(MorningBrief.why(try today(level: "amber", factors: factors)) == "Slept 7.6 h, but sleep debt is off, so go easy.")
    }

    @Test func titlesForRehabRestAndSick() throws {
        #expect(MorningBrief.title(try today(sport: "mobility")) == "Rehab · 27 min")
        #expect(MorningBrief.title(try today(sport: "rest")) == "Rest day")
        #expect(MorningBrief.title(try today(sick: true)) == "Sick mode")
        #expect(MorningBrief.why(try today(sick: true)) == "Slept 7.6 h. Rest and eat well; nothing to train today.")
    }

    @Test func sendsOnceInTheMorningWindow() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = .current
        let morning = try #require(calendar.date(from: DateComponents(year: 2026, month: 11, day: 3, hour: 7, minute: 4)))
        let night = try #require(calendar.date(from: DateComponents(year: 2026, month: 11, day: 3, hour: 2)))
        #expect(MorningBrief.isDue(now: morning, lastSent: "2026-11-02", calendar: calendar))
        #expect(!MorningBrief.isDue(now: morning, lastSent: "2026-11-03", calendar: calendar))
        #expect(!MorningBrief.isDue(now: night, lastSent: nil, calendar: calendar))
    }

    @Test func briefSentDropsTodaysCheckinNudge() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = .current
        let now = try #require(calendar.date(from: DateComponents(year: 2026, month: 11, day: 3, hour: 6)))
        var known = Reminders.Today(date: "2026-11-03")
        known.briefSent = true
        let nudges = Reminders.plan(.init(morning: 7 * 60 + 30), today: known, now: now, calendar: calendar)
        #expect(!nudges.contains { $0.kind == .checkin && $0.day == "2026-11-03" })
        #expect(nudges.contains { $0.kind == .checkin && $0.day == "2026-11-04" })
    }
}
