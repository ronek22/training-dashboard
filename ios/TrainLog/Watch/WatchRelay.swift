import Foundation
import WatchConnectivity
import os

private let logger = Logger(subsystem: "com.ronek22.trainlog", category: "watch-relay")

/// The iPhone side of the Watch app: makes the Watch's server calls with the phone's own
/// `APIClient` (address, failover, cache) and puts its writes on the phone's `WriteQueue`, so a set
/// logged on the wrist is replayed exactly like one logged here. Woken in the background when the
/// Watch sends a message.
final class WatchRelay: NSObject, WCSessionDelegate, Sendable {
    static let shared = WatchRelay()

    func activate() {
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
        NotificationCenter.default.addObserver(forName: WidgetStore.didChange, object: nil, queue: nil) { _ in
            WatchRelay.sendWidgetSnapshot()
        }
    }

    /// The Watch widgets draw the phone's widget snapshot (TrainLogWatchWidgets). A face with one
    /// of them gets it right away (about 50 a day); otherwise the latest copy waits as the
    /// application context and arrives when the Watch next wakes TrainLog.
    static func sendWidgetSnapshot() {
        let session = WCSession.default
        guard session.activationState == .activated, session.isPaired, session.isWatchAppInstalled,
              let data = WidgetStore.data()
        else { return }
        let payload: [String: Any] = [WatchWire.widgetSnapshotKey: data]
        if session.isComplicationEnabled, session.remainingComplicationUserInfoTransfers > 0 {
            session.transferCurrentComplicationUserInfo(payload)
        }
        try? session.updateApplicationContext(payload)
    }

    func session(_ session: WCSession, didReceiveMessageData messageData: Data, replyHandler: @escaping (Data) -> Void) {
        let reply = ReplyBox(replyHandler)
        Task {
            let answer = await Self.handle(messageData)
            reply.send(answer)
        }
    }

    /// A write the Watch handed over as a user-info transfer while the phone was out of reach.
    /// Appended here, before this callback returns, so transfers stay in the order they arrive.
    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        guard Self.queueTransfer(userInfo) else { return }
        Task { await WriteQueue().flush(with: .current) }
    }

    /// Puts a transferred write on the queue; false when the payload isn't one.
    @discardableResult
    static func queueTransfer(_ userInfo: [String: Any], queue: WriteQueue = WriteQueue()) -> Bool {
        guard let data = userInfo[WatchWire.writeKey] as? Data,
              let envelope = try? JSONDecoder().decode(WatchWire.Envelope.self, from: data),
              envelope.kind == .write
        else {
            if userInfo[WatchWire.writeKey] != nil { logger.error("Watch transfer didn't decode as a write") }
            return false
        }
        queue.append(.init(method: envelope.method, path: envelope.path, body: envelope.body))
        return true
    }

    /// Decodes one envelope and answers it; never throws, the Watch reads the reply's status.
    static func handle(_ message: Data, client: APIClient = .current, queue: WriteQueue = WriteQueue()) async -> Data {
        let reply: WatchWire.Reply
        if let envelope = try? JSONDecoder().decode(WatchWire.Envelope.self, from: message) {
            switch envelope.kind {
            case .request: reply = await request(envelope, client: client)
            case .write: reply = await write(envelope, client: client, queue: queue)
            case .leading: reply = await MainActor.run { WatchLive.shared.leadingForWatch() }
            case .command:
                await MainActor.run {
                    if let command = WatchWire.Command(rawValue: envelope.path) { WatchLive.shared.received(command) }
                }
                reply = WatchWire.Reply(status: 200)
            case .event:
                await MainActor.run { WatchLinkLog.shared.add("Watch: " + envelope.path) }
                reply = WatchWire.Reply(status: 200)
            }
        } else {
            logger.error("Watch message didn't decode (\(message.count) bytes)")
            reply = WatchWire.Reply(status: 400)
        }
        return (try? JSONEncoder().encode(reply)) ?? Data()
    }

    private static func request(_ envelope: WatchWire.Envelope, client: APIClient) async -> WatchWire.Reply {
        do {
            let data = try await client.send(envelope.method, envelope.path, body: envelope.body)
            if envelope.method == "GET" { client.cache.store(data, for: envelope.path) }
            return WatchWire.Reply(status: 200, data: data)
        } catch APIError.status(let code) {
            return WatchWire.Reply(status: code)
        } catch {
            // Away from the server: a GET gets the phone's last good copy (Today's own cache too).
            if envelope.method == "GET", let cached = client.cache.load(envelope.path) {
                return WatchWire.Reply(status: 200, data: cached.data, fromCache: true)
            }
            logger.notice("Watch \(envelope.method, privacy: .public) \(envelope.path, privacy: .public) failed: \(error)")
            return WatchWire.Reply(status: nil)
        }
    }

    /// Accepted once it's on the queue (it survives the app being killed); sent on from there.
    private static func write(_ envelope: WatchWire.Envelope, client: APIClient, queue: WriteQueue) async -> WatchWire.Reply {
        queue.append(.init(method: envelope.method, path: envelope.path, body: envelope.body))
        await queue.flush(with: client)
        return WatchWire.Reply(status: 202)
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        if let error { logger.error("Watch session activation failed: \(error)") }
        if activationState == .activated { Self.sendWidgetSnapshot() }
    }
    func sessionDidBecomeInactive(_ session: WCSession) {}

    /// After switching to another Watch.
    func sessionDidDeactivate(_ session: WCSession) {
        WCSession.default.activate()
    }
}

/// WatchConnectivity's reply handler isn't marked Sendable; it's safe to call from any thread.
private struct ReplyBox: @unchecked Sendable {
    let handler: (Data) -> Void
    init(_ handler: @escaping (Data) -> Void) { self.handler = handler }
    func send(_ data: Data) { handler(data) }
}
