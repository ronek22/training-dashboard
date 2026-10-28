import Foundation
import Network
import Synchronization

/// Which of the two server addresses the app talks to: the home one (`.local` on Wi-Fi) or the
/// anywhere one (Tailscale). Remembers the one that answered last, so a request goes straight to
/// it, and switches when it stops answering or the phone changes network.
final class ServerRoute: Sendable {
    static let shared = ServerRoute()

    static let remoteKey = "serverRemoteURL"
    static let activeKey = "serverActiveURL"
    /// The Mac over Tailscale (`tailscale serve --bg 8000`). The Simulator sits on the Mac itself.
    #if targetEnvironment(simulator)
    static let defaultRemoteURL: String? = nil
    #else
    static let defaultRemoteURL: String? = "https://macbook-pro-jakub.tail57ecb4.ts.net"
    #endif

    enum Kind: Equatable { case home, remote }

    /// UserDefaults is thread-safe; the SDK just doesn't mark it Sendable.
    nonisolated(unsafe) private let defaults: UserDefaults
    private let ping: @Sendable (String) async -> Int?
    private let monitor = Mutex<NWPathMonitor?>(nil)

    init(defaults: UserDefaults = .standard, ping: @escaping @Sendable (String) async -> Int? = { await ServerAddress.ping($0) }) {
        self.defaults = defaults
        self.ping = ping
    }

    var home: String { defaults.string(forKey: APIClient.baseURLKey) ?? APIClient.defaultBaseURL }

    /// nil when there's no anywhere address; an empty stored value means it was removed in Settings.
    var remote: String? {
        guard let stored = defaults.string(forKey: Self.remoteKey) else { return Self.defaultRemoteURL }
        return stored.isEmpty ? nil : stored
    }

    /// The address that answered last; home until something else has.
    var active: String {
        let stored = defaults.string(forKey: Self.activeKey)
        return stored == remote && remote != nil ? stored! : home
    }

    var activeKind: Kind { active == home ? .home : .remote }

    func setHome(_ url: String) {
        if url == APIClient.defaultBaseURL {
            defaults.removeObject(forKey: APIClient.baseURLKey)
        } else {
            defaults.set(url, forKey: APIClient.baseURLKey)
        }
    }

    func setRemote(_ url: String?) {
        if url == Self.defaultRemoteURL {
            defaults.removeObject(forKey: Self.remoteKey)
        } else {
            defaults.set(url ?? "", forKey: Self.remoteKey)
        }
    }

    func use(_ url: String) { defaults.set(url, forKey: Self.activeKey) }

    /// After `failed` stopped answering: the other address, if it answers now (and is then used).
    func failover(from failed: String) async -> String? {
        let other = failed == home ? remote : home
        guard let other, other != failed, await ping(other) != nil else { return nil }
        use(other)
        return other
    }

    /// Asks both addresses at once and uses the one that answers, home first when both do (no
    /// tunnel on the way). Returns each one's round trip for Settings.
    @discardableResult
    func resolve() async -> (home: Int?, remote: Int?) {
        let home = home, remote = remote
        async let homeMs = ping(home)
        async let remoteMs = pingIfSet(remote)
        let result = await (home: homeMs, remote: remoteMs)
        if result.home != nil {
            use(home)
        } else if let remote, result.remote != nil {
            use(remote)
        }
        return result
    }

    private func pingIfSet(_ url: String?) async -> Int? {
        guard let url else { return nil }
        return await ping(url)
    }

    /// Re-picks the address whenever the phone joins or leaves a network (home Wi-Fi ↔ cellular,
    /// Tailscale up or down), before a screen has to wait out a timeout on the old one.
    func watchNetwork() {
        monitor.withLock { monitor in
            guard monitor == nil else { return }
            let pathMonitor = NWPathMonitor()
            pathMonitor.pathUpdateHandler = { [weak self] path in
                guard path.status == .satisfied else { return }
                Task {
                    await self?.resolve()
                    Reachability.shared.retry()
                }
            }
            pathMonitor.start(queue: DispatchQueue(label: "ServerRoute.path"))
            monitor = pathMonitor
        }
    }
}
