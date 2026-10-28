import Foundation
import Testing
@testable import TrainLog

struct OfflineTests {
    @Test func servesCacheAndSkipsNetworkOnceOffline() async throws {
        let dir = FileManager.default.temporaryDirectory.appending(path: "cache-\(UUID().uuidString)", directoryHint: .isDirectory)
        let reachability = Reachability()
        // Nothing listens on port 9.
        let api = APIClient(baseURL: "http://127.0.0.1:9", cache: ResponseCache(directory: dir), reachability: reachability)
        api.cache.store(Data("[1, 2]".utf8), for: "/numbers")

        #expect(api.cached("/numbers", as: [Int].self)?.value == [1, 2])
        #expect(api.cached("/missing", as: [Int].self) == nil)

        let first = try await api.get("/numbers", as: [Int].self)
        #expect(first.fromCache)
        #expect(reachability.knownOffline)

        // Known offline: answers from the cache without waiting on the network.
        let clock = ContinuousClock()
        let start = clock.now
        let second = try await api.get("/numbers", as: [Int].self)
        #expect(second.value == [1, 2])
        #expect(clock.now - start < .milliseconds(100))

        reachability.retry()
        #expect(!reachability.knownOffline)
        try? FileManager.default.removeItem(at: dir)
    }
}
