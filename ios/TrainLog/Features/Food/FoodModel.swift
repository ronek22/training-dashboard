import Foundation
import Observation
import UIKit

/// The Food tab: one day's eating against its target, the planned dinner, and the snap-a-meal flow.
@MainActor
@Observable
final class FoodModel {
    private(set) var day: FoodDay?
    private(set) var dinner: DinnerWeek.Day?
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    /// Meals saved while the server was unreachable, shown until they sync.
    private(set) var pending: [FoodEntryInput] = []
    private(set) var selectedDate: String

    private let client: () -> APIClient
    private let queue: WriteQueue

    init(client: @escaping () -> APIClient = { .current }, queue: WriteQueue = WriteQueue(), today: Date = .now) {
        self.client = client
        self.queue = queue
        selectedDate = FoodFormat.iso(today)
    }

    var isToday: Bool { selectedDate == FoodFormat.iso(.now) }

    /// Logged plus not-yet-synced meals.
    var eaten: Macros {
        pending.filter { $0.date == selectedDate }.flatMap(\.items).reduce(day?.totals ?? .zero) { FoodFormat.add($0, $1) }
    }

    /// The planned dinner, while it isn't logged yet.
    var plannedDinner: DinnerWeek.Day? {
        guard let dinner, !dinner.logged, dinner.dish != nil,
              !pending.contains(where: { $0.date == selectedDate && $0.meal == FoodFormat.plannedMeal }) else { return nil }
        return dinner
    }

    func shiftDay(_ days: Int) async {
        guard let start = FoodFormat.parse(selectedDate),
              let date = Calendar(identifier: .gregorian).date(byAdding: .day, value: days, to: start) else { return }
        selectedDate = FoodFormat.iso(date)
        day = nil
        dinner = nil
        await load()
    }

    func load() async {
        let api = client()
        if await queue.flush(with: api) { pending = [] }
        let date = selectedDate
        async let dinners = try? api.get("/nutrition/dinners?week_start=\(date)", as: DinnerWeek.self)
        do {
            let loaded = try await api.get("/nutrition/food?date=\(date)", as: FoodDay.self)
            guard date == selectedDate else { return }
            day = loaded.value
            syncedAt = loaded.syncedAt
            offline = loaded.fromCache
            error = nil
        } catch {
            offline = day != nil
            self.error = error.localizedDescription
        }
        let week = await dinners
        if date == selectedDate {
            dinner = week?.value.days.first { $0.date == date }
        }
    }

    /// Saves a meal; when the server is unreachable it's queued and counted locally.
    func save(_ entry: FoodEntryInput) async {
        let api = client()
        guard let body = try? APIClient.encoder.encode(entry) else { return }
        do {
            day = try await api.send("POST", "/nutrition/food/entries", body: body, as: FoodDay.self)
            syncedAt = .now
            offline = false
            error = nil
        } catch APIError.unreachable {
            queue.append(.init(method: "POST", path: "/nutrition/food/entries", body: body))
            pending.append(entry)
            offline = true
        } catch {
            self.error = error.localizedDescription
        }
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    func delete(_ entry: FoodEntry) async {
        do {
            day = try await client().send("DELETE", "/nutrition/food/entries/\(entry.id)", as: FoodDay.self)
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Logs the planned dinner as eaten, with the recipe's portions when there is one.
    func logPlannedDinner() async {
        guard let dinner = plannedDinner, let dish = dinner.dish else { return }
        let items: [FoodItem]
        if let loaded = try? await client().getLive("/nutrition/dinners/\(dinner.date)/log-items", as: DinnerLogItems.self),
           !loaded.items.isEmpty {
            items = loaded.items
        } else {
            items = [FoodItem(name: dish, kcal: dinner.kcal ?? 0, proteinG: dinner.proteinG ?? 0)]
        }
        await save(FoodEntryInput(date: dinner.date, meal: FoodFormat.plannedMeal, source: "manual", rawText: dish, items: items))
    }
}

/// Sends a photo and/or description to Claude (through the backend relay) and polls for the items.
@MainActor
@Observable
final class MealEstimateModel {
    enum Phase: Equatable {
        case idle
        case estimating(String)
        case ready
        case failed(String)
    }

    var photo: UIImage?
    var text = ""
    var meal: String
    var items: [FoodItem] = []
    private(set) var note = ""
    private(set) var phase: Phase = .idle

    private let client: () -> APIClient
    private let pollInterval: Duration

    init(photo: UIImage?, meal: String = FoodFormat.defaultMeal(), client: @escaping () -> APIClient = { .current },
         pollInterval: Duration = .seconds(1.5)) {
        self.photo = photo
        self.meal = meal
        self.client = client
        self.pollInterval = pollInterval
    }

    var canEstimate: Bool {
        if case .estimating = phase { return false }
        return photo != nil || !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var totals: Macros { items.reduce(.zero, FoodFormat.add) }

    func estimate() async {
        guard canEstimate else { return }
        phase = .estimating("Sending to Claude…")
        let request = MealEstimateRequest(
            text: text.trimmingCharacters(in: .whitespacesAndNewlines),
            image: photo.flatMap { MealPhoto.jpeg($0) }.map { .init(mediaType: "image/jpeg", data: $0.base64EncodedString()) }
        )
        let api = client()
        do {
            var job = try await api.send("POST", "/phone/meal-estimate", body: try APIClient.encoder.encode(request), as: MealEstimateJob.self)
            while job.status != "succeeded" {
                if job.status == "failed" { throw EstimateFailed(message: job.message ?? "The estimate failed.") }
                phase = .estimating(job.message ?? "Estimating…")
                try await Task.sleep(for: pollInterval)
                job = try await api.getLive("/phone/meal-estimate/\(job.jobId)", as: MealEstimateJob.self)
            }
            items = job.estimate?.items ?? []
            note = job.estimate?.note ?? ""
            phase = items.isEmpty ? .failed(note.isEmpty ? "No food was recognised. Add a few words about it." : note) : .ready
        } catch is CancellationError {
            phase = .idle
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    func entry(date: String) -> FoodEntryInput {
        FoodEntryInput(
            date: date,
            meal: meal,
            source: photo == nil ? "text" : "photo",
            rawText: text.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty,
            items: items.filter { !$0.name.trimmingCharacters(in: .whitespaces).isEmpty }
        )
    }

    nonisolated static func message(for error: Error) -> String {
        switch error {
        case APIError.status(503): "The coach helper on the Mac isn't running. Start it with `just coach-helper-start`."
        case APIError.status(404): "The coach helper restarted. Estimate again."
        case APIError.unreachable: "Can't reach the TrainLog server. Estimates need the Mac."
        case let failed as EstimateFailed: failed.message
        default: error.localizedDescription
        }
    }

    private struct EstimateFailed: Error {
        let message: String
    }
}

/// Photos are downscaled before upload: enough to judge portions or read a label, far smaller to send.
enum MealPhoto {
    static func jpeg(_ image: UIImage, maxSide: CGFloat = 1280) -> Data? {
        let longest = max(image.size.width, image.size.height)
        let scale = min(1, maxSide / max(longest, 1))
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        return resized.jpegData(compressionQuality: 0.85)
    }
}

/// Pure formatting and logic for the Food screen (unit-tested).
enum FoodFormat {
    /// The planned main meal (Polish obiad) is stored as "lunch" and labelled Dinner, as on the web.
    static let plannedMeal = "lunch"
    static let meals: [(value: String, label: String)] = [
        ("breakfast", "Breakfast"), ("lunch", "Dinner"), ("dinner", "Supper"), ("snack", "Snack"),
    ]

    static func mealLabel(_ meal: String) -> String {
        meals.first { $0.value == meal }?.label ?? meal.capitalized
    }

    static func defaultMeal(at date: Date = .now) -> String {
        switch Calendar.current.component(.hour, from: date) {
        case ..<11: "breakfast"
        case ..<16: "lunch"
        case ..<21: "dinner"
        default: "snack"
        }
    }

    static func emoji(_ meal: String) -> String {
        switch meal {
        case "breakfast": "🥣"
        case "lunch": "🍲"
        case "dinner": "🥗"
        default: "🍎"
        }
    }

    /// "Breakfast · 07:40 · from photo".
    static func entryMeta(_ entry: FoodEntry, timeZone: TimeZone = .current) -> String {
        var parts = [mealLabel(entry.meal)]
        if let created = entry.createdAt.flatMap(parseTimestamp) {
            let clock = DateFormatter()
            clock.locale = Locale(identifier: "en_US_POSIX")
            clock.timeZone = timeZone
            clock.dateFormat = "HH:mm"
            parts.append(clock.string(from: created))
        }
        if entry.source == "photo" { parts.append("from photo") }
        return parts.joined(separator: " · ")
    }

    /// The first item names the meal; "+2" counts the rest.
    static func entryTitle(_ entry: FoodEntry) -> String {
        guard let first = entry.items.first?.name else { return entry.rawText ?? "Meal" }
        return entry.items.count > 1 ? "\(first) +\(entry.items.count - 1)" : first
    }

    static func add(_ total: Macros, _ item: FoodItem) -> Macros {
        Macros(kcal: total.kcal + item.kcal, proteinG: total.proteinG + item.proteinG,
               carbsG: total.carbsG + item.carbsG, fatG: total.fatG + item.fatG)
    }

    /// Scales an item's kcal and macros to new grams; an item without grams just takes them.
    static func rescale(_ item: FoodItem, grams: Double) -> FoodItem {
        var scaled = item
        scaled.grams = grams
        guard let old = item.grams, old > 0 else { return scaled }
        let factor = grams / old
        scaled.kcal = (item.kcal * factor).rounded()
        scaled.proteinG = (item.proteinG * factor * 10).rounded() / 10
        scaled.carbsG = (item.carbsG * factor * 10).rounded() / 10
        scaled.fatG = (item.fatG * factor * 10).rounded() / 10
        return scaled
    }

    static func kcal(_ value: Double) -> String {
        Int(value.rounded()).formatted(.number.grouping(.automatic).locale(Locale(identifier: "en_US")))
    }

    static func share(_ value: Double, of target: Double?) -> Double {
        guard let target, target > 0 else { return 0 }
        return min(1, max(0, value / target))
    }

    /// "TUESDAY · REST DAY" from the date and the target's day kind.
    static func dayKicker(_ iso: String, kind: String?) -> String {
        guard let date = parse(iso) else { return iso }
        let weekday = date.formatted(.dateTime.weekday(.wide).locale(Locale(identifier: "en_GB")))
        guard let kind, !kind.isEmpty else { return weekday }
        return weekday + " · " + kind.replacingOccurrences(of: "_", with: " ") + " day"
    }

    static func shortWeekday(_ iso: String) -> String {
        parse(iso)?.formatted(.dateTime.weekday(.abbreviated).locale(Locale(identifier: "en_GB"))) ?? iso
    }

    /// SQLite's CURRENT_TIMESTAMP: "2026-10-27 06:40:12", in UTC.
    static func parseTimestamp(_ value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.date(from: value)
    }

    static func iso(_ date: Date) -> String {
        formatter.string(from: date)
    }

    static func parse(_ iso: String) -> Date? {
        formatter.date(from: iso)
    }

    private static let formatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}
