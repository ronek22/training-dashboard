import Foundation
import Observation
import WatchConnectivity
import os

private let logger = Logger(subsystem: "com.ronek22.trainlog.watchkitapp", category: "phone-link")

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
/// first and are handed over in order: as a message when the phone is in reach, otherwise as a
/// queued user-info transfer that the system delivers later.
@MainActor
@Observable
final class PhoneLink: NSObject {
    static let shared = PhoneLink()

    private(set) var reachable = false
    /// Writes the phone hasn't taken yet: in the outbox, or in a transfer still on its way.
    private(set) var pendingWrites = 0

    private let outbox = Outbox()
    private var flushing = false
    private var activation: [CheckedContinuation<Void, Never>] = []
    private var activated = false

    func activate() {
        guard WCSession.isSupported() else { return }
        pendingWrites = waiting
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
        pendingWrites = waiting
        Task { await flush() }
    }

    func flush() async {
        guard !flushing else { return }
        flushing = true
        defer { flushing = false }
        await waitForActivation()
        await outbox.flush { [weak self] write in
            guard let self else { return false }
            return await self.handOver(WatchWire.Envelope(kind: .write, method: write.method, path: write.path, body: write.body))
        }
        pendingWrites = waiting
    }

    private var waiting: Int {
        let session = WCSession.default
        let transfers = session.activationState == .activated ? session.outstandingUserInfoTransfers.count : 0
        return outbox.pending.count + transfers
    }

    /// A transfer reached the phone, or failed; a failed one isn't retried by the system, so its
    /// write goes back in the outbox.
    fileprivate func transferFinished(_ write: Data?, failure: String?) {
        if let failure, let write, let envelope = try? JSONDecoder().decode(WatchWire.Envelope.self, from: write) {
            logger.error("Transfer of \(envelope.path, privacy: .public) failed, back in the outbox: \(failure)")
            outbox.append(.init(method: envelope.method, path: envelope.path, body: envelope.body))
            Task { await flush() }
        }
        pendingWrites = waiting
    }

    /// A message when the phone is in reach (it answers once the write is on its own queue);
    /// otherwise a user-info transfer, which the system keeps and delivers even if this app closes
    /// before the phone is back. While one transfer is still waiting, later writes queue behind it
    /// instead of overtaking it as a message.
    private func handOver(_ envelope: WatchWire.Envelope) async -> Bool {
        let session = WCSession.default
        if session.outstandingUserInfoTransfers.isEmpty, await reachableSoon() {
            return (try? await send(envelope)) != nil
        }
        guard session.activationState == .activated, let data = try? JSONEncoder().encode(envelope) else { return false }
        session.transferUserInfo([WatchWire.writeKey: data])
        logger.info("\(envelope.path, privacy: .public): phone away, handed to a user-info transfer")
        return true
    }

    /// Reachability settles a moment after launch (and after the phone wakes); gives it a few seconds.
    private func reachableSoon() async -> Bool {
        let session = WCSession.default
        for _ in 0..<12 where !(session.activationState == .activated && session.isReachable) {
            try? await Task.sleep(for: .milliseconds(250))
        }
        return session.activationState == .activated && session.isReachable
    }

    private func send(_ envelope: WatchWire.Envelope) async throws -> WatchWire.Reply {
        let session = WCSession.default
        guard await reachableSoon() else {
            logger.info("\(envelope.path, privacy: .public): phone not reachable (activation \(session.activationState.rawValue))")
            throw LinkError.phoneUnreachable
        }
        let message = try JSONEncoder().encode(envelope)
        let data: Data = try await withCheckedThrowingContinuation { continuation in
            // Called on a WatchConnectivity queue, not the main actor.
            session.sendMessageData(message, replyHandler: { @Sendable data in continuation.resume(returning: data) },
                                    errorHandler: { @Sendable error in
                                        logger.notice("Message to the phone failed: \(error)")
                                        continuation.resume(throwing: LinkError.phoneUnreachable)
                                    })
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
        if let error { logger.error("Session activation failed: \(error)") }
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

    nonisolated func session(_ session: WCSession, didFinish userInfoTransfer: WCSessionUserInfoTransfer, error: Error?) {
        let write = userInfoTransfer.userInfo[WatchWire.writeKey] as? Data
        let failure = error.map { String(describing: $0) }
        Task { @MainActor in PhoneLink.shared.transferFinished(write, failure: failure) }
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
