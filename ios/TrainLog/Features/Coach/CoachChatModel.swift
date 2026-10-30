import Foundation
import Observation

/// One coach chat, shared with the web Coach page. The backend runs each turn through the coach
/// helper on the Mac and saves the reply itself, so closing the sheet mid-reply loses nothing:
/// the job id is remembered and polling resumes when the chat opens again.
@MainActor
@Observable
final class CoachChatModel {
    let context: CoachContext?
    private(set) var conversation: CoachConversation?
    private(set) var messages: [CoachMessage] = []
    /// The message being answered, shown until the server's copy arrives with the reply.
    private(set) var sent: String?
    private(set) var thinkingSince: Date?
    private(set) var status: String?
    private(set) var error: String?
    private(set) var loaded = false
    var draft = ""

    private let client: () -> APIClient
    private let defaults: UserDefaults
    private let pollInterval: Duration

    init(context: CoachContext? = nil, conversation: CoachConversation? = nil,
         client: @escaping () -> APIClient = { .current }, defaults: UserDefaults = .standard,
         pollInterval: Duration = .seconds(2.5)) {
        self.context = context
        self.conversation = conversation
        self.client = client
        self.defaults = defaults
        self.pollInterval = pollInterval
    }

    var thinking: Bool { thinkingSince != nil }
    var canSend: Bool { !thinking && !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    var title: String { conversation?.title ?? context?.title ?? "New chat" }

    static func messagesPath(_ id: Int) -> String { "/notes/chat?conversation_id=\(id)&limit=200" }
    static func pendingKey(_ id: Int) -> String { "coachPendingTurn.\(id)" }

    /// Opens the context's chat (the latest one, or a new empty one) and loads its messages.
    func load() async {
        let api = client()
        do {
            if conversation == nil, let context {
                let body = CoachContextOpen(contextKind: context.kind.rawValue, contextId: context.id, title: context.title)
                conversation = try await api.send("POST", "/notes/chat/conversations/open",
                                                  body: try APIClient.encoder.encode(body), as: CoachConversation.self)
            }
            guard let id = conversation?.id else {
                loaded = true
                return
            }
            if messages.isEmpty, let cached = api.cached(Self.messagesPath(id), as: [CoachMessage].self) {
                messages = cached.value
            }
            messages = try await api.get(Self.messagesPath(id), as: [CoachMessage].self).value
            error = nil
            await markRead()
        } catch {
            if messages.isEmpty { self.error = Self.message(for: error) }
        }
        loaded = true
        if !thinking, let id = conversation?.id, let job = defaults.string(forKey: Self.pendingKey(id)) {
            await follow(job)
        }
    }

    func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard canSend else { return }
        let api = client()
        draft = ""
        sent = text
        error = nil
        thinkingSince = .now
        status = "Sending to the coach…"
        do {
            if conversation == nil {
                // A general chat is created on its first message, so empty ones don't pile up.
                conversation = try await api.send("POST", "/notes/chat/conversations",
                                                  body: try APIClient.encoder.encode(CoachConversationCreate(title: "New conversation")),
                                                  as: CoachConversation.self)
            }
            guard let id = conversation?.id else { return }
            let body = try APIClient.encoder.encode(CoachTurnRequest(conversationId: id, message: text))
            let job = try await api.send("POST", "/notes/chat/phone", body: body, as: CoachTurnJob.self, timeout: 45)
            defaults.set(job.jobId, forKey: Self.pendingKey(id))
            await follow(job.jobId)
        } catch {
            // Nothing was saved: give the words back.
            draft = text
            sent = nil
            thinkingSince = nil
            status = nil
            self.error = Self.message(for: error)
        }
    }

    /// Polls a turn until the coach has answered, then reloads the chat with both messages.
    private func follow(_ job: String) async {
        guard let id = conversation?.id else { return }
        let api = client()
        if thinkingSince == nil { thinkingSince = .now }
        defer {
            sent = nil
            thinkingSince = nil
            status = nil
        }
        do {
            while true {
                let turn = try await api.getLive("/notes/chat/phone/\(job)", as: CoachTurnJob.self)
                if turn.status == "failed" {
                    defaults.removeObject(forKey: Self.pendingKey(id))
                    error = turn.message ?? "Coach reply unavailable. Please try again."
                    break
                }
                if turn.status == "succeeded", turn.replyId != nil {
                    defaults.removeObject(forKey: Self.pendingKey(id))
                    break
                }
                status = turn.message
                try await Task.sleep(for: pollInterval)
            }
        } catch is CancellationError {
            // The sheet closed; the backend still saves the reply and the next open picks it up.
            return
        } catch APIError.status(404) {
            // The backend or helper restarted and forgot the turn.
            defaults.removeObject(forKey: Self.pendingKey(id))
        } catch {
            self.error = Self.message(for: error)
            return
        }
        if let fresh = try? await api.getLive(Self.messagesPath(id), as: [CoachMessage].self) {
            messages = fresh
            await markRead()
        }
    }

    private func markRead() async {
        guard let id = conversation?.id, messages.contains(where: \.fromCoach) else { return }
        _ = try? await client().send("POST", "/notes/chat/conversations/\(id)/read")
    }

    /// Starter questions for an empty chat.
    var suggestions: [String] {
        switch context?.kind {
        case .activity: ["How did this go?", "What should I change next time?"]
        case .day: ["Should I still do today's session?", "Give me a shorter version"]
        case .week: ["How is this week going?", "What should next week focus on?"]
        case nil: ["How am I recovering?", "What should I focus on this week?"]
        }
    }

    nonisolated static func message(for error: Error) -> String {
        switch error {
        case APIError.status(409): "The coach is still answering another chat. Try again in a minute."
        case APIError.status(503): "The coach helper on the Mac isn't running. Start it with `just coach-helper-start`."
        case APIError.unreachable: "Can't reach the TrainLog server. The coach needs the Mac."
        default: error.localizedDescription
        }
    }
}
