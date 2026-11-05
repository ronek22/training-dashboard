import Foundation
import Testing
@testable import TrainLog

/// Decodes each screen's real backend response with the app's DTOs, so a backend change that would
/// leave a screen on "didn't decode" shows up here first. Off by default; with the Mac's server up:
///
///     TEST_RUNNER_TRAINLOG_LIVE=1 xcodebuild test -scheme TrainLog \
///       -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:TrainLogTests/LiveContractTests
///
/// Read-only: every request is a GET.
@Suite(.serialized, .enabled(if: ProcessInfo.processInfo.environment["TRAINLOG_LIVE"] != nil))
@MainActor
struct LiveContractTests {
    private let base = ProcessInfo.processInfo.environment["TRAINLOG_LIVE_URL"] ?? "http://localhost:8000"

    private func decode<T: Decodable>(_ path: String, as type: T.Type) async throws {
        let url = try #require(URL(string: base + path))
        let (data, response) = try await URLSession.shared.data(from: url)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        try #require(status == 200, "GET \(path) answered \(status)")
        do {
            _ = try APIClient.decoder.decode(T.self, from: data)
        } catch {
            Issue.record("GET \(path) didn't decode as \(T.self): \(error)")
        }
    }

    private var today: String { FoodFormat.iso(.now) }

    /// This week's Monday, as the dinner planner keys its weeks.
    private var monday: String {
        var calendar = Calendar(identifier: .iso8601)
        calendar.timeZone = .current
        let start = calendar.dateInterval(of: .weekOfYear, for: .now)?.start ?? .now
        return FoodFormat.iso(start)
    }

    @Test func today() async throws {
        try await decode(TodayModel.path, as: PhoneToday.self)
        try await decode("/checkins/today?date=\(today)", as: CheckinResponse.self)
        try await decode("/sick-mode", as: SickModeResponse.self)
        try await decode("/life-load?start=\(today)&end=\(today)", as: LifeLoadResponse.self)
        try await decode("/metrics/weight?limit=1", as: [MetricPoint].self)
    }

    @Test func plan() async throws {
        try await decode(PlanModel.weeksPath, as: [WeeklyPlan].self)
        try await decode(PlanModel.arcPath, as: WinterArc.self)
        try await decode(PlanModel.stallPath, as: [StallBlock].self)
        try await decode(WeekBriefFormat.path(PlanFormat.weekStart(of: today)), as: WeekBrief.self)
        try await decode("/guided-sessions/rehab", as: GuidedSessionEnvelope.self)
    }

    @Test func food() async throws {
        try await decode(FoodModel.dayPath(today), as: FoodDay.self)
        try await decode(FoodModel.dinnersPath(monday), as: DinnerWeek.self)
    }

    @Test func activities() async throws {
        try await decode(ActivitiesModel.listPath, as: [ActivitySummary].self)
        let url = try #require(URL(string: base + ActivitiesModel.listPath))
        let (data, _) = try await URLSession.shared.data(from: url)
        // The newest few, whatever sport they are.
        let ids = (try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []).prefix(5).compactMap { $0["id"] }
        for id in ids {
            try await decode("/activities/\(id)", as: ActivityDetail.self)
        }
    }

    @Test func strength() async throws {
        try await decode(WorkoutStudioModel.path, as: [StrengthTemplateSummary].self)
        try await decode("/strength/workouts/sessions/active", as: StrengthSession?.self)
        try await decode("/strength/workouts/sessions?limit=12", as: [StrengthSession].self)
        try await decode(WorkoutBuilderModel.suggestionsPath, as: [ExerciseSuggestion].self)
    }

    @Test func bodyTrendsAndRun() async throws {
        try await decode(BodyModel.path, as: PhoneBody.self)
        try await decode(TrendsModel.historyPath, as: TrainingHistory.self)
        try await decode(TrendsModel.trendsPath, as: TrendsSummary.self)
        try await decode(TrendsModel.healthPath, as: HealthSummary.self)
        try await decode(RunModel.path, as: RunningFitness.self)
    }
}
