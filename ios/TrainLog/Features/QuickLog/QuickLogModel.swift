import Foundation
import Observation
import UIKit

/// The check-in sheet opened from Today: the morning check-in plus an optional body weight. Writes
/// made while the server is unreachable go to the shared write queue.
@MainActor
@Observable
final class QuickLogModel {
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

    // Weight: left empty unless typed, so a check-in doesn't re-log yesterday's number.
    var weight = ""
    private(set) var lastWeight: MetricPoint?

    private(set) var saving = false
    private(set) var error: String?
    /// Set after a save: whether it reached the server or was queued.
    private(set) var savedOffline: Bool?

    private let client: () -> APIClient
    private let queue: WriteQueue
    private let today: String

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), today: Date = .now) {
        self.client = client
        self.queue = queue
        self.today = FoodFormat.iso(today)
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
        // Weighed in already today: show it so the sheet reads as an edit.
        if weight.isEmpty, let lastWeight, lastWeight.date == today { weight = QuickLogFormat.decimal(lastWeight.value) }
    }

    /// Weight is optional, but a typed one has to make sense.
    var canSave: Bool {
        !saving && checkinInput != nil && (weightEmpty || weightInput != nil)
    }

    var isEditing: Bool { existing != nil }

    private var weightEmpty: Bool { weight.trimmingCharacters(in: .whitespaces).isEmpty }

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

    func toggleSore(_ area: String) {
        if area == QuickLogFormat.noSoreness {
            soreAreas = soreAreas.contains(area) ? [] : [area]
        } else {
            var areas = soreAreas.subtracting([QuickLogFormat.noSoreness])
            if areas.contains(area) { areas.remove(area) } else { areas.insert(area) }
            soreAreas = areas
        }
    }

    /// The writes a save sends: the check-in, sick mode when it flipped, and a typed weight.
    var writes: [WriteQueue.Write] {
        guard let input = checkinInput else { return [] }
        var writes: [WriteQueue.Write] = [.init(method: "POST", path: "/checkins", body: try? APIClient.encoder.encode(input))]
        if sick != wasSick {
            writes.append(sick
                ? .init(method: "POST", path: "/sick-mode", body: try? APIClient.encoder.encode(SickModeInput()))
                : .init(method: "POST", path: "/sick-mode/end", body: nil))
        }
        if let weight = weightInput, weight.value != todaysWeight {
            writes.append(.init(method: "POST", path: "/metrics", body: try? APIClient.encoder.encode(weight)))
        }
        return writes
    }

    /// Today's already-logged weight, so re-saving a check-in doesn't post it twice.
    private var todaysWeight: Double? {
        lastWeight.flatMap { $0.date == today ? $0.value : nil }
    }

    /// Returns true when the sheet can close.
    func save() async -> Bool {
        guard canSave else { return false }
        let writes = self.writes

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

/// Pure labels and mappings for the check-in sheet (unit-tested).
enum QuickLogFormat {
    static let noSoreness = "None"
    static let soreAreas = ["Chest", "Legs", "Back", "Shoulders", "Arms", noSoreness]

    static let energyWords = ["Drained", "Low", "OK", "Good", "Fresh"]
    static let sleepWords = ["Poor", "Restless", "OK", "Good", "Great"]
    static let stressWords = ["Calm", "Low", "Moderate", "High", "Overloaded"]

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
