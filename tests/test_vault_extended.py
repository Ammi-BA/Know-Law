import pytest
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import vault_manager

# Use a fake user ID that will never collide with real data
TEST_USER_ID = 777777


@pytest.fixture
def temp_vault_db(monkeypatch):
    """
    Patches vault_manager.DB_NAME to point to a fresh temp database for each test,
    then initializes the Chat_History table schema inside that temp database.
    monkeypatch automatically restores the original DB_NAME after each test.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_vault_ext.db")
        monkeypatch.setattr(vault_manager, 'DB_NAME', db_path)
        vault_manager.init_vault_db()
        yield db_path


# ==========================================
# 1. DELETE CHAT TESTS
# ==========================================

class TestDeleteChat:

    def test_delete_chat_happy_path(self, temp_vault_db):
        """HAPPY PATH: Saving a chat then deleting it must make it unloadable."""
        vault_manager.save_chat(
            TEST_USER_ID, "To Delete",
            [{"role": "user", "content": "delete me"}],
            session_type="chat"
        )
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        chat_id = chats[0]["id"]

        vault_manager.delete_chat(chat_id)

        # After deletion, loading by that ID must return an empty list
        loaded = vault_manager.load_chat(chat_id)
        assert loaded == []

    def test_delete_removes_from_user_list(self, temp_vault_db):
        """After deletion, the chat must no longer appear in get_user_chats."""
        vault_manager.save_chat(
            TEST_USER_ID, "Disappearing Chat",
            [{"role": "user", "content": "goodbye"}],
            session_type="chat"
        )
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        chat_id = chats[0]["id"]

        vault_manager.delete_chat(chat_id)

        remaining = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        ids = [c["id"] for c in remaining]
        assert chat_id not in ids

    def test_delete_nonexistent_chat_does_not_crash(self, temp_vault_db):
        """EDGE CASE: Deleting an ID that never existed must not raise any exception."""
        vault_manager.delete_chat(9999999)  # Should silently do nothing

    def test_delete_one_does_not_affect_others(self, temp_vault_db):
        """EDGE CASE: Deleting one chat must leave all other chats untouched."""
        vault_manager.save_chat(TEST_USER_ID, "Keep Me",   [{"role": "user", "content": "stay"}],  session_type="chat")
        vault_manager.save_chat(TEST_USER_ID, "Delete Me", [{"role": "user", "content": "delete"}], session_type="chat")

        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        to_delete = next(c for c in chats if c["session_name"] == "Delete Me")
        vault_manager.delete_chat(to_delete["id"])

        remaining = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        names = [c["session_name"] for c in remaining]
        assert "Keep Me" in names
        assert "Delete Me" not in names


# ==========================================
# 2. ARABIC CONTENT PRESERVATION TESTS
# ==========================================

class TestArabicContent:

    def test_save_and_load_arabic_content(self, temp_vault_db):
        """HAPPY PATH: Arabic text must be stored and retrieved without any corruption."""
        arabic_messages = [
            {"role": "user",      "content": "ما هو قانون العقوبات؟"},
            {"role": "assistant", "content": "قانون العقوبات هو مجموعة القواعد التي تحدد الجرائم والعقوبات."},
        ]
        vault_manager.save_chat(TEST_USER_ID, "Arabic Chat", arabic_messages, session_type="chat")
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        loaded = vault_manager.load_chat(chats[0]["id"])

        assert loaded[0]["content"] == "ما هو قانون العقوبات؟"
        assert loaded[1]["content"] == "قانون العقوبات هو مجموعة القواعد التي تحدد الجرائم والعقوبات."

    def test_mixed_arabic_and_english_content(self, temp_vault_db):
        """EDGE CASE: Messages mixing Arabic and English characters must be preserved exactly."""
        mixed_messages = [
            {"role": "user",      "content": "Question about المادة 45 من القانون المدني"},
            {"role": "assistant", "content": "Article 45 (المادة ٤٥) states: يجب الامتثال للقانون."},
        ]
        vault_manager.save_chat(TEST_USER_ID, "Mixed Chat", mixed_messages, session_type="chat")
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        loaded = vault_manager.load_chat(chats[0]["id"])

        assert loaded[0]["content"] == "Question about المادة 45 من القانون المدني"
        assert loaded[1]["content"] == "Article 45 (المادة ٤٥) states: يجب الامتثال للقانون."

    def test_special_characters_preserved(self, temp_vault_db):
        """EDGE CASE: JSON special characters inside message content must survive serialisation."""
        tricky_messages = [
            {"role": "user", "content": 'He said "hello" and it\'s fine — © 2024'},
        ]
        vault_manager.save_chat(TEST_USER_ID, "Special Chars", tricky_messages, session_type="chat")
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        loaded = vault_manager.load_chat(chats[0]["id"])

        assert loaded[0]["content"] == 'He said "hello" and it\'s fine — © 2024'


# ==========================================
# 3. SESSION TYPE ISOLATION TESTS
# ==========================================

class TestSessionTypes:

    def test_all_three_session_types_stored_independently(self, temp_vault_db):
        """HAPPY PATH: chat, ocr, and contract sessions must each be stored and retrieved separately."""
        vault_manager.save_chat(TEST_USER_ID, "My Chat",     [{"role": "user", "content": "law?"}],      session_type="chat")
        vault_manager.save_chat(TEST_USER_ID, "My OCR",      [{"role": "user", "content": "scan text"}], session_type="ocr")
        vault_manager.save_chat(TEST_USER_ID, "My Contract", [{"role": "user", "content": "contract"}],  session_type="contract")

        assert len(vault_manager.get_user_chats(TEST_USER_ID, session_type="chat"))     == 1
        assert len(vault_manager.get_user_chats(TEST_USER_ID, session_type="ocr"))      == 1
        assert len(vault_manager.get_user_chats(TEST_USER_ID, session_type="contract")) == 1

    def test_wrong_session_type_returns_nothing(self, temp_vault_db):
        """NEGATIVE TEST: Querying a session type that the user never used must return []."""
        vault_manager.save_chat(TEST_USER_ID, "Only Chat", [{"role": "user", "content": "hi"}], session_type="chat")
        results = vault_manager.get_user_chats(TEST_USER_ID, session_type="ocr")
        assert results == []

    def test_same_session_name_different_types_coexist(self, temp_vault_db):
        """EDGE CASE: The same session_name under two different types must not collide."""
        vault_manager.save_chat(TEST_USER_ID, "Session A", [{"role": "user", "content": "chat msg"}],    session_type="chat")
        vault_manager.save_chat(TEST_USER_ID, "Session A", [{"role": "user", "content": "ocr result"}],  session_type="ocr")

        chat_sessions = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        ocr_sessions  = vault_manager.get_user_chats(TEST_USER_ID, session_type="ocr")

        # Each type must have exactly one "Session A"
        assert len(chat_sessions) == 1
        assert len(ocr_sessions)  == 1

        chat_loaded = vault_manager.load_chat(chat_sessions[0]["id"])
        ocr_loaded  = vault_manager.load_chat(ocr_sessions[0]["id"])

        assert chat_loaded[0]["content"] == "chat msg"
        assert ocr_loaded[0]["content"]  == "ocr result"


# ==========================================
# 4. ORDERING TESTS
# ==========================================

class TestOrdering:

    def test_newest_chat_returned_first(self, temp_vault_db):
        """EDGE CASE: get_user_chats must return sessions ordered newest-first."""
        vault_manager.save_chat(TEST_USER_ID, "First Session",  [{"role": "user", "content": "first"}],  session_type="chat")
        time.sleep(0.05)  # ensure different updated_at timestamp
        vault_manager.save_chat(TEST_USER_ID, "Second Session", [{"role": "user", "content": "second"}], session_type="chat")

        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        assert chats[0]["session_name"] == "Second Session"

    def test_updated_chat_moves_to_top(self, temp_vault_db):
        """EDGE CASE: When an old chat is updated (upserted), it should move to the top of the list."""
        vault_manager.save_chat(TEST_USER_ID, "Old Session",    [{"role": "user", "content": "old"}],    session_type="chat")
        time.sleep(0.05)
        vault_manager.save_chat(TEST_USER_ID, "Newer Session",  [{"role": "user", "content": "newer"}],  session_type="chat")
        time.sleep(0.05)
        # Re-save (upsert) the old session — it should now be the newest
        vault_manager.save_chat(TEST_USER_ID, "Old Session",    [{"role": "user", "content": "updated"}], session_type="chat")

        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        assert chats[0]["session_name"] == "Old Session"
