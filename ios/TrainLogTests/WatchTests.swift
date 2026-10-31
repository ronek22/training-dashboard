import Foundation
import Testing
@testable import TrainLog

/// The Watch app's pure rules (TrainLogWatch/Logic, compiled into this target) and the phone's relay.
@Suite(.serialized)
struct WatchTests {
    private func set(_ id: Int, order: Int, reps: Int = 10, kg: Double? = 30, rest: Int = 90, done: Bool = false,
                     type: String = "working", seconds: Int? = nil, actualKg: Double? = nil) -> StrengthSession.WorkoutSet {
        StrengthSession.WorkoutSet(
            id: id, setOrder: order, targetReps: reps, targetWeightKg: kg, restSeconds: rest,
            actualReps: done ? reps : nil, actualWeightKg: done ? actualKg ?? kg : nil,
            status: done ? "completed" : "pending", setType: type, effort: nil, targetSeconds: seconds
        )
    }

    private func session() -> StrengthSession {
        StrengthSession(
            id: 4, templateId: 3, templateName: "Workout B", status: "active", startedAt: "2026-10-31T19:00:00",
            completedAt: nil, currentExerciseOrder: 2, currentSetOrder: 1,
            exercises: [
                .init(id: 1, exerciseOrder: 1, exerciseName: "Lat Pulldown", notes: nil, sets: [
                    set(10, order: 1, kg: 20, rest: 60, done: true, type: "warmup"),
                    set(11, order: 2, kg: 50, done: true, actualKg: 52),
                    set(12, order: 3, kg: 50, done: true),
                ]),
                .init(id: 2, exerciseOrder: 2, exerciseName: "Dumbbell Row", notes: nil, sets: [
                    set(20, order: 1, kg: 34),
                    set(21, order: 2, kg: 34),
                ]),
                .init(id: 3, exerciseOrder: 3, exerciseName: "Plank", notes: nil, sets: [
                    set(30, order: 1, reps: 1, kg: nil, rest: 30, seconds: 45),
                ]),
            ]
        )
    }

    // MARK: WatchStrength

    @Test func totalsCountWorkingSetsAndVolume() {
        let totals = WatchStrength.totals(session())
        #expect(totals.setsDone == 2)
        #expect(totals.setsTotal == 5)
        // 52 × 10 + 50 × 10; the warm-up is left out.
        #expect(totals.volumeKg == 1020)
    }

    @Test func minutesLeftAddsWorkAndRestButNotTheLastRest() {
        // Rows: 2 × (40 + 90) s, plank 45 s (its 30 s rest dropped) = 305 s ≈ 5 min.
        #expect(WatchStrength.minutesLeft(session()) == 5)
    }

    @Test func kickerCountsWorkingSetsOnly() {
        let session = session()
        let row = session.exercises[1]
        #expect(WatchStrength.kicker(session, exercise: row, set: row.sets[1]) == "Ex 2/3 · Set 2 of 2")
        let pulldown = session.exercises[0]
        #expect(WatchStrength.kicker(session, exercise: pulldown, set: pulldown.sets[0]) == "Ex 1/3 · Warm-up")
    }

    @Test func nextExerciseSkipsDoneOnesAndWraps() {
        let session = session()
        #expect(WatchStrength.nextExercise(after: session.exercises[1], in: session)?.exerciseName == "Plank")
        // From the plank it wraps past the finished pulldown back to the rows.
        #expect(WatchStrength.nextExercise(after: session.exercises[2], in: session)?.exerciseName == "Dumbbell Row")
    }

    @Test func jumpLandsOnFirstSetNotDone() {
        let session = session()
        #expect(WatchStrength.jumpTarget(session.exercises[1]) == 1)
        #expect(WatchStrength.jumpTarget(session.exercises[0]) == 1)
    }

    @Test func versusLastReadsLikeTheArtboard() {
        #expect(WatchStrength.versusLast(34, last: 33.5) == "+0.5 vs last")
        #expect(WatchStrength.versusLast(10, last: 10) == "same as last")
        #expect(WatchStrength.versusLast(32, last: 34) == "−2 vs last")
        #expect(WatchStrength.versusLast(nil, last: nil) == nil)
    }

    // MARK: Outbox

    private func tempOutbox() -> Outbox {
        Outbox(file: FileManager.default.temporaryDirectory.appending(path: "outbox-\(UUID().uuidString).json"))
    }

    @Test func outboxDeliversInOrderAndStopsAtTheFirstRefusal() async {
        let outbox = tempOutbox()
        for path in ["/a", "/b", "/c"] { outbox.append(.init(method: "POST", path: path)) }
        var delivered: [String] = []
        let left = await outbox.flush { write in
            guard write.path != "/b" else { return false }
            delivered.append(write.path)
            return true
        }
        #expect(delivered == ["/a"])
        #expect(left == 2)
        #expect(outbox.pending.map(\.path) == ["/b", "/c"])

        await outbox.flush { _ in true }
        #expect(outbox.pending.isEmpty)
        #expect(!FileManager.default.fileExists(atPath: outbox.file.path))
    }

    @Test func outboxKeepsAWriteAppendedWhileOneIsInFlight() async {
        let outbox = tempOutbox()
        outbox.append(.init(method: "POST", path: "/set"))
        var delivered: [String] = []
        let left = await outbox.flush { write in
            // The effort tap lands while the set is still on its way to the phone.
            if write.path == "/set" { outbox.append(.init(method: "PUT", path: "/effort")) }
            delivered.append(write.path)
            return true
        }
        #expect(delivered == ["/set", "/effort"])
        #expect(left == 0)
    }

    // MARK: Phone relay

    final class Stub: URLProtocol, @unchecked Sendable {
        nonisolated(unsafe) static var statuses: [String: Int] = [:]
        nonisolated(unsafe) static var offline = false
        /// Runs as a request arrives, before it's answered.
        nonisolated(unsafe) static var onLoad: ((String) -> Void)?
        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func startLoading() {
            if Self.offline {
                client?.urlProtocol(self, didFailWithError: URLError(.cannotConnectToHost))
                return
            }
            Self.onLoad?(request.url?.path ?? "")
            let status = Self.statuses[request.url?.path ?? ""] ?? 200
            client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(#"{"ok":true}"#.utf8))
            client?.urlProtocolDidFinishLoading(self)
        }
        override func stopLoading() {}
    }

    private func client() -> APIClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [Stub.self]
        var api = APIClient(baseURL: "http://test.local", reachability: Reachability())
        api.session = URLSession(configuration: config)
        api.cache = ResponseCache(directory: FileManager.default.temporaryDirectory.appending(path: "relay-\(UUID().uuidString)"))
        return api
    }

    private func relay(_ envelope: WatchWire.Envelope, client: APIClient, queue: WriteQueue? = nil) async throws -> WatchWire.Reply {
        let queue = queue ?? WriteQueue(file: FileManager.default.temporaryDirectory.appending(path: "relayq-\(UUID().uuidString).json"))
        let data = await WatchRelay.handle(try JSONEncoder().encode(envelope), client: client, queue: queue)
        return try JSONDecoder().decode(WatchWire.Reply.self, from: data)
    }

    @Test func relayAnswersARequestAndFallsBackToTheCacheOffline() async throws {
        Stub.statuses = [:]
        Stub.offline = false
        let api = client()
        let envelope = WatchWire.Envelope(kind: .request, method: "GET", path: "/phone/today")
        let live = try await relay(envelope, client: api)
        #expect(live.status == 200)
        #expect(live.fromCache == false)

        Stub.offline = true
        let cached = try await relay(envelope, client: api)
        #expect(cached.status == 200)
        #expect(cached.fromCache)
        #expect(cached.data == live.data)
        Stub.offline = false
    }

    @Test func relayPassesServerStatusesThrough() async throws {
        Stub.statuses = ["/strength/workouts/sessions": 409]
        let reply = try await relay(.init(kind: .request, method: "POST", path: "/strength/workouts/sessions"), client: client())
        #expect(reply.status == 409)
        Stub.statuses = [:]
    }

    @Test func relayQueuesWritesWhenTheServerIsAway() async throws {
        Stub.offline = true
        let queue = WriteQueue(file: FileManager.default.temporaryDirectory.appending(path: "relayq-\(UUID().uuidString).json"))
        let reply = try await relay(.init(kind: .write, method: "POST", path: "/strength/workouts/sessions/4/sets/20/complete"),
                                    client: client(), queue: queue)
        #expect(reply.status == 202)
        #expect(queue.pending.map(\.path) == ["/strength/workouts/sessions/4/sets/20/complete"])
        Stub.offline = false
    }

    @Test func phoneQueueKeepsAWriteAppendedWhileOneIsSending() async {
        Stub.offline = false
        Stub.statuses = [:]
        let queue = WriteQueue(file: FileManager.default.temporaryDirectory.appending(path: "relayq-\(UUID().uuidString).json"))
        queue.append(.init(method: "POST", path: "/set/1", body: nil))
        // The Watch's next set arrives while the first is on its way to the server.
        Stub.onLoad = { path in
            if path == "/set/1" { queue.append(.init(method: "POST", path: "/set/2", body: nil)) }
        }
        defer { Stub.onLoad = nil }
        #expect(await queue.flush(with: client()))
        #expect(queue.pending.isEmpty)
        #expect(queue.log.map(\.path) == ["/set/2", "/set/1"])
    }
}
