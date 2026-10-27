import Foundation
import Observation
import UIKit

/// The + sheet: morning check-in, body weight, a manual activity or a coach note. Writes made
/// while the server is unreachable go to the shared write queue.
@MainActor
@Observable
final class QuickLogModel {
    enum Tab: String, CaseIterable, Identifiable {
        case checkin = "Check-in", weight = "Weight", activity = "Activity", note = "Note"
        var id: Self { self }
    }

    var tab: Tab = .checkin

    // Check-in
    var energy: Int?
    var sleep: Int?
    var stress: Int?
    var pain = 0
    var soreAreas: Set<String> = [] {
        didSet { soreTouched = true }
    }
    var sick = false
    private(set) var wasSick = false
    /// Today's saved check-in: its soreness is kept unless the chips change, its note always is.
    private(set) var existing: DailyCheckin?
    private var soreTouched = false

    // Weight
    var weight = ""
    private(set) var lastWeight: MetricPoint?

    // Activity
    var activityType = QuickLogFormat.activityTypes[0]
    var duration = ""
    var distance = ""
    var activityName = ""

    // Note
    var noteCategory = "general"
    var noteText = ""

    private(set) var saving = false
    private(set) var error: String?
    /// Set after a save: whether it reached the server or was queued.
    private(set) var savedOffline: Bool?

    private let client: () -> APIClient
    private let queue: WriteQueue
    private let today: String
    private let makeID: () -> String

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), today: Date = .now,
         makeID: @escaping () -> String = { "phone-" + UUID().uuidString.lowercased() }) {
        self.client = client
        self.queue = queue
        self.today = FoodFormat.iso(today)
        self.makeID = makeID
    }

    func load() async {
        let api = client()
        async let checkin = try? api.getLive("/checkins/today?date=\(today)", as: CheckinResponse.self)
        async let sickMode = try? api.getLive("/sick-mode", as: SickModeResponse.self)
        async let weights = try? api.getLive("/metrics/weight?limit=1", as: [MetricPoint].self)
        if let saved = await checkin?.checkin {
            existing = saved
            energy = saved.energy
            sleep = saved.sleepQuality
            stress = saved.stress
            pain = saved.painLevel ?? 0
            if saved.muscleSoreness <= 1 { soreAreas = [QuickLogFormat.noSoreness] }
            soreTouched = false
        }
        if let active = await sickMode?.sickMode.active {
            sick = active
            wasSick = active
        }
        lastWeight = await weights?.first
        if weight.isEmpty, let lastWeight { weight = QuickLogFormat.decimal(lastWeight.value) }
    }

    var canSave: Bool {
        guard !saving else { return false }
        switch tab {
        case .checkin: return checkinInput != nil
        case .weight: return weightInput != nil
        case .activity: return activityInput != nil
        case .note: return noteInput != nil
        }
    }

    var actionTitle: String {
        switch tab {
        case .checkin: "Save check-in"
        case .weight: "Save weight"
        case .activity: "Save activity"
        case .note: "Save note"
        }
    }

    var checkinInput: CheckinInput? {
        guard let energy, let sleep, let stress else { return nil }
        let soreness = soreTouched || existing == nil
            ? QuickLogFormat.soreness(soreAreas)
            : existing?.muscleSoreness ?? 1
        return CheckinInput(date: today, energy: energy, muscleSoreness: soreness, stress: stress,
                            sleepQuality: sleep, painLevel: pain, note: existing?.note)
    }

    var weightInput: MetricInput? {
        guard let value = QuickLogFormat.number(weight), (25...300).contains(value) else { return nil }
        return MetricInput(date: today, metric: "weight", value: value, unit: "kg")
    }

    var activityInput: ActivityInput? {
        guard let minutes = QuickLogFormat.number(duration), minutes > 0, minutes <= 24 * 60 else { return nil }
        let km = QuickLogFormat.number(distance).flatMap { $0 > 0 ? $0 : nil }
        if !distance.trimmingCharacters(in: .whitespaces).isEmpty && km == nil { return nil }
        let name = activityName.trimmingCharacters(in: .whitespacesAndNewlines)
        return ActivityInput(id: makeID(), date: today, type: activityType.type, name: name.nilIfEmpty ?? activityType.label,
                             durationMin: minutes, distanceKm: km, notes: nil)
    }

    var noteInput: NoteInput? {
        let content = noteText.trimmingCharacters(in: .whitespacesAndNewlines)
        return content.isEmpty ? nil : NoteInput(date: today, category: noteCategory, content: content)
    }

    func toggleSore(_ area: String) {
        if area == QuickLogFormat.noSoreness {
            soreAreas = soreAreas.contains(area) ? [] : [area]
        } else {
            var areas = soreAreas.subtracting([QuickLogFormat.noSoreness])
            if areas.contains(area) { areas.remove(area) } else { areas.insert(area) }
            soreAreas = areas
        }
    }

    /// Sends the current tab's write. Returns true when the sheet can close.
    func save() async -> Bool {
        var writes: [WriteQueue.Write] = []
        switch tab {
        case .checkin:
            guard let input = checkinInput else { return false }
            writes.append(.init(method: "POST", path: "/checkins", body: try? APIClient.encoder.encode(input)))
            if sick != wasSick {
                writes.append(sick
                    ? .init(method: "POST", path: "/sick-mode", body: try? APIClient.encoder.encode(SickModeInput()))
                    : .init(method: "POST", path: "/sick-mode/end", body: nil))
            }
        case .weight:
            guard let input = weightInput else { return false }
            writes.append(.init(method: "POST", path: "/metrics", body: try? APIClient.encoder.encode(input)))
        case .activity:
            guard let input = activityInput else { return false }
            writes.append(.init(method: "POST", path: "/activities", body: try? APIClient.encoder.encode(input)))
        case .note:
            guard let input = noteInput else { return false }
            writes.append(.init(method: "POST", path: "/notes", body: try? APIClient.encoder.encode(input)))
        }

        saving = true
        defer { saving = false }
        let api = client()
        await queue.flush(with: api)
        for (index, write) in writes.enumerated() {
            do {
                try await api.send(write.method, write.path, body: write.body)
            } catch APIError.unreachable {
                writes[index...].forEach(queue.append)
                savedOffline = true
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                return true
            } catch {
                self.error = error.localizedDescription
                UINotificationFeedbackGenerator().notificationOccurred(.error)
                return false
            }
        }
        savedOffline = false
        error = nil
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        return true
    }
}

/// Pure labels and mappings for the quick log sheet (unit-tested).
enum QuickLogFormat {
    static let noSoreness = "None"
    static let soreAreas = ["Chest", "Legs", "Back", "Shoulders", "Arms", noSoreness]

    static let energyWords = ["Drained", "Low", "OK", "Good", "Fresh"]
    static let sleepWords = ["Poor", "Restless", "OK", "Good", "Great"]
    static let stressWords = ["Calm", "Low", "Moderate", "High", "Overloaded"]

    struct ActivityType: Hashable, Sendable {
        let label: String
        /// Backend activity type, as Strava and HealthFit name them.
        let type: String
        let sport: Sport
    }

    /// Strength has its own session screen, so it isn't offered here.
    static let activityTypes = [
        ActivityType(label: "Ride", type: "Ride", sport: .ride),
        ActivityType(label: "Run", type: "Run", sport: .run),
        ActivityType(label: "Walk", type: "Walk", sport: .walk),
        ActivityType(label: "Hike", type: "Hike", sport: .hike),
        ActivityType(label: "Mobility", type: "Yoga", sport: .mobility),
        ActivityType(label: "Other", type: "Workout", sport: .other),
    ]

    static let noteCategories: [(value: String, label: String)] = [
        ("general", "General"), ("strength", "Strength"), ("cycling", "Cycling"),
        ("running", "Running"), ("nutrition", "Food"), ("heel", "Heel"),
    ]

    /// Sore areas become the backend's 1–5 soreness: none → 1, one area → 2, up to 4 for three or more.
    static func soreness(_ areas: Set<String>) -> Int {
        let count = areas.subtracting([noSoreness]).count
        return min(4, count + 1)
    }

    static func word(_ value: Int?, in words: [String]) -> String {
        guard let value, (1...words.count).contains(value) else { return "" }
        return words[value - 1]
    }

    /// Accepts both "82.4" and the Polish keyboard's "82,4".
    static func number(_ text: String) -> Double? {
        Double(text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "."))
    }

    static func decimal(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(format: "%.1f", value)
    }
}
