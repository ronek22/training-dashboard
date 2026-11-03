import Foundation
import Testing
@testable import TrainLog

struct EveningTests {
    private var warsaw: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Warsaw")!
        return calendar
    }

    private func at(_ hour: Int, _ minute: Int, day: Int = 3, month: Int = 11) -> Date {
        warsaw.date(from: DateComponents(year: 2026, month: month, day: day, hour: hour, minute: minute))!
    }

    @Test func eveningRunsFromEightUntilMidnight() {
        #expect(!EveningFormat.isEvening(at(19, 59), calendar: warsaw))
        #expect(EveningFormat.isEvening(at(20, 0), calendar: warsaw))
        #expect(EveningFormat.isEvening(at(23, 59), calendar: warsaw))
        #expect(!EveningFormat.isEvening(at(0, 30), calendar: warsaw))
    }

    @Test func lightsOutMatchesBodyAndMovesEarlierWhenSick() {
        // Wake 07:30, need 7.14 h, 6 h debt: Body's 23:30.
        #expect(EveningFormat.lightsOut(wakeMinutes: 450, needH: 7.14, debtH: 6, sick: false) == 1410)
        #expect(EveningFormat.lightsOut(wakeMinutes: 450, needH: 7.14, debtH: 6, sick: true) == 1380)
        // Past midnight it stays after now.
        #expect(EveningFormat.lightsOut(wakeMinutes: 480, needH: 7, debtH: 0, sick: false) == 1440 + 45)
        #expect(EveningFormat.lightsOut(wakeMinutes: 450, needH: 7.5, debtH: 0, sick: false) == 1425)
    }

    @Test func tomorrowsSportComesFromItsSessionType() {
        #expect(Sport(sessionType: "strength") == .strength)
        #expect(Sport(sessionType: "WeightTraining") == .strength)
        #expect(Sport(sessionType: "Virtual Ride") == .ride)
        #expect(Sport(sessionType: "TrailRun") == .run)
        #expect(Sport(sessionType: "Rest") == .rest)
        #expect(Sport(sessionType: nil) == .other)
    }

    @Test func reasonExplainsAnEarlierNight() {
        #expect(EveningFormat.reason(debtH: 6, sick: false) == "30 min earlier to chip at 6 h of sleep debt")
        #expect(EveningFormat.reason(debtH: 2, sick: false) == "15 min earlier for this week’s sleep debt")
        #expect(EveningFormat.reason(debtH: 0.5, sick: false) == nil)
        #expect(EveningFormat.reason(debtH: 6, sick: true) == "Sick mode: 30 min earlier than usual")
    }

    @Test func sessionFitsOnlyBeforeWindDown() {
        #expect(EveningFormat.windDown(lightsOut: 1410) == 1365)
        #expect(EveningFormat.fits(now: 1270, durationMin: 25, lightsOut: 1410))
        #expect(EveningFormat.fits(now: 1320, durationMin: 45, lightsOut: 1410))
        #expect(!EveningFormat.fits(now: 1321, durationMin: 45, lightsOut: 1410))
        #expect(!EveningFormat.fits(now: 1375, durationMin: 25, lightsOut: 1410))
    }

    @Test func lineSaysTheSessionThenTheDaylight() {
        #expect(EveningFormat.line(.done(.strength), outsideMin: 46, clean: true) == "Lift done, and 46 minutes in daylight. Close it here.")
        #expect(EveningFormat.line(.done(.ride), outsideMin: 12, clean: false) == "Ride done, and only 12 minutes outside.")
        #expect(EveningFormat.line(.done(.run), outsideMin: nil, clean: false) == "Run done.")
        #expect(EveningFormat.line(.open(.strength), outsideMin: 46, clean: false) == "Lift still open; 46 minutes in daylight.")
        #expect(EveningFormat.line(.open(.strength), outsideMin: 0, clean: false) == "Lift still open.")
        #expect(EveningFormat.line(.rest, outsideMin: 46, clean: true) == "Rest day kept, with 46 minutes in daylight. That counts.")
        #expect(EveningFormat.line(.rest, outsideMin: nil, clean: false) == "Rest day kept.")
        #expect(EveningFormat.line(.sick(day: 2), outsideMin: 40, clean: false) == "Sick day 2. Resting was the plan.")
    }

    @Test func foodLeftOnlyWhenTheGapIsWorthActingOn() {
        let short = PhoneToday.Protein(eatenG: 97, targetG: 130, hit: false)
        let hit = PhoneToday.Protein(eatenG: 125, targetG: 130, hit: true)
        #expect(EveningFormat.food(eatenKcal: 1211, targetKcal: 2451, protein: short) == .left(kcal: 1240, proteinG: 33))
        #expect(EveningFormat.food(eatenKcal: 2300, targetKcal: 2451, protein: short) == .left(kcal: 151, proteinG: 33))
        #expect(EveningFormat.food(eatenKcal: 2410, targetKcal: 2451, protein: hit) == .done(eaten: 2410, target: 2451))
        #expect(EveningFormat.food(eatenKcal: 2600, targetKcal: 2451, protein: nil) == .done(eaten: 2600, target: 2451))
        #expect(EveningFormat.food(eatenKcal: 900, targetKcal: nil, protein: short) == nil)
    }

    @Test func sunInKrakowEarlyNovember() throws {
        let sun = try #require(EveningFormat.sun(on: at(12, 0), calendar: warsaw))
        // 3 Nov: sunrise ~06:32, sunset ~16:17 (CET).
        #expect(abs(sun.rise - (6 * 60 + 32)) <= 4)
        #expect(abs(sun.set - (16 * 60 + 17)) <= 4)
        // 21 Jun: sunset ~20:57 (CEST).
        let june = try #require(EveningFormat.sun(on: at(12, 0, day: 21, month: 6), calendar: warsaw))
        #expect(abs(june.set - (20 * 60 + 57)) <= 5)
    }
}
