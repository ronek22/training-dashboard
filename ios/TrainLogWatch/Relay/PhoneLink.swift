import Foundation
import Observation
import WatchConnectivity

enum LinkError: LocalizedError {
    case phoneUnreachable
    case serverUnreachable
    case status(Int)

    var errorDescription: String? {
        switch self {
        case .phoneUnreachable: "Can't reach your iPhone. Keep it nearby with Bluetooth on."
        case .serverUnreachable: "Your iPhone can't reach the TrainLog server."
        case .status(let code): "Server answered \(code)."
        }
    }
}

/// The Watch's only way to the server: every call goes through the iPhone app
/// (`TrainLog/Watch/WatchRelay.swift`). Reads need the phone in reach; writes go to the `Outbox`
/// first and are handed over in order whenever the phone is reachable.
@MainActor
@Observable
final class PhoneLink: NSObject {
    static let shared = PhoneLink()

    private(set) var reachable = false
    /// Writes the phone hasn't taken yet.
    private(set) var pendingWrites = 0

    private let outbox = Outbox()
    private var flushing = false
    private var activation: [CheckedContinuation<Void, Never>] = []
    private var activated = false

    func activate() {
        guard WCSession.isSupported() else { return }
        pendingWrites = outbox.pending.count
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    /// One server call made by the phone; the reply's data, or the reason there isn't any.
    func request(_ method: String, _ path: String, body: Data? = nil) async throws -> (data: Data, fromCache: Bool) {
        await waitForActivation()
        let envelope = WatchWire.Envelope(kind: .request, method: method, path: path, body: body)
        let reply = try await send(envelope)
        guard let status = reply.status else { throw LinkError.serverUnreachable }
        guard (200..<300).contains(status) else { throw LinkError.status(status) }
        return (reply.data ?? Data(), reply.fromCache)
    }

    /// What the phone has open (its pending workout, rehab step or strength session), asked over
    /// WatchConnectivity: works before the mirrored workout links. Nil when the phone is out of reach.
    func leading() async -> WatchWire.Live? {
        await waitForActivation()
        guard let reply = try? await send(WatchWire.Envelope(kind: .leading, method: "GET", path: "")),
              let data = reply.data
        else { return nil }
        return try? JSONDecoder().decode(WatchWire.Live.self, from: data)
    }

    /// A button pressed here, for the phone (Start on the ready screen; rehab steering without the
    /// mirrored link).
    func command(_ command: WatchWire.Command) {
        Task { _ = try? await send(WatchWire.Envelope(kind: .command, method: "POST", path: command.rawValue)) }
    }

    /// A step of linking up, for the phone's link log (Settings). Dropped when the phone is away.
    func event(_ text: String) {
        #if DEBUG
        if WatchDemo.enabled { return }
        #endif
        Task { _ = try? await send(WatchWire.Envelope(kind: .event, method: "POST", path: text)) }
    }

    /// Queues a write and hands it over as soon as possible. Never fails: it waits in the outbox.
    func enqueue(_ method: String, _ path: String, body: Data? = nil) {
        #if DEBUG
        if WatchDemo.enabled { return }
        #endif
        outbox.append(.init(method: method, path: path, body: body))
        pendingWrites = outbox.pending.count
        Task { await flush() }
    }

    func flush() async {
        guard !flushing else { return }
        flushing = true
        defer { flushing = false }
        await waitForActivation()
        pendingWrites = await outbox.flush { [weak self] write in
            guard let self else { return false }
            let envelope = WatchWire.Envelope(kind: .write, method: write.method, path: write.path, body: write.body)
            // The phone answers once the write is on its own queue.
            return (try? await self.send(envelope)) != nil
        }
    }

    private func send(_ envelope: WatchWire.Envelope) async throws -> WatchWire.Reply {
        let session = WCSession.default
        // Reachability settles a moment after launch (and after the phone wakes); give it a few seconds.
        for _ in 0..<12 where !(session.activationState == .activated && session.isReachable) {
            try? await Task.sleep(for: .milliseconds(250))
        }
        guard session.activationState == .activated, session.isReachable else { throw LinkError.phoneUnreachable }
        let message = try JSONEncoder().encode(envelope)
        let data: Data = try await withCheckedThrowingContinuation { continuation in
            // Called on a WatchConnectivity queue, not the main actor.
            session.sendMessageData(message, replyHandler: { @Sendable data in continuation.resume(returning: data) },
                                    errorHandler: { @Sendable _ in continuation.resume(throwing: LinkError.phoneUnreachable) })
        }
        return try JSONDecoder().decode(WatchWire.Reply.self, from: data)
    }

    private func waitForActivation() async {
        guard !activated, WCSession.isSupported() else { return }
        await withCheckedContinuation { activation.append($0) }
    }

    fileprivate func didActivate() {
        activated = true
        reachable = WCSession.default.isReachable
        activation.forEach { $0.resume() }
        activation = []
        Task { await flush() }
    }

    fileprivate func reachabilityChanged(_ isReachable: Bool) {
        reachable = isReachable
        if isReachable { Task { await flush() } }
    }
}

extension PhoneLink: WCSessionDelegate {
    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        // The phone's latest widget snapshot, left as the application context while TrainLog slept.
        storeWidgetSnapshot(session.receivedApplicationContext)
        Task { @MainActor in PhoneLink.shared.didActivate() }
    }

    /// From a face with a TrainLog widget (`transferCurrentComplicationUserInfo`).
    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        storeWidgetSnapshot(userInfo)
    }

    nonisolated func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
        storeWidgetSnapshot(applicationContext)
    }

    /// For the Watch widgets (TrainLogWatchWidgets), which read it from the App Group.
    private nonisolated func storeWidgetSnapshot(_ payload: [String: Any]) {
        guard let data = payload[WatchWire.widgetSnapshotKey] as? Data else { return }
        WidgetStore.store(data)
    }

    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        let isReachable = session.isReachable
        Task { @MainActor in PhoneLink.shared.reachabilityChanged(isReachable) }
    }
}

/// Typed calls over the link, plus a Watch-side copy of the last good read so the start screen
/// draws with the phone out of reach.
@MainActor
enum WatchAPI {
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    struct Loaded<Value: Sendable>: Sendable {
        let value: Value
        /// From a cache (the phone's or the Watch's), not the server just now.
        let stale: Bool
    }

    static func get<T: Decodable & Sendable>(_ path: String, as type: T.Type = T.self, link: PhoneLink = .shared) async throws -> Loaded<T> {
        do {
            let (data, fromCache) = try await link.request("GET", path)
            let value = try decoder.decode(T.self, from: data)
            cache.store(data, for: path)
            return Loaded(value: value, stale: fromCache)
        } catch let error as DecodingError {
            throw error
        } catch {
            guard let data = cache.load(path), let value = try? decoder.decode(T.self, from: data) else { throw error }
            return Loaded(value: value, stale: true)
        }
    }

    static func send<T: Decodable>(_ method: String, _ path: String, body: Data? = nil, as type: T.Type, link: PhoneLink = .shared) async throws -> T {
        try decoder.decode(T.self, from: try await link.request(method, path, body: body).data)
    }

    private static let cache = WatchCache()
}

struct WatchCache: Sendable {
    var directory: URL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        .appending(path: "api", directoryHint: .isDirectory)

    func store(_ data: Data, for path: String) {
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try? data.write(to: file(for: path), options: .atomic)
    }

    func load(_ path: String) -> Data? {
        try? Data(contentsOf: file(for: path))
    }

    private func file(for path: String) -> URL {
        directory.appending(path: path.replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "?", with: "_") + ".json")
    }
}

extension JSONDecoder {
    /// Backend JSON is snake_case.
    static var snakeCase: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}

extension JSONEncoder {
    static var snakeCase: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}
