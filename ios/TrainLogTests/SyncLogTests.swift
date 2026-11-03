import Foundation
import Testing
@testable import TrainLog

/// Serial: the stub's status table is shared.
@Suite(.serialized)
struct SyncLogTests {
    /// Answers 200, or the status set for a path.
    final class Stub: URLProtocol, @unchecked Sendable {
        nonisolated(unsafe) static var statuses: [String: Int] = [:]
        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func startLoading() {
            let status = Self.statuses[request.url?.path ?? ""] ?? 200
            client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data("{}".utf8))
            client?.urlProtocolDidFinishLoading(self)
        }
        override func stopLoading() {}
    }

    private func stubbedClient() -> APIClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [Stub.self]
        var api = APIClient(baseURL: "http://test.local", reachability: Reachability())
        api.session = URLSession(configuration: config)
        return api
    }

    private func tempQueue() -> WriteQueue {
        WriteQueue(file: FileManager.default.temporaryDirectory.appending(path: "sync-\(UUID().uuidString).json"))
    }

    @Test func appendStampsWhenAWriteWasQueued() throws {
        let queue = tempQueue()
        let before = Date.now
        queue.append(.init(method: "POST", path: "/checkins", body: nil))
        let stamp = try #require(queue.pending.first?.queuedAt)
        #expect(stamp >= before)
        try? FileManager.default.removeItem(at: queue.file)
    }

    @Test func writesQueuedBeforeTheStampStillDecode() throws {
        let queue = tempQueue()
        try Data(#"[{"method":"POST","path":"/metrics"}]"#.utf8).write(to: queue.file)
        #expect(queue.pending.map(\.path) == ["/metrics"])
        #expect(queue.pending.first?.queuedAt == nil)
        try? FileManager.default.removeItem(at: queue.file)
    }

    @Test func queueSurvivesARelaunch() throws {
        let queue = tempQueue()
        queue.append(.init(method: "POST", path: "/checkins", body: Data("{}".utf8)))
        // A new instance on the same file, as after the app was killed.
        let reopened = WriteQueue(file: queue.file)
        #expect(reopened.pending.map(\.path) == ["/checkins"])
        #expect(reopened.pending.first?.body == Data("{}".utf8))
        try? FileManager.default.removeItem(at: queue.file)
    }

    @Test func unreadableQueueIsSetAsideNotOverwritten() throws {
        let queue = tempQueue()
        let garbage = Data("[{\"method\":".utf8)
        try garbage.write(to: queue.file)

        #expect(queue.pending.isEmpty)
        queue.append(.init(method: "POST", path: "/checkins", body: nil))
        #expect(queue.pending.map(\.path) == ["/checkins"])

        let dir = queue.file.deletingLastPathComponent()
        let stem = queue.file.deletingPathExtension().lastPathComponent
        let aside = try FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
            .filter { $0.lastPathComponent.hasPrefix(stem + ".unreadable-") }
        #expect(aside.count == 1)
        #expect(try aside.first.map { try Data(contentsOf: $0) } == garbage)
        aside.forEach { try? FileManager.default.removeItem(at: $0) }
        try? FileManager.default.removeItem(at: queue.file)
    }

    @Test func flushLogsSentAndRefusedWritesNewestFirst() async {
        Stub.statuses = ["/strength/workouts/sessions/4/sets/9/complete": 409]
        let queue = tempQueue()
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/4/sets/9/complete", body: nil))
        queue.append(.init(method: "POST", path: "/checkins", body: nil))

        #expect(await queue.flush(with: stubbedClient()))
        #expect(queue.pending.isEmpty)
        #expect(queue.log.map(\.path) == ["/checkins", "/strength/workouts/sessions/4/sets/9/complete"])
        #expect(queue.log.map(\.rejected) == [nil, 409])
        Stub.statuses = [:]
        try? FileManager.default.removeItem(at: queue.file)
        try? FileManager.default.removeItem(at: queue.logFile)
    }

    @Test func secondEndOfAWorkoutIsNotARefusal() async {
        Stub.statuses = ["/strength/workouts/sessions/4/abandon": 404]
        let queue = tempQueue()
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/4/abandon", body: nil))

        #expect(await queue.flush(with: stubbedClient()))
        #expect(queue.log.map(\.rejected) == [nil])
        Stub.statuses = [:]
        try? FileManager.default.removeItem(at: queue.file)
        try? FileManager.default.removeItem(at: queue.logFile)
    }

    @Test func logKeepsOnlyTheLatest() async {
        Stub.statuses = [:]
        let queue = tempQueue()
        for index in 0..<(WriteQueue.logLimit + 5) {
            queue.append(.init(method: "POST", path: "/w/\(index)", body: nil))
        }
        await queue.flush(with: stubbedClient())
        #expect(queue.log.count == WriteQueue.logLimit)
        #expect(queue.log.first?.path == "/w/\(WriteQueue.logLimit + 4)")
        try? FileManager.default.removeItem(at: queue.logFile)
    }

    @Test func serverErrorStopsTheFlushAndKeepsTheRestInOrder() async {
        // A 5xx may pass (a restart, a deploy): keep the write and everything after it, in order.
        Stub.statuses = ["/strength/workouts/sessions/4/sets/10/complete": 500]
        let queue = tempQueue()
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/4/sets/9/complete", body: nil))
        queue.append(.init(method: "POST", path: "/strength/workouts/sessions/4/sets/10/complete", body: nil))
        queue.append(.init(method: "PUT", path: "/strength/workouts/sessions/4/sets/10/effort", body: nil))

        #expect(await queue.flush(with: stubbedClient()) == false)
        #expect(queue.pending.map(\.path) == ["/strength/workouts/sessions/4/sets/10/complete", "/strength/workouts/sessions/4/sets/10/effort"])
        #expect(queue.log.map(\.path) == ["/strength/workouts/sessions/4/sets/9/complete"])

        // Back up: the rest goes out in the order it was logged.
        Stub.statuses = [:]
        #expect(await queue.flush(with: stubbedClient()))
        #expect(queue.pending.isEmpty)
        #expect(queue.log.map(\.path).prefix(2) == ["/strength/workouts/sessions/4/sets/10/effort", "/strength/workouts/sessions/4/sets/10/complete"])
        try? FileManager.default.removeItem(at: queue.file)
        try? FileManager.default.removeItem(at: queue.logFile)
    }

    @Test func unreachableFlushKeepsWritesAndLogsNothing() async {
        let queue = tempQueue()
        queue.append(.init(method: "POST", path: "/checkins", body: nil))
        // Nothing listens on port 9.
        #expect(await queue.flush(with: APIClient(baseURL: "http://127.0.0.1:9", reachability: Reachability())) == false)
        #expect(queue.pending.count == 1)
        #expect(queue.log.isEmpty)
        try? FileManager.default.removeItem(at: queue.file)
    }

    @MainActor @Test func statusCountsRefusalsUntilSeen() async throws {
        Stub.statuses = ["/metrics": 422]
        let queue = tempQueue()
        let defaults = try #require(UserDefaults(suiteName: "sync-\(UUID().uuidString)"))
        let status = SyncStatus(queue: queue, defaults: defaults)
        queue.append(.init(method: "POST", path: "/metrics", body: nil))
        queue.append(.init(method: "POST", path: "/checkins", body: nil))
        status.refresh()
        #expect(status.pending.count == 2)

        await status.sendNow(with: stubbedClient())
        #expect(status.pending.isEmpty)
        #expect(status.unseenRejections == 1)
        status.markSeen()
        #expect(status.unseenRejections == 0)
        Stub.statuses = [:]
        try? FileManager.default.removeItem(at: queue.logFile)
    }

    @Test func labelsNameWhatWasLogged() {
        #expect(SyncFormat.label(method: "POST", path: "/strength/workouts/sessions/4/sets/9/complete") == "Strength set")
        #expect(SyncFormat.label(method: "PUT", path: "/strength/workouts/sessions/4/sets/9/effort") == "Set effort")
        #expect(SyncFormat.label(method: "POST", path: "/nutrition/food/entries") == "Meal")
        #expect(SyncFormat.label(method: "PUT", path: "/nutrition/food/entries/12") == "Meal edit")
        #expect(SyncFormat.label(method: "PUT", path: "/recovery/issues/2/ticks") == "Rehab ticks")
        #expect(SyncFormat.label(method: "POST", path: "/recovery/issues/2/checkins") == "Rehab check-in")
        #expect(SyncFormat.label(method: "POST", path: "/checkins") == "Check-in")
        #expect(SyncFormat.label(method: "PUT", path: "/life-load/2026-10-31") == "Busy day")
        #expect(SyncFormat.label(method: "POST", path: "/strength/workouts/templates") == "New workout")
        #expect(SyncFormat.label(method: "POST", path: "/something/new") == "New")
    }

    @Test func repeatedWritesFoldIntoOneRow() {
        let set = WriteQueue.Write(method: "POST", path: "/strength/workouts/sessions/4/sets/1/complete", body: nil, queuedAt: Date(timeIntervalSince1970: 100))
        let rows = SyncFormat.grouped([set, set, set, .init(method: "POST", path: "/checkins", body: nil)])
        #expect(rows.map(\.label) == ["Strength set", "Check-in"])
        #expect(rows.map(\.count) == [3, 1])
        #expect(rows.first?.since == Date(timeIntervalSince1970: 100))
    }

    @Test func whenReadsTimeTodayAndDayEarlier() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try #require(TimeZone(identifier: "Europe/Warsaw"))
        let now = try #require(calendar.date(from: DateComponents(year: 2026, month: 10, day: 31, hour: 18)))
        let earlier = now.addingTimeInterval(-3600)
        #expect(SyncFormat.when(earlier, now: now, calendar: calendar) == earlier.formatted(date: .omitted, time: .shortened))
        let old = now.addingTimeInterval(-20 * 86400)
        #expect(SyncFormat.when(old, now: now, calendar: calendar) == old.formatted(.dateTime.day().month(.abbreviated)))
    }
}
