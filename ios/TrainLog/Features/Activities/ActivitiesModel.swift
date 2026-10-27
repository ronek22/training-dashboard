import Foundation
import Observation
import UIKit

/// The Activities tab: recent sessions grouped by week, a sport filter, and swipe-to-rate.
@MainActor
@Observable
final class ActivitiesModel {
    private(set) var activities: [ActivitySummary] = []
    private(set) var loaded = false
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    var filter: Sport?

    private let client: () -> APIClient
    private let queue: WriteQueue

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue()) {
        self.client = client
        self.queue = queue
    }

    /// Sports present in the list, in a fixed order, for the filter chips.
    var sports: [Sport] {
        let present = Set(activities.map { ActivityFormat.sport($0) })
        return ActivityFormat.chipOrder.filter(present.contains)
    }

    var weeks: [ActivityWeek] {
        ActivityFormat.weeks(activities.filter { filter == nil || ActivityFormat.sport($0) == filter })
    }

    func load() async {
        let api = client()
        await queue.flush(with: api)
        do {
            let result = try await api.get("/activities?limit=60", as: [ActivitySummary].self)
            activities = result.value
            syncedAt = result.syncedAt
            offline = result.fromCache
            error = nil
        } catch {
            offline = !activities.isEmpty
            self.error = error.localizedDescription
        }
        loaded = true
    }

    /// Pull to refresh: ask the server to pull new Strava activities first. A failed sync (no
    /// Strava token, Strava down) still reloads what the server has.
    func sync() async {
        let body = try? APIClient.encoder.encode(["fetch_streams": false])
        _ = try? await client().send("POST", "/integrations/strava/import", body: body, timeout: 30)
        await load()
    }

    func rate(_ activity: ActivitySummary, verdict: String) async {
        update(activity.id) { $0.sessionTags = SessionTags(verdict: verdict) }
        let body = try? APIClient.encoder.encode(SessionTags(verdict: verdict))
        await write("PUT", "/activities/\(activity.id)/tags", body: body)
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    func saveFeedback(_ input: ActivityFeedbackInput, for id: String) async {
        update(id) {
            $0.feedback = ActivityFeedback(rpe: input.rpe, energy: input.energy, muscleSoreness: input.muscleSoreness,
                                           painLevel: input.painLevel, note: input.note)
        }
        let body = try? APIClient.encoder.encode(input)
        await write("POST", "/activities/\(id)/feedback", body: body)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    /// Sends a write, or queues it when the server is unreachable; the row already shows it.
    private func write(_ method: String, _ path: String, body: Data?) async {
        do {
            try await client().send(method, path, body: body)
        } catch APIError.unreachable {
            queue.append(.init(method: method, path: path, body: body))
            offline = true
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func update(_ id: String, _ change: (inout ActivitySummary) -> Void) {
        guard let index = activities.firstIndex(where: { $0.id == id }) else { return }
        change(&activities[index])
    }
}

struct ActivityWeek: Identifiable, Equatable {
    let start: Date
    let title: String
    let activities: [ActivitySummary]

    var id: Date { start }
}

/// Labels and numbers for activity rows and the detail page.
enum ActivityFormat {
    static let chipOrder: [Sport] = [.ride, .strength, .hike, .run, .walk, .mobility, .other]

    /// Dot decimals whatever the phone's region, like the rest of the app.
    static let oneDecimal = FloatingPointFormatStyle<Double>.number.precision(.fractionLength(1)).locale(Locale(identifier: "en_US_POSIX"))

    /// The colour family. Strava "Workout" covers both guided rehab and lifting, so the intent decides.
    static func sport(_ activity: ActivitySummary) -> Sport {
        switch activity.type {
        case "Ride", "VirtualRide", "EBikeRide", "GravelRide", "MountainBikeRide": return .ride
        case "Run", "TrailRun", "VirtualRun": return .run
        case "WeightTraining": return .strength
        case "Hike": return .hike
        case "Walk": return .walk
        case "PhysicalTherapy", "Yoga", "Pilates": return .mobility
        default: break
        }
        if activity.recordedStrengthSession != nil || activity.workoutIntent?.hasPrefix("strength") == true {
            return .strength
        }
        if activity.guidedSession != nil || activity.workoutIntent == "mobility" {
            return .mobility
        }
        return .other
    }

    static func typeLabel(_ activity: ActivitySummary) -> String {
        if let guided = activity.guidedSession {
            return guided.contextLabel.map { "Guided · \($0)" } ?? "Guided"
        }
        switch activity.type {
        case "VirtualRide": return "Virtual ride"
        case "WeightTraining": return "Strength"
        case "PhysicalTherapy": return "Physio"
        case "TrailRun": return "Trail run"
        default: return activity.type.replacingOccurrences(of: "([a-z])([A-Z])", with: "$1 $2", options: .regularExpression).capitalized
        }
    }

    /// What matters about the session, after the date: pain, then the verdict, then the intent or effort.
    static func subtitle(_ activity: ActivitySummary) -> (plain: String, highlight: Highlight?) {
        let day = shortDay(activity.date)
        if let pain = activity.feedback?.painLevel, pain >= 3 {
            return (day, .init(text: "Pain \(pain)/10", tone: .pain))
        }
        if activity.sessionTags?.verdict == "loved" {
            return ("\(day) · \(typeLabel(activity))", .init(text: "Loved it", tone: .win))
        }
        if activity.sessionTags?.verdict == "hated" {
            return ("\(day) · \(typeLabel(activity))", .init(text: "Hated it", tone: .muted))
        }
        var parts = [day, typeLabel(activity)]
        if let intent = activity.workoutIntentLabel, activity.guidedSession == nil, intent != typeLabel(activity) {
            parts.append(intent)
        } else if let rpe = activity.feedback?.rpe {
            parts.append("RPE \(rpe)")
        }
        return (parts.joined(separator: " · "), nil)
    }

    struct Highlight: Equatable {
        enum Tone { case pain, win, muted }
        let text: String
        let tone: Tone
    }

    /// The one number on the right: distance when there is one, otherwise time.
    static func headline(_ activity: ActivitySummary) -> (value: String, unit: String) {
        if let km = activity.distanceKm, km >= 0.5 {
            return (km.formatted(ActivityFormat.oneDecimal), " km")
        }
        return duration(activity.durationMin ?? 0)
    }

    /// The small line under the number.
    static func detail(_ activity: ActivitySummary) -> String {
        var parts: [String] = []
        let hasDistance = (activity.distanceKm ?? 0) >= 0.5
        if hasDistance, let minutes = activity.durationMin {
            parts.append(compactDuration(minutes))
        }
        if let watts = activity.avgWatts, watts > 0, sport(activity) == .ride {
            parts.append("\(Int(watts.rounded())) W")
        } else if hasDistance, let climb = activity.elevationM, climb >= 50 {
            parts.append("\(Int(climb.rounded())) m↑")
        } else if let hr = activity.avgHr, hr > 0 {
            parts.append("\(Int(hr.rounded())) bpm")
        }
        return parts.joined(separator: " · ")
    }

    /// "34 min" or "1h 39" + "m", split so the number can be large and the unit small.
    static func duration(_ minutes: Double) -> (value: String, unit: String) {
        let total = Int(minutes.rounded())
        if total < 60 { return ("\(total)", " min") }
        return ("\(total / 60)h \(String(format: "%02d", total % 60))", "m")
    }

    /// "30m", "2h 36".
    static func compactDuration(_ minutes: Double) -> String {
        let total = Int(minutes.rounded())
        return total < 60 ? "\(total)m" : "\(total / 60)h \(String(format: "%02d", total % 60))"
    }

    /// Clock-style time for the detail tile: "30:24", "2:36:24".
    static func clock(_ minutes: Double) -> String {
        let seconds = Int((minutes * 60).rounded())
        let (h, m, s) = (seconds / 3600, seconds % 3600 / 60, seconds % 60)
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%d:%02d", m, s)
    }

    /// Groups newest first by Monday-start week: "This week · Oct 26 – Nov 1", "Last week · …".
    static func weeks(_ activities: [ActivitySummary], today: Date = .now) -> [ActivityWeek] {
        let calendar = mondayCalendar
        let sorted = activities.sorted { ($0.date, $0.createdAt ?? "") > ($1.date, $1.createdAt ?? "") }
        let thisWeek = calendar.dateInterval(of: .weekOfYear, for: today)?.start
        var groups: [(start: Date, items: [ActivitySummary])] = []
        for activity in sorted {
            guard let day = FoodFormat.parse(activity.date),
                  let start = calendar.dateInterval(of: .weekOfYear, for: day)?.start else { continue }
            if groups.last?.start == start {
                groups[groups.count - 1].items.append(activity)
            } else {
                groups.append((start, [activity]))
            }
        }
        return groups.map { group in
            let range = weekRange(group.start)
            let title: String
            if group.start == thisWeek {
                title = "This week · \(range)"
            } else if let thisWeek, calendar.date(byAdding: .weekOfYear, value: -1, to: thisWeek) == group.start {
                title = "Last week · \(range)"
            } else {
                title = range
            }
            return ActivityWeek(start: group.start, title: title, activities: group.items)
        }
    }

    /// "Oct 26 – Nov 1", or "Oct 19 – 25" inside one month.
    static func weekRange(_ start: Date) -> String {
        let end = mondayCalendar.date(byAdding: .day, value: 6, to: start) ?? start
        let month = Date.FormatStyle().month(.abbreviated).locale(english)
        let sameMonth = mondayCalendar.component(.month, from: start) == mondayCalendar.component(.month, from: end)
        let day = { (date: Date) in "\(mondayCalendar.component(.day, from: date))" }
        let endText = sameMonth ? day(end) : "\(end.formatted(month)) \(day(end))"
        return "\(start.formatted(month)) \(day(start)) – \(endText)"
    }

    /// "Tue 27".
    static func shortDay(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return iso }
        return "\(date.formatted(.dateTime.weekday(.abbreviated).locale(english))) \(mondayCalendar.component(.day, from: date))"
    }

    /// "Tue 27 Oct".
    static func longDay(_ iso: String) -> String {
        guard let date = FoodFormat.parse(iso) else { return iso }
        return "\(shortDay(iso)) \(date.formatted(.dateTime.month(.abbreviated).locale(english)))"
    }

    private static let english = Locale(identifier: "en_GB")

    private static let mondayCalendar: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.firstWeekday = 2
        calendar.minimumDaysInFirstWeek = 4
        return calendar
    }()
}
