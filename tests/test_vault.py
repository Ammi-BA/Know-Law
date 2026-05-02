import pytest
import os
import sys

# ---------------------------------------------------------
# SETUP: Tell Python where to find the vault_manager.py file
# ---------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import vault_manager

# We use a fake user ID (999999) for testing so we do not accidentally 
# delete or modify a real citizen's or lawyer's data in the database!
TEST_USER_ID = 999999

# ---------------------------------------------------------
# PYTEST SETUP & TEARDOWN
# ---------------------------------------------------------
def setup_module(module):
    """Runs ONCE before the tests start. Ensures the database tables exist."""
    vault_manager.init_vault_db()

def teardown_module(module):
    """Runs ONCE after all tests finish. Cleans up our fake user's data from the database."""
    import sqlite3
    conn = sqlite3.connect(vault_manager.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Chat_History WHERE user_id = ?", (TEST_USER_ID,))
    conn.commit()
    conn.close()

class TestVaultManager:
    # -----------------------------------------------------
    # HAPPY PATH: Testing normal, expected, correct inputs
    # -----------------------------------------------------
    def test_save_and_load_chat_happy_path(self):
        """Tests that a normal chat can be saved to the database and perfectly loaded back."""
        session_name = "Test Legal Case"
        
        # This is what a normal chat history looks like
        messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        
        # 1. Save the chat
        vault_manager.save_chat(TEST_USER_ID, session_name, messages, session_type="chat")
        
        # 2. Retrieve it to find out what ID the database gave it
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        assert len(chats) >= 1  # Make sure we got at least one result back
        
        chat_id = chats[0]["id"]
        
        # 3. Load the actual message text and verify it wasn't corrupted
        loaded_messages = vault_manager.load_chat(chat_id)
        assert len(loaded_messages) == 2
        assert loaded_messages[0]["content"] == "Hello"

    # -----------------------------------------------------
    # NEGATIVE TESTS: Testing invalid inputs to ensure they are handled safely
    # -----------------------------------------------------
    def test_load_non_existent_chat(self):
        """Tests what happens if someone tries to load a chat ID that doesn't exist."""
        # Instead of throwing a massive SQL Error and crashing the app,
        # our code should safely return an empty list [].
        loaded_messages = vault_manager.load_chat(99999999)
        assert loaded_messages == []

    def test_get_chats_wrong_type(self):
        """Tests searching for a session type the user does not have."""
        # If we ask for "contract_analysis_fake", it should just return nothing.
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="contract_analysis_fake")
        assert chats == []

    # -----------------------------------------------------
    # EDGE CASES: Testing weird boundaries (empty fields, duplicates)
    # -----------------------------------------------------
    def test_save_empty_message_list(self):
        """Tests saving a chat that has exactly 0 messages in it."""
        # The database should not crash if we try to save an empty list.
        session_name = "Empty Chat"
        vault_manager.save_chat(TEST_USER_ID, session_name, [], session_type="chat")
        
        # Get the ID of the chat we just saved
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="chat")
        chat_id = [c["id"] for c in chats if c["session_name"] == "Empty Chat"][0]
        
        # Make sure loading it back gives us an empty list, not a Null error
        loaded = vault_manager.load_chat(chat_id)
        assert loaded == []

    def test_update_existing_chat(self):
        """Tests that saving the same chat twice UPDATES the row, instead of DUPLICATING it."""
        session_name = "Upsert Test"
        
        # Imagine the user sends one message...
        messages_v1 = [{"role": "user", "content": "First message"}]
        # Then 5 minutes later, they send a second message...
        messages_v2 = [{"role": "user", "content": "First message"}, {"role": "user", "content": "Second message"}]
        
        # We save both to the database under the same session_name
        vault_manager.save_chat(TEST_USER_ID, session_name, messages_v1, session_type="ocr")
        vault_manager.save_chat(TEST_USER_ID, session_name, messages_v2, session_type="ocr")
        
        # Now we ask the database for this user's chats
        chats = vault_manager.get_user_chats(TEST_USER_ID, session_type="ocr")
        upsert_chats = [c for c in chats if c["session_name"] == session_name]
        
        # CRITICAL TEST: There should only be 1 row in the database, not 2!
        assert len(upsert_chats) == 1
        
        # And that 1 row should contain the newest data (2 messages)
        loaded = vault_manager.load_chat(upsert_chats[0]["id"])
        assert len(loaded) == 2
