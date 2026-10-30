import Foundation
import Testing
@testable import TrainLog

struct CoachChatTests {
    @Test func decodesConversationsAndMessages() throws {
        let conversations = try APIClient.decoder.decode([CoachConversation].self, from: Data("""
        [{"id": 7, "title": "Thu 30 Oct", "context_kind": "day", "context_id": "2026-10-30",
          "created_at": "2026-10-30 07:00:00", "updated_at": "2026-10-30 07:02:11",
          "last_read_message_id": 3, "message_count": 4, "unread_count": 1},
         {"id": 2, "title": "Knee question", "context_kind": null, "context_id": null, "message_count": 2, "unread_count": 0}]
        """.utf8))
        #expect(CoachFormat.kind(conversations[0]) == .day)
        #expect(CoachFormat.kind(conversations[1]) == nil)
        #expect(conversations[0].unreadCount == 1)

        let messages = try APIClient.decoder.decode([CoachMessage].self, from: Data("""
        [{"id": 1, "conversation_id": 7, "role": "user", "content": "Legs heavy", "created_at": "2026-10-30 07:00:00"},
         {"id": 2, "conversation_id": 7, "role": "assistant", "content": "Go easy.", "created_at": "2026-10-30 07:02:11"}]
        """.utf8))
        #expect(messages.map(\.fromCoach) == [false, true])

        let job = try APIClient.decoder.decode(CoachTurnJob.self, from: Data("""
        {"job_id": "abc", "status": "succeeded", "message": "Coach replied.", "reply_id": 12}
        """.utf8))
        #expect(job.replyId == 12)
    }

    @Test func splitsMarkdownIntoBlocks() {
        let blocks = CoachFormat.blocks("""
        ## Today
        Keep it **easy**: legs are
        still heavy.

        - 45 min Z2
        * no intervals
        1. Check in tomorrow
        2) Then decide
        """)
        #expect(blocks == [
            .heading("Today"),
            .paragraph("Keep it **easy**: legs are still heavy."),
            .bullet("•", "45 min Z2"),
            .bullet("•", "no intervals"),
            .bullet("1.", "Check in tomorrow"),
            .bullet("2.", "Then decide"),
        ])
    }

    @Test func namesContextsAndTimes() {
        #expect(CoachFormat.weekContext("2026-10-26").id == "2026-10-26")
        #expect(CoachFormat.dayContext("2026-10-30", title: "Endurance ride (Z2)").title.hasSuffix("· Endurance ride"))
        #expect(CoachFormat.activityContext("123", title: "").title == "Activity")
        #expect(CoachFormat.elapsed(65) == "1:05")
        let parsed = CoachFormat.parseTimestamp("2026-10-30 14:05:00")
        #expect(parsed == ISO8601DateFormatter().date(from: "2026-10-30T14:05:00Z"))
    }
}
