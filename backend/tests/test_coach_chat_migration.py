import os
import sqlite3
import tempfile
import unittest

from backend.app import db


class CoachChatMigrationTests(unittest.TestCase):
    def test_existing_messages_are_grouped_into_a_previous_conversation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "training.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE coach_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO coach_chat_messages (role, content) VALUES
                    ('user', 'How was my ride?'),
                    ('assistant', 'It was an appropriate recovery ride.');
                """
            )
            conn.commit()
            conn.close()

            previous_path = db.DB_PATH
            db.DB_PATH = db_path
            try:
                db.init_db()
            finally:
                db.DB_PATH = previous_path

            conn = sqlite3.connect(db_path)
            try:
                conversation = conn.execute(
                    "SELECT id, title FROM coach_chat_conversations"
                ).fetchone()
                self.assertEqual(conversation[1], "Previous conversation")
                message_conversations = conn.execute(
                    "SELECT DISTINCT conversation_id FROM coach_chat_messages"
                ).fetchall()
                self.assertEqual(message_conversations, [(conversation[0],)])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
