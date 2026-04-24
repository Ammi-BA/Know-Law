"""
=============================================================================
database_setup.py (SQLITE SCHEMA BUILDER)
=============================================================================
This file initializes the local user database.
Read this file third, to understand how data is stored.

It executes the SQL commands to create tables for:
- Users & Lawyer Profiles
- Chat History
- Vault Files (OCR documents and Contracts)
- Lawyer Appointments
- Password Resets
"""
import sqlite3
import bcrypt
import os

# --- Configuration ---
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowlaw.db")
VAULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_data")

def hash_password(password):
    """Creates a secure bcrypt hash — MUST match auth.py behaviour."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def setup_database():
    print("🚀 Initializing Know Law Database Architecture...")
    
    # 1. Create the physical Vault folder if it doesn't exist
    if not os.path.exists(VAULT_FOLDER):
        os.makedirs(VAULT_FOLDER)
        print("📁 Created secure storage folder: vault_data/")

    # 2. Connect to SQLite (Creates the file if it doesn't exist)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 3. CREATE TABLES ---
    
    print("🛠️ Building 'Users' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL, 
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            age INTEGER,
            city TEXT,
            address TEXT,
            verified_status TEXT DEFAULT 'Unverified',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    print("🛠️ Building 'Lawyer_Profiles' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Lawyer_Profiles (
            user_id INTEGER PRIMARY KEY,
            specialty TEXT,
            bio TEXT,
            approval_status TEXT DEFAULT 'Pending',
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    print("🛠️ Building 'Chat_History' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chat_History (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            session_type TEXT DEFAULT 'chat',
            chat_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    print("🛠️ Building 'Vault_Files' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Vault_Files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL, 
            file_path TEXT NOT NULL,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    ''')

    print("🛠️ Building 'Appointments' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_id INTEGER NOT NULL,
            lawyer_id INTEGER NOT NULL,
            request_message TEXT NOT NULL,
            response_details TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(citizen_id) REFERENCES Users(id),
            FOREIGN KEY(lawyer_id) REFERENCES Users(id)
        )
    ''')

    print("🛠️ Building 'Password_Resets' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Password_Resets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    NOT NULL,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 4. INJECT DEFAULT ADMIN ACCOUNT ---
    admin_email = "admin@knowlaw.com"
    admin_pass = hash_password("admin123")
    
    # Check if admin already exists
    cursor.execute("SELECT id FROM Users WHERE email = ?", (admin_email,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO Users (role, full_name, email, password_hash, verified_status)
            VALUES ('Admin', 'System Admin', ?, ?, 'Approved')
        ''', (admin_email, admin_pass))
        print("👑 Default Admin account created! (Email: admin@knowlaw.com | Pass: admin123)")

    # Save changes and close
    conn.commit()
    conn.close()
    print("✅ Database setup complete! knowlaw.db is ready.")

if __name__ == "__main__":
    setup_database()