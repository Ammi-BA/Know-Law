import pytest
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import auth


@pytest.fixture
def temp_db_with_user():
    """Creates an isolated DB with a single registered citizen for password-reset testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_reset.db")
        with patch('auth.DB_NAME', db_path):
            auth.init_db()
            auth.register_user(
                "Citizen", "Reset Test User", "reset@test.com", "original123",
                "0100000000", 28, "Cairo", "Reset St"
            )
            yield db_path


# ==========================================
# 1. TOKEN CREATION TESTS
# ==========================================

class TestCreateResetToken:

    def test_create_token_happy_path(self, temp_db_with_user):
        """HAPPY PATH: A valid email produces a non-None URL-safe token string."""
        token = auth.create_password_reset_token("reset@test.com")
        assert token is not None
        assert len(token) > 10

    def test_create_token_nonexistent_email(self, temp_db_with_user):
        """NEGATIVE TEST: Requesting a token for an email not in the database must return None."""
        token = auth.create_password_reset_token("nobody@test.com")
        assert token is None

    def test_create_token_replaces_previous(self, temp_db_with_user):
        """EDGE CASE: Requesting a second token for the same email must invalidate the first."""
        token_1 = auth.create_password_reset_token("reset@test.com")
        token_2 = auth.create_password_reset_token("reset@test.com")

        # The first token should no longer be valid
        assert auth.validate_reset_token(token_1) is None
        # Only the second token should be valid
        assert auth.validate_reset_token(token_2) == "reset@test.com"

    def test_token_is_stored_in_db(self, temp_db_with_user):
        """The generated token must be persisted in the Password_Resets table."""
        token = auth.create_password_reset_token("reset@test.com")
        conn = sqlite3.connect(temp_db_with_user)
        cursor = conn.cursor()
        cursor.execute("SELECT token FROM Password_Resets WHERE token=?", (token,))
        row = cursor.fetchone()
        conn.close()
        assert row is not None


# ==========================================
# 2. TOKEN VALIDATION TESTS
# ==========================================

class TestValidateResetToken:

    def test_validate_valid_token(self, temp_db_with_user):
        """HAPPY PATH: A freshly created, unexpired token must return the correct email."""
        token = auth.create_password_reset_token("reset@test.com")
        email = auth.validate_reset_token(token)
        assert email == "reset@test.com"

    def test_validate_expired_token(self, temp_db_with_user):
        """NEGATIVE TEST: A token whose expiry is in the past must return None."""
        token = auth.create_password_reset_token("reset@test.com")

        # Manually back-date the expiry to one hour ago
        conn = sqlite3.connect(temp_db_with_user)
        cursor = conn.cursor()
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        cursor.execute(
            "UPDATE Password_Resets SET expires_at = ? WHERE token = ?",
            (past_time, token)
        )
        conn.commit()
        conn.close()

        email = auth.validate_reset_token(token)
        assert email is None

    def test_validate_completely_fake_token(self, temp_db_with_user):
        """NEGATIVE TEST: A random string that was never stored must return None."""
        email = auth.validate_reset_token("completely_fake_token_xyz_123")
        assert email is None

    def test_validate_empty_token(self, temp_db_with_user):
        """EDGE CASE: An empty string token must return None without crashing."""
        email = auth.validate_reset_token("")
        assert email is None


# ==========================================
# 3. PASSWORD RESET EXECUTION TESTS
# ==========================================

class TestResetPassword:

    def test_reset_password_happy_path(self, temp_db_with_user):
        """HAPPY PATH: A valid token allows a new password to be set."""
        token = auth.create_password_reset_token("reset@test.com")
        result = auth.reset_password(token, "newpassword456")
        assert result == True

    def test_new_password_is_functional(self, temp_db_with_user):
        """After a successful reset, the user can log in with the NEW password."""
        token = auth.create_password_reset_token("reset@test.com")
        auth.reset_password(token, "newpassword456")
        user = auth.login_user("reset@test.com", "newpassword456")
        assert user is not None

    def test_old_password_rejected_after_reset(self, temp_db_with_user):
        """After a successful reset, the OLD password must no longer work."""
        token = auth.create_password_reset_token("reset@test.com")
        auth.reset_password(token, "newpassword456")
        user = auth.login_user("reset@test.com", "original123")
        assert user is None

    def test_reset_password_invalid_token(self, temp_db_with_user):
        """NEGATIVE TEST: Attempting a reset with a fake token must return False."""
        result = auth.reset_password("invalid_token_xyz", "newpassword456")
        assert result == False

    def test_token_deleted_after_successful_reset(self, temp_db_with_user):
        """EDGE CASE: After a successful reset, the token must be consumed (deleted)."""
        token = auth.create_password_reset_token("reset@test.com")
        auth.reset_password(token, "newpassword456")
        # Trying to reuse the same token must now fail
        email = auth.validate_reset_token(token)
        assert email is None

    def test_token_cannot_be_reused(self, temp_db_with_user):
        """EDGE CASE: A token used once must not allow a second password change."""
        token = auth.create_password_reset_token("reset@test.com")
        auth.reset_password(token, "password_attempt_1")
        result = auth.reset_password(token, "password_attempt_2")
        assert result == False


# ==========================================
# 4. EMAIL SENDING TESTS
# ==========================================

class TestSendResetEmail:

    def test_send_email_not_configured(self):
        """NEGATIVE TEST: When EMAIL_SENDER is empty, the function must return (False, error msg)."""
        with patch('auth.EMAIL_SENDER', ''), patch('auth.EMAIL_PASSWORD', ''):
            success, error = auth.send_reset_email("user@test.com", "fake_token")
            assert success == False
            assert "not configured" in error.lower()

    def test_send_email_success_mocked(self):
        """HAPPY PATH: With valid credentials and a mocked SMTP server, send must return (True, '')."""
        mock_server = MagicMock()
        mock_server.__enter__ = lambda s: s
        mock_server.__exit__ = MagicMock(return_value=False)

        with patch('auth.EMAIL_SENDER', 'sender@test.com'), \
             patch('auth.EMAIL_PASSWORD', 'app_password'), \
             patch('smtplib.SMTP', return_value=mock_server):
            success, error = auth.send_reset_email("user@test.com", "valid_token_abc")
            assert success == True
            assert error == ""

    def test_send_email_authentication_failure(self):
        """NEGATIVE TEST: If SMTP auth fails, the function must return (False, error message)."""
        import smtplib
        mock_server = MagicMock()
        mock_server.__enter__ = lambda s: s
        mock_server.__exit__ = MagicMock(return_value=False)
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

        with patch('auth.EMAIL_SENDER', 'sender@test.com'), \
             patch('auth.EMAIL_PASSWORD', 'wrong_password'), \
             patch('smtplib.SMTP', return_value=mock_server):
            success, error = auth.send_reset_email("user@test.com", "some_token")
            assert success == False
            assert "authentication" in error.lower()
