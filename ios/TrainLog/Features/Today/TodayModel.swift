import Foundation
import Observation
import SwiftUI

@MainActor
@Observable
final class TodayModel {
    private(set) var data: PhoneToday?
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?
    private(set) var loading = false
    /// An open strength workout (started here or on the web), for the Resume banner.
    private(set) var activeWorkout: StrengthSession?

    private let client: () -> APIClient

    init(client: @escaping () -> APIClient = { .current }) {
        self.client = client
    }

    private static var path: String {
        #if DEBUG
        // `-todayDate 2026-10-28` as a launch argument previews another day.
        if let day = UserDefaults.standard.string(forKey: "todayDate") { return "/phone/today?date=\(day)" }
        #endif
        return "/phone/today"
    }

    func load() async {
        loading = true
        defer { loading = false }
        let api = client()
        if data == nil, let cached = api.cached(Self.path, as: PhoneToday.self) {
            data = cached.value
            syncedAt = cached.syncedAt
        }
        async let workout = Self.activeWorkout(api)
        do {
            let loaded = try await api.get(Self.path, as: PhoneToday.self)
            data = loaded.value
            syncedAt = loaded.syncedAt
            offline = loaded.fromCache
            error = nil
            let baseURL = api.baseURL
            WidgetStore.update { $0.baseURL = baseURL; $0.today = .init(loaded.value) }
        } catch {
            offline = data != nil
            self.error = error.localizedDescription
        }
        activeWorkout = await workout
        // A workout finished on the web leaves no open session to end the Live Activity.
        if activeWorkout == nil { StrengthActivity.end() }
    }

    /// Keeps the Resume banner in step with a workout started, advanced or finished on the web.
    func refreshWorkout() async {
        guard !loading else { return }
        let workout = await Self.activeWorkout(client())
        if workout != activeWorkout { activeWorkout = workout }
    }

    /// The server's open workout; when it's unreachable, the one this phone has in progress.
    private static func activeWorkout(_ client: APIClient) async -> StrengthSession? {
        do {
            return try await client.getLive("/strength/workouts/sessions/active", as: StrengthSession?.self)
        } catch {
            return SessionStore().load().flatMap { $0.isActive ? $0 : nil }
        }
    }
}

/// Pure formatting for the Today screen (unit-tested).
enum TodayFormat {
    static func duration(_ minutes: Int) -> String {
        let hours = minutes / 60
        let rest = minutes % 60
        if hours == 0 { return "\(rest)m" }
        return rest == 0 ? "\(hours)h" : "\(hours)h \(rest)m"
    }

    static func exerciseTarget(_ exercise: PhoneToday.Exercise) -> String {
        let reps = exercise.reps.map { "\(exercise.sets) × \($0)" } ?? "\(exercise.sets) sets"
        let load = exercise.weightKg.map { "\(number($0)) kg" } ?? "BW"
        return "\(reps) · \(load)"
    }

    static func number(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(format: "%.1f", value)
    }

    /// "WEDNESDAY · 28 OCTOBER" from "2026-10-28".
    static func dateKicker(_ iso: String) -> String {
        guard let date = parse(iso) else { return iso }
        return date.formatted(.dateTime.weekday(.wide).locale(.en)) + " · " + date.formatted(.dateTime.day().month(.wide).locale(.en))
    }

    /// "Thu 22" for "last done" within the past week, "Thu 17 Sep" before that.
    static func shortDay(_ iso: String, relativeTo today: String) -> String {
        guard let date = parse(iso) else { return iso }
        let recent = parse(today).map { $0.timeIntervalSince(date) < 7 * 86_400 } ?? false
        let day = date.formatted(.dateTime.weekday(.abbreviated).locale(.en)) + " " + date.formatted(.dateTime.day().locale(.en))
        return recent ? day : day + " " + date.formatted(.dateTime.month(.abbreviated).locale(.en))
    }

    static func parse(_ iso: String) -> Date? {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: iso)
    }

    static func readiness(_ level: String) -> (label: String, color: Color) {
        switch level {
        case "green": ("Good to go", .mobility)
        case "amber": ("Go easy", .warning)
        case "red": ("Take it easy", .danger)
        default: ("No read yet", .muted)
        }
    }

    static func painColor(_ pain: Int) -> Color {
        switch pain {
        case ...2: .mobility
        case 3...5: .warning
        default: .danger
        }
    }
}

private extension Locale {
    static let en = Locale(identifier: "en_GB")
}
