"""Standing preferences saved from the coach chat: stored, edited, retired, and read by planning."""
import unittest

from backend.tests import smoke_base


class CoachPreferenceTests(smoke_base.SmokeTestCase):
    def _chat_message(self, content="No leg lifts the day before a long ride."):
        conversation_id = self.client.post("/notes/chat/conversations", json={"title": "Leg day timing"}).json()["id"]
        message = self.client.post(
            "/notes/chat", json={"conversation_id": conversation_id, "role": "assistant", "content": content}
        ).json()
        return conversation_id, message["id"]

    def test_saved_preference_links_its_chat_and_reaches_recent_context(self):
        conversation_id, message_id = self._chat_message()
        created = self.client.post(
            "/notes/preferences",
            json={"content": "  No leg lifts\nthe day before a long ride ", "conversation_id": conversation_id, "message_id": message_id},
        )
        self.assertEqual(created.status_code, 201)
        preference = created.json()
        self.assertEqual(preference["content"], "No leg lifts the day before a long ride")
        self.assertEqual(preference["status"], "active")
        self.assertEqual(preference["source_conversation_id"], conversation_id)
        self.assertEqual(preference["source_conversation_title"], "Leg day timing")

        context = self.client.get("/context/recent").json()
        self.assertEqual([item["preference"] for item in context["standing_preferences"]], [preference["content"]])

        edited = self.client.patch(f"/notes/preferences/{preference['id']}", json={"content": "No leg lifts before long rides"})
        self.assertEqual(edited.json()["content"], "No leg lifts before long rides")

        retired = self.client.patch(f"/notes/preferences/{preference['id']}", json={"status": "retired"})
        self.assertEqual(retired.json()["status"], "retired")
        self.assertEqual(self.client.get("/notes/preferences").json(), [])
        self.assertEqual(len(self.client.get("/notes/preferences?include_retired=true").json()), 1)
        self.assertEqual(self.client.get("/context/recent").json()["standing_preferences"], [])

    def test_preference_is_validated_and_survives_its_chat(self):
        conversation_id, message_id = self._chat_message()
        self.assertEqual(self.client.post("/notes/preferences", json={"content": "   "}).status_code, 400)
        self.assertEqual(self.client.post("/notes/preferences", json={"content": "x" * 301}).status_code, 400)
        self.assertEqual(
            self.client.post("/notes/preferences", json={"content": "Rule", "conversation_id": 999}).status_code, 400
        )
        other_conversation, _ = self._chat_message()
        self.assertEqual(
            self.client.post(
                "/notes/preferences", json={"content": "Rule", "conversation_id": other_conversation, "message_id": message_id}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.patch("/notes/preferences/999", json={"status": "retired"}).status_code, 404)

        preference = self.client.post(
            "/notes/preferences", json={"content": "Rule", "message_id": message_id}
        ).json()
        self.assertEqual(preference["source_conversation_id"], conversation_id)
        self.assertEqual(self.client.patch(f"/notes/preferences/{preference['id']}", json={"status": "paused"}).status_code, 400)

        self.client.delete(f"/notes/chat/conversations/{conversation_id}")
        kept = self.client.get("/notes/preferences").json()
        self.assertEqual([item["content"] for item in kept], ["Rule"])
        self.assertIsNone(kept[0]["source_conversation_id"])


if __name__ == "__main__":
    unittest.main()
