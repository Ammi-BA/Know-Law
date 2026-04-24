import sqlite3
import json
import os

# ── Absolute DB path — mirrors auth.py ────────────────────────────────────────
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowlaw.db")


def init_vault_db():
    """Ensures the Chat_History table exists and has the session_type column."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chat_History (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            session_name TEXT    NOT NULL,
            chat_json    TEXT    NOT NULL,
            session_type TEXT    DEFAULT 'chat',
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')
    # Safe migration: add session_type column if it doesn't exist yet
    try:
        cursor.execute("ALTER TABLE Chat_History ADD COLUMN session_type TEXT DEFAULT 'chat'")
    except sqlite3.OperationalError:
        pass  # Column already exists — skip silently

    # Fix legacy rows: any row with NULL session_type → set to 'chat'
    cursor.execute("UPDATE Chat_History SET session_type = 'chat' WHERE session_type IS NULL")

    conn.commit()
    conn.close()


# Run once on import
init_vault_db()


def save_chat(user_id: int, session_name: str, messages: list, session_type: str = "chat"):
    """
    Saves or updates a chat session. Upserts by (user_id, session_name, session_type).
    session_type: 'chat' | 'ocr' | 'contract'
    """
    conn      = sqlite3.connect(DB_NAME)
    cursor    = conn.cursor()
    chat_json = json.dumps(messages, ensure_ascii=False)  # preserve Arabic chars

    cursor.execute(
        "SELECT id FROM Chat_History WHERE user_id = ? AND session_name = ? AND session_type = ?",
        (user_id, session_name, session_type),
    )
    result = cursor.fetchone()

    if result:
        cursor.execute(
            "UPDATE Chat_History SET chat_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (chat_json, result[0]),
        )
    else:
        cursor.execute(
            "INSERT INTO Chat_History (user_id, session_name, chat_json, session_type) VALUES (?, ?, ?, ?)",
            (user_id, session_name, chat_json, session_type),
        )

    conn.commit()
    conn.close()


def get_user_chats(user_id: int, session_type: str = "chat") -> list:
    """Returns all chat sessions for a user filtered by type, newest first."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, session_name, updated_at FROM Chat_History "
        "WHERE user_id = ? AND session_type = ? ORDER BY updated_at DESC",
        (user_id, session_type),
    )
    chats = cursor.fetchall()
    conn.close()
    return [{"id": c[0], "session_name": c[1], "updated_at": c[2]} for c in chats]


def load_chat(chat_id: int) -> list:
    """Loads the message list for a specific chat session."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_json FROM Chat_History WHERE id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result else []


def delete_chat(chat_id: int):
    """Permanently deletes a chat session by its ID."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Chat_History WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()