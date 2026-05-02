import os
import sqlite3
import pytest
import tempfile
from unittest.mock import patch

# Import the database_setup module
import database_setup

@pytest.fixture
def temp_db_env():
    """Fixture to create a temporary database file and vault folder."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_knowlaw.db")
        vault_path = os.path.join(temp_dir, "test_vault_data")
        
        # Patch the configuration variables in the module
        with patch('database_setup.DB_NAME', db_path), \
             patch('database_setup.VAULT_FOLDER', vault_path):
            yield db_path, vault_path

def test_setup_database_happy_path(temp_db_env):
    """
    HAPPY PATH: Test that running the setup script successfully builds the database
    and creates the necessary physical vault folder without errors.
    """
    db_path, vault_path = temp_db_env

    # Act
    database_setup.setup_database()

    # Assert 1: Vault folder was physically created
    assert os.path.exists(vault_path), "Vault folder was not created."

    # Assert 2: Database file was created
    assert os.path.exists(db_path), "SQLite database file was not created."

    # Assert 3: All 6 core tables exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = ["Users", "Lawyer_Profiles", "Chat_History", "Vault_Files", "Appointments", "Password_Resets"]
    for table in expected_tables:
        assert table in tables, f"Missing table in database: {table}"

    # Assert 4: Default Admin account was injected
    cursor.execute("SELECT email, role FROM Users WHERE email='admin@knowlaw.com'")
    admin = cursor.fetchone()
    assert admin is not None, "Default Admin account was not injected."
    assert admin[1] == "Admin", "Admin account does not have the 'Admin' role."
    conn.close()

def test_setup_database_edge_case_idempotency(temp_db_env):
    """
    EDGE CASE: Test running the setup script twice on the same database.
    Ensures that the script uses IF NOT EXISTS and does not crash or duplicate the admin.
    """
    db_path, vault_path = temp_db_env

    # Act - Run it twice
    database_setup.setup_database()
    database_setup.setup_database() # Second run should be safe

    # Assert - Ensure no duplicate admin accounts
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Users WHERE email='admin@knowlaw.com'")
    admin_count = cursor.fetchone()[0]
    conn.close()

    assert admin_count == 1, "Edge Case failed: Admin account was duplicated when running setup twice."

def test_setup_database_negative_permission_error(temp_db_env):
    """
    NEGATIVE TEST: Simulate a PermissionError when trying to create the vault folder.
    Ensures that if the server denies file write permissions, the unhandled crash is caught
    during our testing suite logic.
    """
    db_path, vault_path = temp_db_env

    # Act & Assert
    with patch('os.makedirs', side_effect=PermissionError("Simulated Permission Denied")):
        with pytest.raises(PermissionError):
            database_setup.setup_database()
            # The test passes because the script accurately bubbles up the PermissionError
            # instead of silently failing and pretending the folder was created.
