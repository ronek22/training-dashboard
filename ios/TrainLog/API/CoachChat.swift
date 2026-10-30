import Foundation

/// `GET /notes/chat/conversations`: chats shared with the web Coach page.
struct CoachConversation: Decodable, Sendable, Identifiable, Hashable {
    let id: Int
    let title: String
    let contextKind: String?
    let contextId: String?
    let updatedAt: String?
    let messageCount: Int?
    let unreadCount: Int?
}

/// `GET /notes/chat?conversation_id=`.
struct CoachMessage: Decodable, Sendable, Identifiable, Hashable {
    let id: Int
    let role: String
    let content: String
    let createdAt: String?

    var fromCoach: Bool { role == "assistant" }
}

/// What a chat is about: one activity, one day or one week (its Monday). Nil is a general chat.
struct CoachContext: Sendable, Hashable, Identifiable {
    enum Kind: String, Sendable { case activity, day, week }

    let kind: Kind
    let id: String
    /// The conversation's title when it's first opened, as the web names it.
    let title: String
}

/// `POST /notes/chat/conversations/open` body.
struct CoachContextOpen: Encodable, Sendable {
    let contextKind: String
    let contextId: String
    let title: String
}

/// `POST /notes/chat/conversations` body.
struct CoachConversationCreate: Encodable, Sendable {
    let title: String
}

/// `POST /notes/chat/phone` body: the backend asks the coach helper and saves both messages.
struct CoachTurnRequest: Encodable, Sendable {
    let conversationId: Int
    let message: String
}

/// `POST /notes/chat/phone` and `GET /notes/chat/phone/{job_id}`.
struct CoachTurnJob: Decodable, Sendable {
    let jobId: String
    let status: String
    let message: String?
    /// The saved reply, once the coach has answered.
    let replyId: Int?
}
