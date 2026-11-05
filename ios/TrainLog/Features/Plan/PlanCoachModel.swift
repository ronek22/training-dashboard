import Foundation
import Observation
import SwiftUI
import UIKit

/// What the coach is asked to do. Codable so a job still running can be picked up after a relaunch.
enum PlanCoachTask: Codable, Equatable, Sendable {
    /// Write a whole week.
    case plan(week: String)
    /// Change the rest of a week from today on.
    case refine(week: String)
    /// Change one day and nothing else.
    case day(week: String, date: String)

    var week: String {
        switch self {
        case .plan(let week), .refine(let week), .day(let week, _): week
        }
    }

    var key: String {
        switch self {
        case .plan(let week): "plan.\(week)"
        case .refine(let week): "refine.\(week)"
        case .day(_, let date): "day.\(date)"
        }
    }
}

/// What the finished job changed, for the result sheet.
struct PlanCoachResult: Equatable {
    let task: PlanCoachTask
    let days: [PlanWeekStrip.Day]
    let changes: [PlanCoachFormat.Change]
    let totalMinutes: Int
    let mix: [PlanCoachFormat.MixPart]
    let summary: String?
    let seconds: Int
    /// The saved week day by day, for a planned week.
    var sessions: [PlanCoachFormat.Session] = []
}

/// Planning and refining weeks with the coach helper on the Mac, through the backend relay
/// (`/plans/weekly/coach`). The job runs on the Mac: closing the sheet only stops the polling,
/// and the Plan tab keeps following it.
@MainActor
@Observable
final class PlanCoachModel {
    enum Helper: Equatable {
        case unknown, up, down(String), away
    }

    enum Phase: Equatable {
        case compose
        case working(stage: String)
        case done(PlanCoachResult)
        case failed(String)
    }

    private(set) var task: PlanCoachTask?
    private(set) var phase: Phase = .compose
    private(set) var helper: Helper = .unknown
    private(set) var startedAt: Date?
    /// What was sent, shown while the coach works and given back after a failure.
    private(set) var sent = ""
    var note = "" {
        didSet { if case .compose = phase, let task { saveDraft(note, for: task) } }
    }

    private let plans: PlanModel
    private let client: () -> APIClient
    private let defaults = UserDefaults.standard
    private var before: [PlanDay] = []
    private var follower: Task<Void, Never>?
    var pollInterval: Duration = .seconds(3)

    private static let pendingKey = "planCoach.pending"
    private static let deadline: TimeInterval = 16 * 60

    init(plans: PlanModel, client: @escaping () -> APIClient = { .current }) {
        self.plans = plans
        self.client = client
    }

    var isRunning: Bool {
        if case .working = phase { return true }
        return false
    }

    func isRunning(for week: String) -> Bool { isRunning && task?.week == week }

    var canSend: Bool {
        guard let task, helper != .away, !isDown else { return false }
        if case .plan = task { return true }
        return !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var isDown: Bool {
        if case .down = helper { return true }
        return false
    }

    /// Opens the sheet for a task. A running job keeps the sheet on its progress instead.
    func open(_ task: PlanCoachTask) {
        if isRunning { return }
        self.task = task
        phase = .compose
        note = defaults.string(forKey: Self.draftKey(task)) ?? ""
        Task { await checkHelper() }
    }

    func checkHelper() async {
        #if DEBUG
        if Self.demoStage != nil { return }
        #endif
        do {
            let status = try await client().getLive("/plans/weekly/coach/status", as: CoachPlanStatus.self)
            helper = status.available ? .up : .down(status.detail ?? "The coach helper on the Mac isn't answering.")
        } catch APIError.unreachable {
            helper = .away
        } catch {
            helper = .down(Self.message(for: error))
        }
    }

    func send() {
        guard let task, canSend else { return }
        let text = note.trimmingCharacters(in: .whitespacesAndNewlines)
        sent = text
        before = plans.weeks.first { $0.weekStart == task.week }?.days ?? []
        startedAt = .now
        phase = .working(stage: "Sending to the coach…")
        follower = Task { await run(task, text) }
    }

    /// After a failure: back to the form with the note as it was.
    func retry() {
        guard task != nil else { return }
        phase = .compose
        note = sent
        Task { await checkHelper() }
    }

    /// Picks up a job that was still running when the app last closed.
    func resume() {
        guard !isRunning, let data = defaults.data(forKey: Self.pendingKey),
              let pending = try? JSONDecoder().decode(Pending.self, from: data) else { return }
        guard Date.now.timeIntervalSince(pending.startedAt) < Self.deadline else {
            defaults.removeObject(forKey: Self.pendingKey)
            return
        }
        task = pending.task
        sent = pending.note
        startedAt = pending.startedAt
        before = plans.weeks.first { $0.weekStart == pending.task.week }?.days ?? []
        phase = .working(stage: "The coach is working")
        follower = Task { await follow(pending.jobId, pending.task) }
    }

    private func run(_ task: PlanCoachTask, _ text: String) async {
        let api = client()
        do {
            let job: CoachPlanJob
            switch task {
            case .plan(let week):
                let body = try APIClient.encoder.encode(CoachPlanRequest(weekStart: week, planningBrief: text))
                job = try await api.send("POST", "/plans/weekly/coach", body: body, as: CoachPlanJob.self, timeout: 45)
            case .refine(let week):
                let body = try APIClient.encoder.encode(CoachRevisionRequest(weekStart: week, feedback: text, targetDate: nil))
                job = try await api.send("POST", "/plans/weekly/coach/revise", body: body, as: CoachPlanJob.self, timeout: 45)
            case .day(let week, let date):
                let body = try APIClient.encoder.encode(CoachRevisionRequest(weekStart: week, feedback: text, targetDate: date))
                job = try await api.send("POST", "/plans/weekly/coach/revise", body: body, as: CoachPlanJob.self, timeout: 45)
            }
            let pending = Pending(jobId: job.jobId, task: task, note: text, startedAt: startedAt ?? .now)
            defaults.set(try? JSONEncoder().encode(pending), forKey: Self.pendingKey)
            defaults.removeObject(forKey: Self.draftKey(task))
            await follow(job.jobId, task)
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    /// Polls until the job finishes. A dropped connection only pauses it: the job lives on the Mac.
    private func follow(_ jobId: String, _ task: PlanCoachTask) async {
        let api = client()
        while !Task.isCancelled {
            if let startedAt, Date.now.timeIntervalSince(startedAt) > Self.deadline {
                defaults.removeObject(forKey: Self.pendingKey)
                phase = .failed("The coach took longer than 15 minutes. Check the week, then try again.")
                return
            }
            do {
                let job = try await api.getLive("/plans/weekly/coach/\(jobId)", as: CoachPlanJob.self)
                switch job.status {
                case "succeeded":
                    defaults.removeObject(forKey: Self.pendingKey)
                    await finish(task, summary: job.summary)
                    return
                case "failed":
                    defaults.removeObject(forKey: Self.pendingKey)
                    phase = .failed(job.message ?? "The coach couldn't save the plan.")
                    return
                default:
                    phase = .working(stage: PlanCoachFormat.stage(job.message))
                }
            } catch APIError.status(404) {
                // The helper restarted and forgot the job.
                defaults.removeObject(forKey: Self.pendingKey)
                phase = .failed("The coach on the Mac restarted before it finished. Check the week, then try again.")
                return
            } catch is CancellationError {
                return
            } catch {
                phase = .working(stage: "Can't reach the server · still trying")
            }
            try? await Task.sleep(for: pollInterval)
        }
    }

    private func finish(_ task: PlanCoachTask, summary: String?) async {
        await plans.load()
        plans.select(task.week)
        let after = plans.weeks.first { $0.weekStart == task.week }
        phase = .done(PlanCoachFormat.result(task, before: before, after: after, today: plans.today, summary: summary,
                                             seconds: Int(Date.now.timeIntervalSince(startedAt ?? .now))))
        Haptics.success()
    }

    private func saveDraft(_ text: String, for task: PlanCoachTask) {
        #if DEBUG
        if Self.demoStage != nil { return }
        #endif
        defaults.set(text, forKey: Self.draftKey(task))
    }

    private static func draftKey(_ task: PlanCoachTask) -> String { "planCoach.draft.\(task.key)" }

    nonisolated static func message(for error: Error) -> String {
        switch error {
        case APIError.status(409): "The coach is busy with another job. Try again in a minute."
        case APIError.status(503): "The coach helper on the Mac isn't running. Restart TrainLog on the Mac, then try again."
        case APIError.unreachable: "Can't reach the server. Planning runs on the Mac, so try again on home Wi-Fi."
        default: error.localizedDescription
        }
    }

    private struct Pending: Codable {
        let jobId: String
        let task: PlanCoachTask
        let note: String
        let startedAt: Date
    }

    #if DEBUG
    /// `-planCoachDemo compose|refine|day|working|done|changed|offline|away|failed` (simulator screenshots, no server writes).
    static var demoStage: String? { UserDefaults.standard.string(forKey: "planCoachDemo") }

    /// Change today's screenshots (`-changeTodayDemo`): the job state without the server.
    func demoDay(_ task: PlanCoachTask, phase: Phase, helper: Helper, sent: String = "") {
        self.task = task
        self.phase = phase
        self.helper = helper
        self.sent = sent
        startedAt = .now.addingTimeInterval(-48)
    }

    func startDemo(week: WeeklyPlan?, unplanned: String?) {
        guard let stage = Self.demoStage else { return }
        let next = unplanned ?? "2026-11-09"
        helper = .up
        startedAt = .now.addingTimeInterval(-108)
        switch stage {
        case "refine", "changed":
            task = .refine(week: week?.weekStart ?? next)
            note = "Fri: I'm away until late, move the lift"
        case "day":
            let date = week?.days.first { $0.date > plans.today }?.date ?? next
            task = .day(week: week?.weekStart ?? next, date: date)
            note = "Away until 20:00, something short at home"
        default:
            task = .plan(week: next)
            note = "Thu: deadline, keep it short.\nSat: long ride if the knee is calm"
        }
        sent = note
        switch stage {
        case "working": phase = .working(stage: "Reviewing your training context")
        case "offline": helper = .down("The coach helper on the Mac isn't answering. Restart TrainLog on the Mac, then try again.")
        case "away": helper = .away
        case "failed": phase = .failed("Planning timed out after 15 minutes.")
        case "done": phase = .done(PlanCoachFormat.demoPlanned(next))
        case "changed":
            if let week { phase = .done(PlanCoachFormat.demoChanged(week, today: plans.today)) }
        default: break
        }
    }
    #endif
}

/// Pure rules and labels for planning with the coach (unit-tested).
enum PlanCoachFormat {
    struct Change: Equatable {
        let date: String
        let was: String?
        let now: String?
    }

    /// One day of the planned week: "Workout B · Back + Arms", "Easy · 55 min".
    struct Session: Equatable {
        let date: String
        let sport: Sport
        let title: String
        let meta: String
    }

    struct MixPart: Equatable {
        let sport: Sport
        let label: String
    }

    /// The week to offer planning for: next week once this one is saved, this week when nothing
    /// covers it yet, nil when next week is already saved.
    static func unplannedStart(_ starts: [String], today: String) -> String? {
        let current = PlanFormat.weekStart(of: today)
        let next = PlanFormat.addingDays(7, to: current)
        guard let last = starts.max() else { return current }
        if last >= next { return nil }
        return last >= current ? next : current
    }

    /// Days the coach may still rewrite: later this week, and today unless it's already done.
    static func editableDates(_ week: WeeklyPlan, today: String) -> [String] {
        PlanFormat.slots(week).compactMap { slot in
            if slot.date > today { return slot.date }
            if slot.date == today, ![.done, .replaced].contains(PlanFormat.status(slot.day, today: today)) { return slot.date }
            return nil
        }
    }

    /// "Wed – Sun", "Sun".
    static func range(_ dates: [String]) -> String {
        guard let first = dates.first, let last = dates.last else { return "" }
        return first == last ? weekday(first) : "\(weekday(first)) – \(weekday(last))"
    }

    /// "Thu".
    static func weekday(_ iso: String) -> String {
        String(ActivityFormat.shortDay(iso).prefix(3))
    }

    /// "46".
    static func weekNumber(_ weekStart: String) -> Int {
        FoodFormat.parse(weekStart).map { ActivityFormat.mondayCalendar.component(.weekOfYear, from: $0) } ?? 0
    }

    /// Tapping a day in the strip starts a "Thu: " line; tapping it again removes the line while it's still empty.
    static func toggleDay(_ note: String, date: String) -> String {
        let label = "\(weekday(date)):"
        var lines = note.isEmpty ? [] : note.components(separatedBy: "\n")
        if let empty = lines.firstIndex(where: { $0.trimmingCharacters(in: .whitespaces) == label }) {
            lines.remove(at: empty)
            return lines.joined(separator: "\n")
        }
        if lines.contains(where: { $0.hasPrefix(label) }) { return note }
        if let last = lines.last, last.trimmingCharacters(in: .whitespaces).isEmpty { lines.removeLast() }
        lines.append("\(label) ")
        return lines.joined(separator: "\n")
    }

    /// Days the note already talks about, highlighted in the strip.
    static func mentioned(_ note: String, in dates: [String]) -> Set<String> {
        let lines = note.components(separatedBy: "\n")
        return Set(dates.filter { date in lines.contains { $0.hasPrefix("\(weekday(date)):") } })
    }

    /// Adds a suggestion on its own line.
    static func adding(_ suggestion: String, to note: String) -> String {
        if note.contains(suggestion) { return note }
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? suggestion : "\(trimmed)\n\(suggestion)"
    }

    static let planSuggestions = ["Prioritize recovery", "Keep Friday free", "Long ride on Saturday", "Weekdays ≤ 60 min"]
    static let refineSuggestions = ["Reduce the load", "Add a recovery day", "Move the hard session later", "Lighter weekend"]
    static let daySuggestions = ["Make it shorter", "Easier", "No equipment"]

    /// The helper's stage line without its "The coach is" lead: "Reviewing your training context".
    static func stage(_ message: String?) -> String {
        guard var text = message?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { return "The coach is working" }
        if text.hasSuffix(" is queued.") { return "Queued on the Mac" }
        for lead in ["The coach is ", "Coach is "] where text.hasPrefix(lead) {
            text = String(text.dropFirst(lead.count))
        }
        if text.hasSuffix(".") { text.removeLast() }
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    /// "Workout B · Back + Arms · 50 min".
    static func describe(_ day: PlanDay?) -> String? {
        guard let day, PlanFormat.sport(day) != .rest else { return nil }
        return [PlanFormat.rowTitle(day.title), day.targetDurationMin.map { "\($0) min" }].compactMap { $0 }.joined(separator: " · ")
    }

    /// Days whose session changed between the two versions of the week, in date order.
    static func changes(before: [PlanDay], after: [PlanDay]) -> [Change] {
        let old = Dictionary(before.map { ($0.date, $0) }, uniquingKeysWith: { first, _ in first })
        let new = Dictionary(after.map { ($0.date, $0) }, uniquingKeysWith: { first, _ in first })
        return Set(old.keys).union(new.keys).sorted().compactMap { date in
            let was = describe(old[date])
            let now = describe(new[date])
            let same = was == now && old[date]?.sessionType == new[date]?.sessionType
            return same ? nil : Change(date: date, was: was, now: now)
        }
    }

    /// "3 lifts", "2 rides", "rehab": the week's mix for the legend, biggest first.
    static func mix(_ days: [PlanDay]) -> [MixPart] {
        var counts: [Sport: Int] = [:]
        for day in days where PlanFormat.sport(day) != .rest { counts[PlanFormat.sport(day), default: 0] += 1 }
        let order: [Sport] = [.strength, .ride, .run, .mobility, .walk, .hike, .other]
        return order.compactMap { sport in
            guard let n = counts[sport] else { return nil }
            let label = switch sport {
            case .strength: n == 1 ? "1 lift" : "\(n) lifts"
            case .ride: n == 1 ? "1 ride" : "\(n) rides"
            case .run: n == 1 ? "1 run" : "\(n) runs"
            case .mobility: n == 1 ? "rehab" : "\(n) × rehab"
            default: "\(n) \(sport.label.lowercased())"
            }
            return MixPart(sport: sport, label: label)
        }
    }

    static func totalMinutes(_ days: [PlanDay]) -> Int {
        days.filter { PlanFormat.sport($0) != .rest }.reduce(0) { $0 + ($1.targetDurationMin ?? 0) }
    }

    /// "5 lifts · 2 rides · 5h": the line under the empty week, from the week before it.
    static func weekLine(_ week: WeeklyPlan) -> String {
        let parts = mix(week.days).map(\.label) + [ActivityFormat.compactDuration(Double(totalMinutes(week.days)))]
        return parts.joined(separator: " · ")
    }

    /// The strip for a saved week; `changed` dates get the volt outline.
    static func strip(_ week: WeeklyPlan, today: String, changed: Set<String> = [], selected: Set<String> = [], editable: Set<String>? = nil) -> [PlanWeekStrip.Day] {
        PlanFormat.slots(week).map { slot in
            let sport = slot.day.map(PlanFormat.sport)
            let style: PlanWeekStrip.Style
            if changed.contains(slot.date) { style = .changed }
            else if selected.contains(slot.date) { style = .selected }
            else if let editable, !editable.contains(slot.date) { style = .past }
            else if slot.date == today { style = .today }
            else { style = .normal }
            return PlanWeekStrip.Day(date: slot.date, color: sport == .rest ? nil : sport?.color,
                                 minutes: sport == .rest ? 0 : slot.day?.targetDurationMin ?? 0, style: style)
        }
    }

    /// Seven dashed slots for a week that isn't saved yet.
    static func ghost(_ weekStart: String, selected: Set<String> = []) -> [PlanWeekStrip.Day] {
        (0..<7).map { offset in
            let date = PlanFormat.addingDays(offset, to: weekStart)
            return PlanWeekStrip.Day(date: date, color: nil, minutes: 0, style: selected.contains(date) ? .selectedGhost : .ghost)
        }
    }

    static func result(_ task: PlanCoachTask, before: [PlanDay], after: WeeklyPlan?, today: String, summary: String?, seconds: Int) -> PlanCoachResult {
        let days = after?.days ?? []
        let changes = changes(before: before, after: days)
        var strip: [PlanWeekStrip.Day] = []
        if let after {
            if case .plan = task {
                strip = Self.strip(after, today: "")
            } else {
                strip = Self.strip(after, today: today, changed: Set(changes.map(\.date)), editable: Set(editableDates(after, today: today)).union(changes.map(\.date)))
            }
        }
        let isPlan = if case .plan = task { true } else { false }
        return PlanCoachResult(task: task, days: strip, changes: changes, totalMinutes: totalMinutes(days), mix: mix(days),
                               summary: note(summary), seconds: seconds, sessions: isPlan ? sessions(days) : [])
    }

    static func sessions(_ days: [PlanDay]) -> [Session] {
        days.sorted { $0.date < $1.date }.map { day in
            let sport = PlanFormat.sport(day)
            return sport == .rest
                ? Session(date: day.date, sport: .rest, title: "Rest", meta: "")
                : Session(date: day.date, sport: sport, title: PlanFormat.rowTitle(day.title), meta: PlanFormat.plannedMeta(day))
        }
    }

    /// The coach's reply as plain prose for the phone: markdown tables, headings and list markers go
    /// (the day list shows the week), code and emphasis marks are stripped, and sentences about its own
    /// tools (`get_weekly_plans`) are dropped.
    static func note(_ raw: String?) -> String? {
        guard let raw else { return nil }
        let lines = raw.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.hasPrefix("|") && !$0.hasPrefix("#") }
            .map { $0.replacingOccurrences(of: #"^([-*•]|\d+\.)\s+"#, with: "", options: .regularExpression) }
        let paragraphs = lines.split(separator: "", omittingEmptySubsequences: true).map { $0.joined(separator: " ") }
        let cleaned = paragraphs.compactMap { paragraph -> String? in
            let sentences = paragraph.replacingOccurrences(of: #"(?<=[.!?])\s+"#, with: "\n", options: .regularExpression)
                .components(separatedBy: "\n")
                .filter { !$0.contains("`") || $0.range(of: #"`[a-z]+_[a-z_]+`"#, options: .regularExpression) == nil }
            let text = sentences.joined(separator: " ")
                .replacingOccurrences(of: "`", with: "")
                .replacingOccurrences(of: "**", with: "")
                .replacingOccurrences(of: "__", with: "")
                .trimmingCharacters(in: .whitespaces)
            return text.isEmpty ? nil : text
        }
        let text = cleaned.joined(separator: "\n\n")
        return text.isEmpty ? nil : text
    }

    /// "3:51".
    static func clock(_ seconds: Int) -> String {
        "\(max(seconds, 0) / 60):\(String(format: "%02d", max(seconds, 0) % 60))"
    }

    #if DEBUG
    static func demoPlanned(_ weekStart: String) -> PlanCoachResult {
        let plan: [(Sport, Int)] = [(.strength, 45), (.ride, 45), (.strength, 50), (.mobility, 25), (.strength, 45), (.ride, 90), (.rest, 0)]
        let strip = plan.enumerated().map { offset, item in
            PlanWeekStrip.Day(date: PlanFormat.addingDays(offset, to: weekStart), color: item.0 == .rest ? nil : item.0.color, minutes: item.1, style: .normal)
        }
        return PlanCoachResult(task: .plan(week: weekStart), days: strip, changes: [], totalMinutes: 300,
                               mix: [MixPart(sport: .strength, label: "3 lifts"), MixPart(sport: .ride, label: "2 rides"), MixPart(sport: .mobility, label: "rehab")],
                               summary: "Lifts stay at three, Thursday is rehab only for the deadline, and Saturday's 90 min ride is gated on the knee: drop to 60 min if it's above 2/10.",
                               seconds: 231,
                               sessions: zip(plan.indices, ["Workout B · Back + Arms", "Sweet spot 3×10", "Workout C · Wide Shoulders", "Rehab: left knee", "Workout A · Upper", "Endurance ride", "Rest"]).map { offset, title in
                                   Session(date: PlanFormat.addingDays(offset, to: weekStart), sport: plan[offset].0, title: title,
                                           meta: plan[offset].0 == .rest ? "" : "\(plan[offset].1) min")
                               })
    }

    static func demoChanged(_ week: WeeklyPlan, today: String) -> PlanCoachResult {
        let editable = editableDates(week, today: today)
        let targets = Array(editable.dropFirst(2).prefix(2))
        let changes = targets.enumerated().map { index, date in
            Change(date: date, was: describe(week.days.first { $0.date == date }),
                   now: index == 0 ? "Rehab: left knee · 20 min" : "Workout B + C merged · 50 min")
        }
        return PlanCoachResult(task: .refine(week: week.weekStart),
                               days: strip(week, today: today, changed: Set(targets), editable: Set(editable)),
                               changes: changes, totalMinutes: totalMinutes(week.days), mix: mix(week.days),
                               summary: "Kept 3 lifts by merging Saturday; Sunday's ride is unchanged.", seconds: 140)
    }
    #endif
}
