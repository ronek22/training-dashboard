import Foundation
import Observation
import SwiftUI

/// Body, opened from the readiness card on Today: last night's sleep stages, steps and heart rate
/// today, and fitness, fatigue and form from training load.
@MainActor
@Observable
final class BodyModel {
    private(set) var data: PhoneBody?
    /// Hour-by-hour steps and heart rate from Apple Health on this phone, when it has them.
    private(set) var live: LiveDay?
    private(set) var syncedAt: Date?
    private(set) var offline = false
    private(set) var error: String?

    private let client: () -> APIClient
    private let readLive: @Sendable @MainActor () async -> LiveDay?

    init(
        client: @escaping () -> APIClient = { .current },
        readLive: @escaping @Sendable @MainActor () async -> LiveDay? = { await BodyModel.readHealth() }
    ) {
        self.client = client
        self.readLive = readLive
    }

    static let path = "/phone/body"

    func load() async {
        let api = client()
        if data == nil, let cached = api.cached(Self.path, as: PhoneBody.self) {
            data = cached.value
            syncedAt = cached.syncedAt
        }
        let read = readLive
        async let health = read()
        do {
            let loaded = try await api.get(Self.path, as: PhoneBody.self, timeout: 12)
            data = loaded.value
            syncedAt = loaded.syncedAt
            offline = loaded.fromCache
            error = nil
        } catch {
            offline = data != nil
            self.error = error.localizedDescription
        }
        live = await health
    }

    /// Pull to refresh pushes Health to the Mac first, so last night and today's steps are current.
    func refresh() async {
        await APIClient.current.reconnect()
        await HealthSync.shared.sync(force: true)
        await load()
    }

    private static func readHealth() async -> LiveDay? {
        guard HealthSync.shared.readsRecovery else { return nil }
        // Asks only for what hasn't been asked yet (heart rate, the first time).
        await HealthSync.shared.requestAccess()
        return await LiveHealth.today()
    }

    /// Steps today: the phone's own count beats the last push to the Mac.
    var steps: Double? {
        if let live, live.stepTotal > 0 { return live.stepTotal }
        guard let vital = data?.vitals.steps, vital.date == data?.date else { return nil }
        return vital.value
    }
}

enum SleepStage: String, CaseIterable, Identifiable {
    case awake, rem, core, deep
    var id: String { rawValue }

    init?(backend: String) {
        if backend == "asleep_unspecified" { self = .core } else { self.init(rawValue: backend) }
    }

    var title: String {
        switch self {
        case .awake: "Awake"
        case .rem: "REM"
        case .core: "Core"
        case .deep: "Deep"
        }
    }

    /// Lane from the top of the hypnogram, Apple Health's order.
    var lane: Int { SleepStage.allCases.firstIndex(of: self) ?? 0 }

    var color: Color {
        switch self {
        case .awake: Color(hex: 0xFF8A7A)
        case .rem: Color(hex: 0x6FD3FF)
        case .core: .ride
        case .deep: .other
        }
    }
}

/// A stretch of one stage, as fractions of the night (0 = fell asleep, 1 = woke up).
struct SleepBlock: Equatable, Identifiable {
    let stage: SleepStage
    let from: Double
    let to: Double
    var id: Double { from }
}

/// Where form (fitness minus fatigue) sits, in the usual TrainingPeaks bands.
struct FormZone: Equatable {
    let label: String
    let note: String
    let color: Color
}

/// Pure formatting for the Body screen (unit-tested).
enum BodyFormat {
    static func date(_ value: String) -> Date? {
        try? Date(value, strategy: .iso8601)
    }

    static func blocks(_ sleep: PhoneBody.Sleep) -> [SleepBlock] {
        guard let start = date(sleep.start), let end = date(sleep.end), end > start else { return [] }
        let length = end.timeIntervalSince(start)
        return sleep.segments.compactMap { segment in
            guard let stage = SleepStage(backend: segment.stage), let from = date(segment.start), let to = date(segment.end) else { return nil }
            return SleepBlock(
                stage: stage,
                from: max(0, from.timeIntervalSince(start) / length),
                to: min(1, to.timeIntervalSince(start) / length)
            )
        }
    }

    static func hours(_ stage: SleepStage, _ stages: SleepStages) -> Double {
        switch stage {
        case .awake: stages.awake ?? 0
        case .rem: stages.rem ?? 0
        case .core: stages.core ?? 0
        case .deep: stages.deep ?? 0
        }
    }

    /// "6 h 12", "48 min".
    static func duration(_ hours: Double) -> String {
        let minutes = Int((hours * 60).rounded())
        if minutes < 60 { return "\(minutes) min" }
        return "\(minutes / 60) h \(String(format: "%02d", minutes % 60))"
    }

    /// "00:28" in the phone's time zone.
    static func clock(_ value: String) -> String {
        guard let date = date(value) else { return "–" }
        return date.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(Locale(identifier: "en_GB")))
    }

    /// "−34 min vs 30 d" for sleep; nil when there's no baseline.
    static func sleepDelta(_ sleep: PhoneBody.Sleep) -> (text: String, good: Bool?)? {
        guard let baseline = sleep.baselineH else { return nil }
        let delta = sleep.asleepH - baseline
        let minutes = Int((abs(delta) * 60).rounded())
        if minutes < 15 { return ("On your average", nil) }
        return ("\(delta < 0 ? "−" : "+")\(minutes) min vs 30 d", delta > 0)
    }

    /// "+3 bpm", "−12 %"; good is nil inside day-to-day noise.
    static func vitalDelta(_ vital: PhoneBody.Vital, higherIsBetter: Bool, unit: String) -> (text: String, good: Bool?)? {
        guard let baseline = vital.baseline else { return nil }
        let delta = vital.value - baseline
        if abs(delta) < 1.5 { return ("Steady", nil) }
        return ("\(delta < 0 ? "−" : "+")\(Int(abs(delta).rounded())) \(unit)", (delta > 0) == higherIsBetter)
    }

    static func steps(_ value: Double) -> String {
        value.formatted(.number.precision(.fractionLength(0)).locale(Locale(identifier: "en_US")))
    }

    static func formZone(_ form: Double) -> FormZone {
        switch form {
        case 25...: FormZone(label: "Detraining", note: "Fresh for a long while. Fitness is starting to fade.", color: .warning)
        case 5..<25: FormZone(label: "Fresh", note: "Rested and ready for a hard day or a test.", color: .mobility)
        case -10..<5: FormZone(label: "Neutral", note: "Fitness and fatigue are in balance.", color: .inkSoft)
        case -30 ..< -10: FormZone(label: "Building", note: "Productive fatigue: the load is making you fitter.", color: .ride)
        default: FormZone(label: "Overreaching", note: "Fatigue is well above fitness. Plan easy days.", color: .danger)
        }
    }

    /// "+4", "−12".
    static func signed(_ value: Double) -> String {
        let rounded = Int(value.rounded())
        return rounded > 0 ? "+\(rounded)" : rounded < 0 ? "−\(-rounded)" : "0"
    }

    static func toneColor(_ tone: String) -> Color {
        switch tone {
        case "risk": .danger
        case "caution": .warning
        default: .mobility
        }
    }
}
