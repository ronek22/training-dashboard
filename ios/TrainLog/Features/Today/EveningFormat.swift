import Foundation

/// Pure rules for Today's evening mode (unit-tested). Times are minutes after midnight; a lights
/// out after midnight is carried past 1440 so it stays after "now".
enum EveningFormat {
    static let startHour = 20
    static let windDownMinutes = 45
    /// Sick mode brings lights out earlier.
    static let sickEarlierMinutes = 30
    /// Food left only when the gap is worth acting on (same thresholds as Food's gap card).
    static let foodKcalSlack = 300.0
    static let foodProteinSlack = 15.0
    /// Home for sunrise and sunset: Kraków. The app asks for no location.
    static let home = (latitude: 50.06, longitude: 19.94)

    /// 20:00 to midnight. After midnight Today is the next day and opens on the morning screen.
    static func isEvening(_ date: Date, calendar: Calendar = .current) -> Bool {
        calendar.component(.hour, from: date) >= startHour
    }

    static func minutes(_ date: Date, calendar: Calendar = .current) -> Int {
        let parts = calendar.dateComponents([.hour, .minute], from: date)
        return (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
    }

    /// Why lights out is when it is, when it isn't just the usual night.
    static func reason(debtH: Double, sick: Bool) -> String? {
        if sick { return "Sick mode: 30 min earlier than usual" }
        if debtH > 3 { return "30 min earlier to chip at \(Int(debtH.rounded())) h of sleep debt" }
        if debtH > 1 { return "15 min earlier for this week’s sleep debt" }
        return nil
    }

    /// Body's lights-out formula, 30 minutes earlier in sick mode; past midnight it's carried over
    /// 1440 so it stays after an evening "now".
    static func lightsOut(wakeMinutes: Int, needH: Double, debtH: Double, sick: Bool) -> Int {
        var value = BodyClockMath.lightsOut(wakeMinutes: wakeMinutes, needH: needH, debtH: debtH)
        if sick { value -= sickEarlierMinutes }
        value = (value % 1440 + 1440) % 1440
        // 23:30 stays 23:30; 00:15 becomes 24:15 so it lands after a 21:10 "now".
        return value < 12 * 60 ? value + 1440 : value
    }

    static func windDown(lightsOut: Int) -> Int { lightsOut - windDownMinutes }

    /// The session fits when it's over before wind-down starts.
    static func fits(now: Int, durationMin: Int, lightsOut: Int) -> Bool {
        now + durationMin <= windDown(lightsOut: lightsOut)
    }

    enum Day: Equatable {
        case done(Sport), open(Sport), rest, sick(day: Int?)
    }

    /// The one line on how today went: the session, then time outside, then a close on a good day.
    static func line(_ day: Day, outsideMin: Int?, clean: Bool) -> String {
        let outside: String? = outsideMin.flatMap { minutes in
            guard minutes > 0 else { return nil }
            return minutes >= 30 ? "\(minutes) minutes in daylight" : "only \(minutes) minutes outside"
        }
        switch day {
        case .done(let sport):
            let head = outside.map { "\(noun(sport)) done, and \($0)." } ?? "\(noun(sport)) done."
            return clean ? head + " Close it here." : head
        case .open(let sport):
            return outside.map { "\(noun(sport)) still open; \($0)." } ?? "\(noun(sport)) still open."
        case .rest:
            guard let outside else { return "Rest day kept." }
            return "Rest day kept, with \(outside)." + ((outsideMin ?? 0) >= 30 ? " That counts." : "")
        case .sick(let day):
            return (day.map { "Sick day \($0)." } ?? "Sick day.") + " Resting was the plan."
        }
    }

    static func noun(_ sport: Sport) -> String {
        switch sport {
        case .strength: "Lift"
        case .ride: "Ride"
        case .run: "Run"
        case .mobility: "Mobility"
        case .walk: "Walk"
        case .hike: "Hike"
        case .rest, .other: "Workout"
        }
    }

    enum Food: Equatable {
        case left(kcal: Int, proteinG: Int), done(eaten: Int, target: Int)
    }

    /// Nil without a kcal target. Protein counts only when it has a target.
    static func food(eatenKcal: Double, targetKcal: Double?, protein: PhoneToday.Protein?) -> Food? {
        guard let targetKcal, targetKcal > 0 else { return nil }
        let kcalLeft = max(0, targetKcal - eatenKcal)
        let proteinLeft = protein.map { $0.hit ? 0 : max(0, Double($0.targetG) - $0.eatenG) } ?? 0
        if kcalLeft > foodKcalSlack || proteinLeft > foodProteinSlack {
            return .left(kcal: Int(kcalLeft.rounded()), proteinG: Int(proteinLeft.rounded()))
        }
        return .done(eaten: Int(eatenKcal.rounded()), target: Int(targetKcal.rounded()))
    }

    /// Sunrise and sunset in local minutes after midnight (NOAA approximation, ±2 min).
    static func sun(on date: Date, latitude: Double = home.latitude, longitude: Double = home.longitude,
                    calendar: Calendar = .current) -> (rise: Int, set: Int)? {
        guard let dayOfYear = calendar.ordinality(of: .day, in: .year, for: date) else { return nil }
        let gamma = 2 * Double.pi / 365 * (Double(dayOfYear) - 1)
        let eqTime = 229.18 * (0.000075 + 0.001868 * cos(gamma) - 0.032077 * sin(gamma)
                               - 0.014615 * cos(2 * gamma) - 0.040849 * sin(2 * gamma))
        let decl = 0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma) - 0.006758 * cos(2 * gamma)
            + 0.000907 * sin(2 * gamma) - 0.002697 * cos(3 * gamma) + 0.00148 * sin(3 * gamma)
        let lat = latitude * .pi / 180
        let cosHA = cos(90.833 * .pi / 180) / (cos(lat) * cos(decl)) - tan(lat) * tan(decl)
        guard (-1...1).contains(cosHA) else { return nil }
        let ha = acos(cosHA) * 180 / .pi
        let offset = Double(calendar.timeZone.secondsFromGMT(for: date)) / 60
        let noon = 720 - 4 * longitude - eqTime + offset
        return (Int((noon - 4 * ha).rounded()), Int((noon + 4 * ha).rounded()))
    }

    static func clock(_ minutes: Int) -> String { BodyClockMath.clock(minutes: minutes) }
}
