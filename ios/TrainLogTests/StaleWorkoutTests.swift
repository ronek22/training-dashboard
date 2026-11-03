import Foundation
import Testing
@testable import TrainLog

/// Serial: the stub's answers are shared.
@Suite(.serialized)
@MainActor
struct StaleWorkoutTests {
    /// Answers each path with a set status and body; anything else is a 500.
    final class Stub: URLProtocol, @unchecked Sendable {
        nonisolated(unsafe) static var answers: [String: (Int, String)] = [:]
        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func startLoading() {
            let (status, body) = Self.answers[request.url?.path ?? ""] ?? (500, "{}")
            client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!,
                                cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(body.utf8))
            client?.urlProtocolDidFinishLoading(self)
        }
        override func stopLoading() {}
    }

    private func client() -> APIClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [Stub.self]
        var api = APIClient(baseURL: "http://test.local", reachability: Reachability())
        api.session = URLSession(configuration: config)
        return api
    }

    private func storeWithOpenWorkout() -> SessionStore {
        let store = SessionStore(file: FileManager.default.temporaryDirectory.appending(path: "stale-\(UUID().uuidString).json"))
        store.save(StrengthSession(id: 47, templateId: 5, templateName: "Workout D", status: "active", startedAt: "2026-11-01T18:00:00",
                                   completedAt: nil, currentExerciseOrder: 1, currentSetOrder: 1, exercises: []))
        return store
    }

    @Test func workoutDeletedOnTheWebIsDroppedFromThePhone() async {
        Stub.answers = ["/strength/workouts/sessions/active": (200, "null"), "/strength/workouts/sessions/47": (404, "{}")]
        let store = storeWithOpenWorkout()
        #expect(await TodayModel.activeWorkout(client(), store: store) == nil)
        #expect(store.load() == nil)
    }

    @Test func serverHiccupKeepsTheLocalWorkout() async {
        // A 500 says nothing about the workout: keep it.
        Stub.answers = ["/strength/workouts/sessions/active": (200, "null")]
        let store = storeWithOpenWorkout()
        _ = await TodayModel.activeWorkout(client(), store: store)
        #expect(store.load()?.id == 47)
        store.clear()
    }
}
