import pytest
import os
import sys
import sqlite3
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import auth


@pytest.fixture
def temp_auth_db():
    """Creates an isolated temp database and patches auth.DB_NAME for the test duration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_user_mgmt.db")
        with patch('auth.DB_NAME', db_path):
            auth.init_db()
            yield db_path


# ==========================================
# 1. USER REGISTRATION TESTS
# ==========================================

class TestRegisterUser:

    def test_register_citizen_happy_path(self, temp_auth_db):
        """HAPPY PATH: A new citizen registers with valid data — should succeed and return True."""
        result = auth.register_user(
            "Citizen", "Sara Hassan", "sara@test.com", "securepass",
            "0111111111", 25, "Alexandria", "5 Corniche Rd"
        )
        assert result == True

    def test_register_lawyer_happy_path(self, temp_auth_db):
        """HAPPY PATH: A lawyer registers with specialty and bio — should succeed."""
        result = auth.register_user(
            "Lawyer", "Karim Nour", "karim@test.com", "lawyerpass",
            "0122222222", 40, "Cairo", "10 Justice St",
            specialty="Criminal Law", bio="10 years of courtroom experience."
        )
        assert result == True

    def test_lawyer_starts_as_pending(self, temp_auth_db):
        """Lawyers must wait for admin approval — their verified_status should be 'Pending'."""
        auth.register_user(
            "Lawyer", "Pending Lawyer", "pending@test.com", "pass12345",
            "0122222222", 35, "Cairo", "Law St",
            specialty="Civil Law", bio="Pending approval bio."
        )
        conn = sqlite3.connect(temp_auth_db)
        cursor = conn.cursor()
        cursor.execute("SELECT verified_status FROM Users WHERE email='pending@test.com'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "Pending"

    def test_citizen_auto_approved(self, temp_auth_db):
        """Citizens do not need admin review — their verified_status should be 'Approved'."""
        auth.register_user(
            "Citizen", "Omar Yasser", "omar@test.com", "pass12345",
            "0133333333", 22, "Giza", "12 Pyramids St"
        )
        conn = sqlite3.connect(temp_auth_db)
        cursor = conn.cursor()
        cursor.execute("SELECT verified_status FROM Users WHERE email='omar@test.com'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "Approved"

    def test_register_duplicate_email(self, temp_auth_db):
        """NEGATIVE TEST: Registering the same email twice should fail (return False)."""
        auth.register_user(
            "Citizen", "First User", "dup@test.com", "pass12345",
            "0111", 20, "Cairo", "Addr"
        )
        result = auth.register_user(
            "Citizen", "Second User", "dup@test.com", "pass12345",
            "0222", 25, "Cairo", "Addr2"
        )
        assert result == False

    def test_lawyer_profile_created_on_register(self, temp_auth_db):
        """EDGE CASE: A lawyer registration should also insert a row in Lawyer_Profiles."""
        auth.register_user(
            "Lawyer", "Profile Lawyer", "profile@test.com", "pass12345",
            "0155555555", 38, "Cairo", "Profile St",
            specialty="Family Law", bio="Family law specialist."
        )
        conn = sqlite3.connect(temp_auth_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lp.specialty FROM Lawyer_Profiles lp "
            "JOIN Users u ON lp.user_id = u.id WHERE u.email='profile@test.com'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Family Law"

    def test_lawyer_default_specialty_when_none(self, temp_auth_db):
        """EDGE CASE: If no specialty is provided, it defaults to 'Not Specified'."""
        auth.register_user(
            "Lawyer", "No Specialty Lawyer", "nospec@test.com", "pass12345",
            "0166666666", 33, "Cairo", "NoSpec St"
        )
        conn = sqlite3.connect(temp_auth_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lp.specialty FROM Lawyer_Profiles lp "
            "JOIN Users u ON lp.user_id = u.id WHERE u.email='nospec@test.com'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Not Specified"


# ==========================================
# 2. LOGIN TESTS
# ==========================================

class TestLoginUser:

    def test_login_happy_path(self, temp_auth_db):
        """HAPPY PATH: A citizen logs in with the correct email and password."""
        auth.register_user(
            "Citizen", "Ahmed Ali", "ahmed@test.com", "password123",
            "0123456789", 30, "Cairo", "123 Tahrir St"
        )
        user = auth.login_user("ahmed@test.com", "password123")
        assert user is not None
        assert user["role"] == "Citizen"
        assert user["full_name"] == "Ahmed Ali"

    def test_login_wrong_password(self, temp_auth_db):
        """NEGATIVE TEST: Login with correct email but wrong password must return None."""
        auth.register_user(
            "Citizen", "Ahmed Ali", "ahmed2@test.com", "password123",
            "0123456789", 30, "Cairo", "123 Street"
        )
        user = auth.login_user("ahmed2@test.com", "wrongpassword")
        assert user is None

    def test_login_nonexistent_email(self, temp_auth_db):
        """NEGATIVE TEST: Login with an email that was never registered must return None."""
        user = auth.login_user("ghost@nowhere.com", "anypassword")
        assert user is None

    def test_login_returns_correct_role(self, temp_auth_db):
        """EDGE CASE: The returned user dict must include the correct role field."""
        auth.register_user(
            "Lawyer", "Lawyer Nada", "nada@test.com", "securepass",
            "0177777777", 42, "Cairo", "Lawyer Ave",
            specialty="Criminal Law", bio="Bio."
        )
        user = auth.login_user("nada@test.com", "securepass")
        assert user is not None
        assert user["role"] == "Lawyer"

    def test_login_admin_account(self, temp_auth_db):
        """EDGE CASE: The default Admin account injected by init_db() must be loginable."""
        user = auth.login_user("admin@knowlaw.com", "admin123")
        assert user is not None
        assert user["role"] == "Admin"


# ==========================================
# 3. ADMIN APPROVAL WORKFLOW TESTS
# ==========================================

class TestAdminFunctions:

    @pytest.fixture
    def db_with_pending_lawyer(self, temp_auth_db):
        """Sub-fixture: registers a pending lawyer and returns (db_path, lawyer_id)."""
        auth.register_user(
            "Lawyer", "Lawyer Pending", "toapprove@test.com", "pass12345",
            "0188888888", 37, "Cairo", "Pending Blvd",
            specialty="Tax Law", bio="Tax expert."
        )
        conn = sqlite3.connect(temp_auth_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE email='toapprove@test.com'")
        lawyer_id = cursor.fetchone()[0]
        conn.close()
        return temp_auth_db, lawyer_id

    def test_get_pending_lawyers_happy_path(self, db_with_pending_lawyer):
        """HAPPY PATH: A newly registered lawyer should appear in the pending list."""
        _, lawyer_id = db_with_pending_lawyer
        pending = auth.get_pending_lawyers()
        ids = [l["id"] for l in pending]
        assert lawyer_id in ids

    def test_approve_lawyer(self, db_with_pending_lawyer):
        """HAPPY PATH: After approval, the lawyer must no longer appear in the pending list."""
        _, lawyer_id = db_with_pending_lawyer
        auth.approve_lawyer(lawyer_id)
        pending = auth.get_pending_lawyers()
        ids = [l["id"] for l in pending]
        assert lawyer_id not in ids

    def test_approved_lawyer_status_in_db(self, db_with_pending_lawyer):
        """Approving a lawyer must set their verified_status to 'Approved' in the Users table."""
        db_path, lawyer_id = db_with_pending_lawyer
        auth.approve_lawyer(lawyer_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT verified_status FROM Users WHERE id=?", (lawyer_id,))
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "Approved"

    def test_reject_lawyer_removes_from_db(self, db_with_pending_lawyer):
        """NEGATIVE TEST: Rejecting a lawyer must delete their record from the database."""
        db_path, lawyer_id = db_with_pending_lawyer
        auth.reject_lawyer(lawyer_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE id=?", (lawyer_id,))
        row = cursor.fetchone()
        conn.close()
        assert row is None

    def test_no_pending_lawyers_returns_empty(self, temp_auth_db):
        """EDGE CASE: If there are no pending lawyers, the function must return an empty list."""
        pending = auth.get_pending_lawyers()
        assert pending == []
