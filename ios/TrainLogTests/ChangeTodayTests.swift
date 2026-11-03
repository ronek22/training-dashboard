import Foundation
import Testing
@testable import TrainLog

struct ChangeTodayTests {
    /// Today on 3 Nov.
    private let lift = ChangeTodayFormat.Session(sport: .strength, minutes: 25, title: "Bodyweight upper + core (short, travel day)")

    @Test func redReadinessPreselectsEasier() {
        #expect(ChangeTodayFormat.initial(suggestsSwap: true, now: lift)! == (.rough, .easier))
        #expect(ChangeTodayFormat.initial(suggestsSwap: false, now: lift) == nil)
        let rest = ChangeTodayFormat.Session(sport: .rest, minutes: 0, title: "Rest")
        #expect(ChangeTodayFormat.initial(suggestsSwap: true, now: rest) == nil)
    }

    @Test func shortOptionsStayUnderToday() {
        #expect(ChangeTodayFormat.shortMinutes(lift) == [10, 15, 20])
        let long = ChangeTodayFormat.Session(sport: .ride, minutes: 70, title: "Sweet spot")
        #expect(ChangeTodayFormat.shortMinutes(long) == [20, 30, 40])
        let tiny = ChangeTodayFormat.Session(sport: .mobility, minutes: 10, title: "Rehab")
        #expect(ChangeTodayFormat.shortMinutes(tiny) == [10])
    }

    @Test func otherSportLeavesOutTodays() {
        let options = ChangeTodayFormat.options(.sport, now: lift)
        #expect(options == [.sport(.ride), .sport(.run), .sport(.walk), .sport(.mobility)])
        let ride = ChangeTodayFormat.Session(sport: .ride, minutes: 45, title: "Easy spin")
        #expect(!ChangeTodayFormat.options(.sport, now: ride).contains(.sport(.ride)))
        #expect(ChangeTodayFormat.options(.sport, now: ride).contains(.sport(.strength)))
    }

    @Test func ghostFollowsThePick() {
        #expect(ChangeTodayFormat.ghost(nil, now: lift) == nil)
        #expect(ChangeTodayFormat.ghost(.add(30), now: lift) == .init(sport: .strength, minutes: 55, label: "~55 min"))
        #expect(ChangeTodayFormat.ghost(.shorter, now: lift)?.minutes == 15)
        #expect(ChangeTodayFormat.ghost(.sport(.ride), now: lift) == .init(sport: .ride, minutes: 30, label: "Ride · ~30 min"))
        #expect(ChangeTodayFormat.ghost(.easier, now: lift)?.minutes == 25)
        #expect(ChangeTodayFormat.ghost(.rest, now: lift)?.sport == .rest)
    }

    @Test func feedbackIsTheSentenceThenTheNote() {
        let text = ChangeTodayFormat.feedback(.sport(.ride), note: "  Sunny out, easy on the knee ", now: lift)
        #expect(text == "I'd rather do a ride today instead of Bodyweight upper + core (short, travel day), about 30 min.\nSunny out, easy on the knee")
        #expect(ChangeTodayFormat.feedback(nil, note: "Something short", now: lift) == "Something short")
        #expect(ChangeTodayFormat.feedback(nil, note: "  ", now: lift).isEmpty)
        #expect(ChangeTodayFormat.sentence(.session(.walk, 30), now: .init(sport: .rest, minutes: 0, title: "Rest"))
                == "Today is a rest day, but I'd like to do a walk, about 30 min.")
    }

    @Test func planShortLeadsWhenThePlanHasOne() {
        #expect(ChangeTodayFormat.options(.short, now: lift, hasFallback: true) == [.planShort, .minutes(15), .minutes(20)])
        #expect(ChangeTodayFormat.options(.short, now: lift) == [.minutes(10), .minutes(15), .minutes(20)])
    }

    @Test func readinessLineNamesWhatsOff() {
        let factors = [
            PhoneToday.Factor(key: "hrv", label: "HRV", tone: "risk", points: 2),
            PhoneToday.Factor(key: "resting_hr", label: "Resting HR", tone: "steady", points: 0),
            PhoneToday.Factor(key: "sleep", label: "Sleep", tone: "caution", points: 1),
            PhoneToday.Factor(key: "sleep_debt", label: "Sleep debt", tone: "risk", points: 1),
        ]
        #expect(ChangeTodayFormat.readinessLine(factors) == "HRV, sleep and sleep debt are off.")
        #expect(ChangeTodayFormat.readinessLine(Array(factors.prefix(1))) == "HRV is off.")
        #expect(ChangeTodayFormat.readinessLine([]) == "Recovery is low today.")
    }

    @Test func scaleStretchesForLongSessions() {
        #expect(ChangeTodayFormat.scale(25, 55) == 90)
        #expect(ChangeTodayFormat.scale(90) == 120)
        #expect(ChangeTodayFormat.scale(25, 115) == 150)
    }

    @Test func trailIsShort() {
        #expect(ChangeTodayFormat.trail(lift) == "Bodyweight upper, 25 min")
        #expect(ChangeTodayFormat.trail(.init(sport: .rest, minutes: 0, title: "Rest")) == "rest day")
    }
}
