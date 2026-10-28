import Foundation
import Testing
@testable import TrainLog

/// Answers requests by host: `up.test` hosts return `{"ok": true}`, others fail as an unknown host.
/// `slow.test` times out instead, as a request that might have reached the server.
final class StubHosts: URLProtocol {
    nonisolated(unsafe) static var hits: [String] = []

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let url = request.url!
        Self.hits.append("\(request.httpMethod ?? "GET") \(url.host()!)")
        if url.host()!.hasSuffix("up.test") {
            let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(#"{"ok": true}"#.utf8))
            client?.urlProtocolDidFinishLoading(self)
        } else {
            let code: URLError.Code = url.host() == "slow.test" ? .timedOut : .cannotFindHost
            client?.urlProtocol(self, didFailWithError: URLError(code))
        }
    }

    override func stopLoading() {}

    static var session: URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubHosts.self]
        return URLSession(configuration: config)
    }
}

@Suite(.serialized)
struct ServerRouteTests {
    private func route(home: String, remote: String?, answering: Set<String>) -> ServerRoute {
        let defaults = UserDefaults(suiteName: "route-\(UUID().uuidString)")!
        let route = ServerRoute(defaults: defaults) { url in answering.contains(url) ? 20 : nil }
        route.setHome(home)
        route.setRemote(remote)
        return route
    }

    @Test func startsAtHomeAndPrefersItWhenBothAnswer() async {
        let route = route(home: "http://mac.local:8000", remote: "https://mac.ts.net", answering: ["http://mac.local:8000", "https://mac.ts.net"])
        #expect(route.active == "http://mac.local:8000")
        let result = await route.resolve()
        #expect(result.home == 20 && result.remote == 20)
        #expect(route.activeKind == .home)
    }

    @Test func resolveSwitchesToTailscaleAwayFromHome() async {
        let route = route(home: "http://mac.local:8000", remote: "https://mac.ts.net", answering: ["https://mac.ts.net"])
        await route.resolve()
        #expect(route.active == "https://mac.ts.net")
        #expect(route.activeKind == .remote)
    }

    @Test func failoverOnlyMovesToAnAddressThatAnswers() async {
        let route = route(home: "http://mac.local:8000", remote: "https://mac.ts.net", answering: [])
        #expect(await route.failover(from: "http://mac.local:8000") == nil)
        #expect(route.activeKind == .home)

        let noRemote = self.route(home: "http://mac.local:8000", remote: nil, answering: ["http://mac.local:8000"])
        #expect(await noRemote.failover(from: "http://mac.local:8000") == nil)
    }

    @Test func removedOrChangedRemoteFallsBackToHome() {
        let route = route(home: "http://mac.local:8000", remote: "https://mac.ts.net", answering: [])
        route.use("https://mac.ts.net")
        #expect(route.activeKind == .remote)
        route.setRemote(nil)
        #expect(route.remote == nil)
        #expect(route.active == "http://mac.local:8000")
    }

    @Test func requestRetriesOnTheOtherAddress() async throws {
        let route = route(home: "http://home.test", remote: "https://up.test", answering: ["https://up.test"])
        let api = APIClient(baseURL: route.home, session: StubHosts.session, reachability: Reachability(), route: route)
        StubHosts.hits = []
        let data = try await api.send("POST", "/checkins")
        #expect(String(decoding: data, as: UTF8.self).contains("ok"))
        #expect(StubHosts.hits == ["POST home.test", "POST up.test"])
        #expect(route.active == "https://up.test")
        #expect(!api.reachability.knownOffline)
    }

    @Test func writeThatMayHaveArrivedIsNotSentTwice() async {
        let route = route(home: "http://slow.test", remote: "https://up.test", answering: ["https://up.test"])
        let api = APIClient(baseURL: route.home, session: StubHosts.session, reachability: Reachability(), route: route)
        StubHosts.hits = []
        await #expect(throws: APIError.self) { try await api.send("POST", "/checkins") }
        #expect(StubHosts.hits == ["POST slow.test"])
        #expect(api.reachability.knownOffline)
    }
}
