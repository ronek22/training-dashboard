import Foundation
import Network
import Observation

/// Settings: the home and anywhere server addresses, which one is in use, and whether each answers.
@MainActor
@Observable
final class SettingsModel {
    enum Status: Equatable {
        case checking
        case online(ms: Int)
        case offline
    }

    private(set) var home: String
    private(set) var remote: String?
    private(set) var activeKind: ServerRoute.Kind
    private(set) var homeStatus: Status = .checking
    private(set) var remoteStatus: Status = .checking

    private let route: ServerRoute

    init(route: ServerRoute = .shared) {
        self.route = route
        home = route.home
        remote = route.remote
        activeKind = route.activeKind
    }

    /// Pings both addresses and switches to the one that answers.
    func check() async {
        homeStatus = .checking
        remoteStatus = remote == nil ? .offline : .checking
        let result = await route.resolve()
        homeStatus = result.home.map { .online(ms: $0) } ?? .offline
        remoteStatus = result.remote.map { .online(ms: $0) } ?? .offline
        activeKind = route.activeKind
        if result.home != nil || result.remote != nil { Reachability.shared.retry() }
    }

    func useHome(_ url: String) async {
        route.setHome(url)
        home = route.home
        await check()
    }

    /// nil removes the anywhere address.
    func useRemote(_ url: String?) async {
        route.setRemote(url)
        remote = route.remote
        await check()
    }
}

enum ServerAddress {
    static let defaultPort = 8000

    /// Turns what was typed ("192.168.1.24", "mac.local:9000", "https://mac.ts.net") into a base URL.
    /// A bare host gets http:// and the backend's port; nil when there's no usable host.
    static func normalize(_ input: String) -> String? {
        var text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        while text.hasSuffix("/") { text.removeLast() }
        guard !text.isEmpty, !text.contains(" ") else { return nil }
        let hasScheme = text.contains("://")
        if !hasScheme { text = "http://" + text }
        guard var components = URLComponents(string: text),
              let scheme = components.scheme?.lowercased(), ["http", "https"].contains(scheme),
              let host = components.host, !host.isEmpty,
              components.path.isEmpty, components.query == nil else { return nil }
        components.scheme = scheme
        if !hasScheme && components.port == nil { components.port = defaultPort }
        return components.string
    }

    /// "TrainLog on MacBook Pro Jakub" for a Bonjour name, "this Mac" for the Simulator's localhost.
    static func displayName(_ baseURL: String) -> String {
        guard let host = URLComponents(string: baseURL)?.host else { return "TrainLog server" }
        let lower = host.lowercased()
        if lower == "localhost" || lower == "127.0.0.1" { return "TrainLog on this Mac" }
        if lower.hasSuffix(".local") {
            return "TrainLog on " + host.dropLast(".local".count).replacingOccurrences(of: "-", with: " ")
        }
        if lower.hasSuffix(".ts.net") { return "TrainLog over Tailscale" }
        return "TrainLog server"
    }

    /// The Mac's `.local` host name as macOS derives it from the computer name:
    /// "Jakub’s MacBook Pro" → "Jakubs-MacBook-Pro.local".
    static func localHost(forComputerName name: String) -> String? {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-"))
        let hyphenated = name.replacingOccurrences(of: " ", with: "-")
        let cleaned = String(String.UnicodeScalarView(hyphenated.unicodeScalars.filter { $0.isASCII && allowed.contains($0) }))
        return cleaned.isEmpty ? nil : cleaned + ".local"
    }

    /// Round trip to the backend's `/health` in milliseconds, or nil when it doesn't answer as TrainLog.
    static func ping(_ baseURL: String, timeout: TimeInterval = 3) async -> Int? {
        guard let url = URL(string: baseURL + "/health") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let clock = ContinuousClock()
        let start = clock.now
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200,
              let body = try? JSONDecoder().decode([String: String].self, from: data),
              body["status"] == "ok" else { return nil }
        let elapsed = clock.now - start
        return Int(elapsed.components.seconds * 1000 + elapsed.components.attoseconds / 1_000_000_000_000_000)
    }
}

/// "Find on this Wi-Fi": the backend runs in Docker and can't advertise itself, so this browses
/// services every Mac publishes, turns each computer name into its `.local` host and asks it for
/// TrainLog's `/health` on port 8000.
@MainActor
@Observable
final class ServerFinder {
    struct Found: Identifiable, Equatable {
        var id: String { url }
        let url: String
        let ms: Int
    }

    /// Service types Macs commonly publish; listed under NSBonjourServices in Info.plist.
    nonisolated static let serviceTypes = ["_companion-link._tcp", "_airplay._tcp", "_ssh._tcp", "_smb._tcp", "_rfb._tcp"]

    private(set) var found: [Found] = []
    private(set) var searching = false
    private var browsers: [NWBrowser] = []
    private var probed: Set<String> = []

    func start() {
        stop()
        found = []
        probed = []
        searching = true
        // The built-in address is worth a try even if the Mac publishes nothing.
        probe(APIClient.defaultBaseURL)
        for type in Self.serviceTypes {
            let browser = NWBrowser(for: .bonjour(type: type, domain: "local."), using: .tcp)
            browser.browseResultsChangedHandler = { [weak self] results, _ in
                let names = results.compactMap { result -> String? in
                    if case let .service(name, _, _, _) = result.endpoint { return name }
                    return nil
                }
                Task { @MainActor in
                    for name in names {
                        if let host = ServerAddress.localHost(forComputerName: name) {
                            self?.probe("http://\(host):\(ServerAddress.defaultPort)")
                        }
                    }
                }
            }
            browser.start(queue: .main)
            browsers.append(browser)
        }
        Task {
            try? await Task.sleep(for: .seconds(8))
            searching = false
        }
    }

    func stop() {
        browsers.forEach { $0.cancel() }
        browsers = []
        searching = false
    }

    private func probe(_ url: String) {
        guard probed.insert(url.lowercased()).inserted else { return }
        Task {
            if let ms = await ServerAddress.ping(url) {
                found.append(Found(url: url, ms: ms))
            }
        }
    }
}
