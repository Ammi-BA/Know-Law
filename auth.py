"""
=============================================================================
auth.py (SECURITY & LOGIN MODULE)
=============================================================================
This file handles all user authentication logic.
Read this file second, after understanding App.py.

It manages:
- Logging in and Registering users
- Securely hashing passwords using bcrypt
- Sending password reset emails via SMTP
- Session management across Streamlit pages
"""
import sqlite3
import hashlib
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

import bcrypt
from dotenv import load_dotenv

# Load .env variables (admin credentials, etc.)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── Absolute DB path — works regardless of where `streamlit run` is called from ──
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowlaw.db")

ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL",    "admin@knowlaw.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

EMAIL_SENDER   = os.getenv("EMAIL_SENDER",   "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
APP_BASE_URL   = os.getenv("APP_BASE_URL", "http://localhost:8501")


# ==========================================
# PASSWORD HASHING (bcrypt)
# ==========================================

def hash_password(password: str) -> str:
    """Hash a password with bcrypt (includes random salt automatically)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.
    Supports both bcrypt (new) and legacy SHA-256 (migration fallback).
    """
    # Modern bcrypt check
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False
    # Legacy SHA-256 fallback (for accounts created before this upgrade)
    legacy_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return legacy_hash == stored_hash


# ==========================================
# DATABASE INITIALISATION
# ==========================================

def init_db():
    """Creates all tables and injects the default Admin account if it doesn't exist."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ── Users ──────────────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            role            TEXT    NOT NULL,
            full_name       TEXT    NOT NULL,
            email           TEXT    UNIQUE NOT NULL,
            password_hash   TEXT    NOT NULL,
            phone           TEXT,
            age             INTEGER,
            city            TEXT,
            address         TEXT,
            verified_status TEXT    DEFAULT "Unverified",
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Lawyer Profiles ────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Lawyer_Profiles (
            user_id   INTEGER PRIMARY KEY,
            specialty TEXT,
            bio       TEXT,
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    # ── Appointments ───────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_id       INTEGER NOT NULL,
            lawyer_id        INTEGER NOT NULL,
            request_message  TEXT    NOT NULL,
            response_details TEXT,
            status           TEXT    DEFAULT "Pending",
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(citizen_id) REFERENCES Users(id),
            FOREIGN KEY(lawyer_id)  REFERENCES Users(id)
        )
    ''')

    # ── Chat History ───────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chat_History (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            session_name TEXT    NOT NULL,
            session_type TEXT    DEFAULT 'chat',
            chat_json    TEXT    NOT NULL,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    # ── Password Reset Tokens ──────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Password_Resets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    NOT NULL,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Schema Migrations (safe, idempotent) ───────────────────────────────────
    for migration in [
        "ALTER TABLE Appointments ADD COLUMN response_details TEXT",
        "ALTER TABLE Appointments ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE Users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ]:
        try:
            cursor.execute(migration)
        except sqlite3.OperationalError:
            pass  # Column already exists — skip silently

    # ── Default Admin Account ──────────────────────────────────────────────────
    cursor.execute("SELECT id FROM Users WHERE email = ?", (ADMIN_EMAIL,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO Users (role, full_name, email, password_hash, verified_status) "
            "VALUES ('Admin', 'System Admin', ?, ?, 'Approved')",
            (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
        )

    conn.commit()
    conn.close()


# Run once when the module is imported
init_db()


# ==========================================
# PASSWORD RESET
# ==========================================

def create_password_reset_token(email: str) -> str | None:
    """
    Creates a secure 32-byte URL-safe token for the given email,
    stores it in Password_Resets with a 30-minute expiry,
    and returns the token string.  Returns None if the email is not found.
    """
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Check email exists
    cursor.execute("SELECT id FROM Users WHERE email = ?", (email.lower().strip(),))
    if not cursor.fetchone():
        conn.close()
        return None

    # Delete any existing tokens for this email
    cursor.execute("DELETE FROM Password_Resets WHERE email = ?", (email.lower().strip(),))

    token      = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    cursor.execute(
        "INSERT INTO Password_Resets (email, token, expires_at) VALUES (?, ?, ?)",
        (email.lower().strip(), token, expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def validate_reset_token(token: str) -> str | None:
    """
    Returns the email associated with the token if it's valid and not expired.
    Returns None otherwise.
    """
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email, expires_at FROM Password_Resets WHERE token = ?", (token,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    email, expires_at_str = row
    expires_at = datetime.fromisoformat(expires_at_str)
    if datetime.utcnow() > expires_at:
        return None   # Token expired
    return email


def reset_password(token: str, new_password: str) -> bool:
    """
    Validates token and sets a new bcrypt-hashed password.
    Deletes the token after successful use.
    Returns True on success.
    """
    email = validate_reset_token(token)
    if not email:
        return False

    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Users SET password_hash = ? WHERE email = ?",
        (hash_password(new_password), email),
    )
    cursor.execute("DELETE FROM Password_Resets WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return True


def send_reset_email(email: str, token: str) -> tuple[bool, str]:
    """
    Sends a password reset email with a one-time link.
    Returns (True, "") on success or (False, error_message) on failure.
    """
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return False, "Email sender not configured in .env file."

    reset_url = f"{APP_BASE_URL}?reset_token={token}"

    msg             = MIMEMultipart("alternative")
    msg["Subject"]  = "KnowLaw AI — Password Reset Request"
    msg["From"]     = EMAIL_SENDER
    msg["To"]       = email

    text_body = f"""KnowLaw AI — Password Reset

You requested a password reset for your KnowLaw AI account.

Click the link below to set a new password (valid for 30 minutes):
{reset_url}

If you did not request this, ignore this email — your password will not change.

KnowLaw AI Team"""

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#0d1117;color:#c9d1d9;padding:40px;">
      <div style="max-width:480px;margin:auto;background:#161f2e;border-radius:14px;padding:32px;border:1px solid #21262d;">
        <div style="text-align:center;font-size:2.5rem;">⚖️</div>
        <h2 style="color:#58a6ff;text-align:center;">KnowLaw AI</h2>
        <h3 style="color:#e6edf3;">Password Reset Request</h3>
        <p>You requested a password reset for your account (<strong>{email}</strong>).</p>
        <p>Click the button below. This link is valid for <strong>30 minutes</strong>.</p>
        <div style="text-align:center;margin:28px 0;">
          <a href="{reset_url}" style="background:linear-gradient(135deg,#1f6feb,#388bfd);color:#fff;
             padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;
             display:inline-block;">Reset My Password</a>
        </div>
        <p style="color:#8b949e;font-size:0.85rem;">If you did not request this, ignore this email.</p>
        <hr style="border-color:#21262d;"/>
        <p style="color:#8b949e;font-size:0.8rem;text-align:center;">KnowLaw AI — Egyptian Legal Assistant</p>
      </div>
    </body></html>"""

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, email, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "Email authentication failed. Check EMAIL_SENDER and EMAIL_PASSWORD in .env"
    except Exception as exc:
        return False, str(exc)


# ==========================================
# AUTHENTICATION
# ==========================================

def login_user(email: str, password: str):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, full_name, verified_status, password_hash FROM Users WHERE email = ?",
        (email,),
    )
    user = cursor.fetchone()
    conn.close()

    if user and check_password(password, user[4]):
        return {"id": user[0], "role": user[1], "full_name": user[2], "status": user[3]}
    return None


def register_user(role, full_name, email, password, phone, age, city, address,
                  specialty=None, bio=None) -> bool:
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    status = "Pending" if role == "Lawyer" else "Approved"
    try:
        cursor.execute(
            "INSERT INTO Users (role, full_name, email, password_hash, phone, age, city, address, verified_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (role, full_name, email, hash_password(password), phone, age, city, address, status),
        )
        user_id = cursor.lastrowid
        if role == "Lawyer":
            cursor.execute(
                "INSERT INTO Lawyer_Profiles (user_id, specialty, bio) VALUES (?, ?, ?)",
                (user_id, specialty or "Not Specified", bio or "No bio provided."),
            )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success


# ==========================================
# ADMIN FUNCTIONS
# ==========================================

def get_pending_lawyers() -> list:
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT u.id, u.full_name, u.email, u.city, l.specialty, l.bio "
        "FROM Users u JOIN Lawyer_Profiles l ON u.id = l.user_id "
        "WHERE u.role = 'Lawyer' AND u.verified_status = 'Pending'"
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "email": r[2], "city": r[3],
             "specialty": r[4], "bio": r[5]} for r in rows]


def approve_lawyer(user_id: int):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET verified_status = 'Approved' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def reject_lawyer(user_id: int):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Lawyer_Profiles WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM Users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ==========================================
# LAWYER DIRECTORY
# ==========================================

def get_approved_lawyers(city=None, specialty=None, search=None) -> list:
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    query  = (
        "SELECT u.id, u.full_name, u.city, u.phone, l.specialty, l.bio "
        "FROM Users u LEFT JOIN Lawyer_Profiles l ON u.id = l.user_id "
        "WHERE u.role = 'Lawyer' AND u.verified_status = 'Approved'"
    )
    params = []
    if city:
        query += " AND u.city = ?"
        params.append(city)
    if specialty:
        query += " AND l.specialty = ?"
        params.append(specialty)
    if search:
        query += " AND u.full_name LIKE ?"
        params.append(f"%{search}%")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id":        r[0],
            "name":      r[1],
            "city":      r[2] or "Not specified",
            "phone":     r[3] or "N/A",
            "specialty": r[4] or "Not specified",
            "bio":       r[5] or "Not specified",
        }
        for r in rows
    ]


# ==========================================
# APPOINTMENTS
# ==========================================

def send_appointment_request(citizen_id: int, lawyer_id: int, message: str):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Appointments (citizen_id, lawyer_id, request_message) VALUES (?, ?, ?)",
        (citizen_id, lawyer_id, message),
    )
    conn.commit()
    conn.close()


def get_lawyer_appointments(lawyer_id: int) -> list:
    """Returns all appointment requests received by a lawyer."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT a.id, u.full_name, u.phone, a.request_message, a.status, "
        "       a.response_details, a.created_at "
        "FROM Appointments a "
        "JOIN Users u ON a.citizen_id = u.id "
        "WHERE a.lawyer_id = ? "
        "ORDER BY a.created_at DESC",
        (lawyer_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id":            r[0],
            "citizen_name":  r[1],
            "citizen_phone": r[2] or "N/A",
            "message":       r[3],
            "status":        r[4],
            "response":      r[5],
            "created_at":    r[6],
        }
        for r in rows
    ]


def get_citizen_appointments(citizen_id: int) -> list:
    """Returns all appointment requests sent by a citizen."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT a.id, u.full_name, u.phone, a.request_message, a.status, "
        "       a.response_details, a.created_at "
        "FROM Appointments a "
        "JOIN Users u ON a.lawyer_id = u.id "
        "WHERE a.citizen_id = ? "
        "ORDER BY a.created_at DESC",
        (citizen_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id":            r[0],
            "lawyer_name":   r[1],
            "lawyer_phone":  r[2] or "N/A",
            "message":       r[3],
            "status":        r[4],
            "response":      r[5],
            "created_at":    r[6],
        }
        for r in rows
    ]


def respond_to_appointment(appointment_id: int, status: str, response_details: str):
    """Lawyer accepts or declines an appointment request."""
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Appointments SET status = ?, response_details = ? WHERE id = ?",
        (status, response_details, appointment_id),
    )
    conn.commit()
    conn.close()