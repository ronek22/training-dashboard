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
    /// Target hit / short per finished day, kept across loads so the week strip keeps its dots.
    private(set) var marks: [String: FoodFormat.DayMark] = [:]
    /// Today's Again cards, evening picks and ride fuel (`GET /phone/food/quick`).
    private(set) var quick: FoodQuick?
    /// The evening pick drawn as a ghost on the ring; the first one until another is tapped.
    var selectedPick: String?
    /// The last one-tap log: its Again card shows a check and the toast offers Undo.
    private(set) var relogged: Relogged?
    /// Screenshot state from `-foodDemo`; never touches the server.
    private var demo = false

    struct Relogged: Equatable {
        let key: String
        let meal: String
        let kcal: Double
        let entryId: Int?
    }

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

    /// The pick shown on the ring, when the evening card is up.
    var pick: FoodQuick.Pick? {
        guard let picks = quick?.gap?.picks else { return nil }
        return picks.first { $0.key == selectedPick } ?? picks.first
    }

    /// Mon–Sun of the selected day's week.
    var weekDates: [String] { FoodFormat.weekDates(of: selectedDate) }

    func shiftDay(_ days: Int) async {
        guard let start = FoodFormat.parse(selectedDate),
              let date = Calendar(identifier: .gregorian).date(byAdding: .day, value: days, to: start) else { return }
        await select(min(FoodFormat.iso(date), FoodFormat.iso(.now)))
    }

    /// Opens another day; days after today aren't loggable yet.
    func select(_ date: String) async {
        guard date != selectedDate, date <= FoodFormat.iso(.now) else { return }
        selectedDate = date
        day = nil
        dinner = nil
        quick = nil
        relogged = nil
        await load()
    }

    private func remember(_ day: FoodDay) {
        for item in day.week ?? [] {
            marks[item.date] = FoodFormat.mark(item)
        }
    }

    static func dayPath(_ date: String) -> String { "/nutrition/food?date=\(date)" }
    static func dinnersPath(_ date: String) -> String { "/nutrition/dinners?week_start=\(date)" }
    static func quickPath(_ date: String, hour: Int) -> String { "/phone/food/quick?date=\(date)&hour=\(hour)" }

    func load() async {
        guard !demo else { return }
        let api = client()
        let date = selectedDate
        if day == nil, let cached = api.cached(Self.dayPath(date), as: FoodDay.self) {
            day = cached.value
            remember(cached.value)
            syncedAt = cached.syncedAt
            dinner = api.cached(Self.dinnersPath(date), as: DinnerWeek.self)?.value.days.first { $0.date == date }
        }
        if await queue.flush(with: api) { pending = [] }
        async let dinners = try? api.get(Self.dinnersPath(date), as: DinnerWeek.self)
        do {
            let loaded = try await api.get(Self.dayPath(date), as: FoodDay.self)
            guard date == selectedDate else { return }
            day = loaded.value
            remember(loaded.value)
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
        await loadQuick()
        publishWidget()
    }

    /// Today only; a failed load keeps what was there.
    private func loadQuick() async {
        guard isToday else { return }
        let date = selectedDate
        let path = Self.quickPath(date, hour: Calendar.current.component(.hour, from: .now))
        if let loaded = try? await client().get(path, as: FoodQuick.self), date == selectedDate {
            quick = loaded.value
        }
    }

    /// One tap from an Again card or an evening pick: the items are logged as they are, no sheet.
    func quickLog(key: String, items: [FoodItem], meal: String = FoodFormat.defaultMeal()) async {
        guard !demo else { return }
        let before = Set(day?.entries.map(\.id) ?? [])
        await save(FoodEntryInput(date: selectedDate, meal: meal, source: "saved", rawText: nil, items: items))
        let added = day?.entries.first { !before.contains($0.id) }?.id
        relogged = Relogged(key: key, meal: meal, kcal: items.reduce(.zero, FoodFormat.add).kcal, entryId: added)
    }

    #if DEBUG
    func applyDemo(day: FoodDay, quick: FoodQuick, relogged: Relogged?) {
        demo = true
        self.day = day
        self.quick = quick
        self.relogged = relogged
        syncedAt = .now
    }
    #endif

    /// Removes the entry the last one-tap log made (only once the server has it).
    func undoQuickLog() async {
        guard !demo, let id = relogged?.entryId, let entry = day?.entries.first(where: { $0.id == id }) else { return }
        relogged = nil
        await delete(entry)
        await loadQuick()
    }

    /// The toast is gone: the cards catch up with what's now eaten.
    func finishQuickLog() async {
        guard !demo else { return }
        relogged = nil
        await loadQuick()
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
        publishWidget()
        Haptics.success()
    }

    /// Today's kcal to go for the Food widgets and the dinner nudge, counting meals still queued here.
    private func publishWidget() {
        guard isToday, let day, day.date == selectedDate else { return }
        let food = WidgetSnapshot.Food(day, eaten: eaten)
        WidgetStore.update { $0.food = food }
        let kcal = eaten.kcal
        Reminders.note {
            $0.eatenKcal = kcal
            $0.targetKcal = day.target?.kcal
        }
    }

    /// Saves corrections to a logged meal; offline, the change is queued and shown straight away.
    func update(_ entry: FoodEntry, with input: FoodEntryInput) async {
        let api = client()
        let path = "/nutrition/food/entries/\(entry.id)"
        guard let body = try? APIClient.encoder.encode(input) else { return }
        do {
            day = try await api.send("PUT", path, body: body, as: FoodDay.self)
            syncedAt = .now
            offline = false
            error = nil
        } catch APIError.unreachable {
            queue.append(.init(method: "PUT", path: path, body: body))
            day = day.map { FoodFormat.replacing(entry.id, with: input, in: $0) }
            offline = true
        } catch {
            self.error = error.localizedDescription
        }
        publishWidget()
        Haptics.success()
    }

    func delete(_ entry: FoodEntry) async {
        do {
            day = try await client().send("DELETE", "/nutrition/food/entries/\(entry.id)", as: FoodDay.self)
            publishWidget()
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
    /// Claude's own numbers per item, so a corrected item can go back to them.
    private(set) var estimated: [UUID: FoodItem] = [:]
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
            // A photo is a few hundred KB; on weak Wi-Fi the upload alone can outlast the default 8 s.
            var job = try await api.send("POST", "/phone/meal-estimate", body: try APIClient.encoder.encode(request), as: MealEstimateJob.self, timeout: 45)
            while job.status != "succeeded" {
                if job.status == "failed" { throw EstimateFailed(message: job.message ?? "The estimate failed.") }
                phase = .estimating(job.message ?? "Estimating…")
                try await Task.sleep(for: pollInterval)
                job = try await api.getLive("/phone/meal-estimate/\(job.jobId)", as: MealEstimateJob.self)
            }
            items = job.estimate?.items ?? []
            estimated = Dictionary(uniqueKeysWithValues: items.map { ($0.id, $0) })
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

    /// A finished, logged day against its target: volt dot when eaten, amber when short.
    enum DayMark: Equatable { case hit, short }

    static func mark(_ day: FoodDay.WeekDay) -> DayMark? {
        guard day.logged, day.finished, day.targetKcal != nil else { return nil }
        return day.under ? .short : .hit
    }

    /// Monday to Sunday of the week holding `iso`.
    static func weekDates(of iso: String) -> [String] {
        let calendar = Calendar(identifier: .gregorian)
        guard let date = parse(iso) else { return [iso] }
        let fromMonday = (calendar.component(.weekday, from: date) + 5) % 7
        return (0..<7).compactMap { calendar.date(byAdding: .day, value: $0 - fromMonday, to: date).map(Self.iso) }
    }

    /// Each macro's share of the kcal (4 / 4 / 9 kcal per gram), for the split bar and donut.
    static func kcalShares(_ macros: Macros) -> (protein: Double, carbs: Double, fat: Double) {
        let protein = macros.proteinG * 4, carbs = macros.carbsG * 4, fat = macros.fatG * 9
        let total = protein + carbs + fat
        guard total > 0 else { return (0, 0, 0) }
        return (protein / total, carbs / total, fat / total)
    }

    /// The whole meal scaled for a bigger or smaller portion: grams, portions and macros alike.
    static func portioned(_ items: [FoodItem], by factor: Double) -> [FoodItem] {
        guard factor > 0, factor != 1 else { return items }
        return items.map { item in
            var scaled = scale(item, by: factor)
            scaled.grams = item.grams.map { ($0 * factor).rounded() }
            scaled.portions = item.portions.map { ($0 * factor * 100).rounded() / 100 }
            return scaled
        }
    }

    /// "Oats, banana, whey" for a meal card.
    static func itemNames(_ items: [FoodItem], limit: Int = 3) -> String {
        let names = items.map(\.name).filter { !$0.isEmpty }
        let shown = names.prefix(limit).enumerated().map { $0.offset == 0 ? $0.element : $0.element.lowercased() }
        return shown.joined(separator: ", ") + (names.count > limit ? " +\(names.count - limit)" : "")
    }

    /// "07:40" from the entry's server timestamp.
    static func clock(_ entry: FoodEntry, timeZone: TimeZone = .current) -> String? {
        guard let created = entry.createdAt.flatMap(parseTimestamp) else { return nil }
        let clock = DateFormatter()
        clock.locale = Locale(identifier: "en_US_POSIX")
        clock.timeZone = timeZone
        clock.dateFormat = "HH:mm"
        return clock.string(from: created)
    }

    /// What's left of today's target after this meal, and whether the planned dinner closes it.
    static func impact(meal: Double, eaten: Double, target: Double?, dinner: Double?) -> (headline: String, detail: String, closes: Bool)? {
        guard let target else { return nil }
        let after = target - eaten - meal
        guard after > 0 else { return ("That covers today's target.", "", true) }
        let headline = "After this: \(kcal(after)) to go."
        guard let dinner else { return (headline, "", false) }
        let short = after - dinner
        return short > 0
            ? (headline, "Planned dinner still leaves ~\(kcal(short)) short.", false)
            : (headline, "Planned dinner covers the rest.", true)
    }

    static func add(_ total: Macros, _ item: FoodItem) -> Macros {
        Macros(kcal: total.kcal + item.kcal, proteinG: total.proteinG + item.proteinG,
               carbsG: total.carbsG + item.carbsG, fatG: total.fatG + item.fatG)
    }

    /// Scales an item's kcal and macros to new grams; an item without grams just takes them.
    /// Zero is ignored: it's only ever on the way to typing "0.5", and scaling by it can't be undone.
    static func rescale(_ item: FoodItem, grams: Double) -> FoodItem {
        guard grams > 0 else { return item }
        var scaled = item
        scaled.grams = grams
        guard let old = item.grams, old > 0 else { return scaled }
        return scale(scaled, by: grams / old)
    }

    /// Scales a recipe dish's kcal and macros to a new number of portions.
    static func rescale(_ item: FoodItem, portions: Double) -> FoodItem {
        guard portions > 0 else { return item }
        var scaled = item
        scaled.portions = portions
        guard let old = item.portions, old > 0 else { return scaled }
        return scale(scaled, by: portions / old)
    }

    private static func scale(_ item: FoodItem, by factor: Double) -> FoodItem {
        var scaled = item
        scaled.kcal = (item.kcal * factor).rounded()
        scaled.proteinG = (item.proteinG * factor * 10).rounded() / 10
        scaled.carbsG = (item.carbsG * factor * 10).rounded() / 10
        scaled.fatG = (item.fatG * factor * 10).rounded() / 10
        return scaled
    }

    /// The day with one entry swapped for its edited version, totals recounted (for offline edits).
    static func replacing(_ id: Int, with input: FoodEntryInput, in day: FoodDay) -> FoodDay {
        let entries = day.entries.map { entry in
            guard entry.id == id else { return entry }
            return FoodEntry(id: id, date: entry.date, meal: input.meal, source: input.source, rawText: input.rawText,
                             createdAt: entry.createdAt, items: input.items, totals: input.items.reduce(.zero, add))
        }
        return FoodDay(date: day.date, entries: entries, totals: entries.map(\.totals).reduce(.zero) {
            Macros(kcal: $0.kcal + $1.kcal, proteinG: $0.proteinG + $1.proteinG, carbsG: $0.carbsG + $1.carbsG, fatG: $0.fatG + $1.fatG)
        }, target: day.target, proteinTargetG: day.proteinTargetG, week: day.week)
    }

    static func kcal(_ value: Double) -> String {
        Int(value.rounded()).formatted(.number.grouping(.automatic).locale(Locale(identifier: "en_US")))
    }

    /// The kcal ring closes (and turns volt) once eaten reaches the target.
    static func ringClosed(eaten: Double, target: Double) -> Bool {
        target > 0 && eaten >= target
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
