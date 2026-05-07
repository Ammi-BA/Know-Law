import pytest
import os
import sys
import sqlite3
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import auth


@pytest.fixture
def temp_db_with_users():
    """
    Sets up an isolated temp database with one pre-approved citizen and one pre-approved
    lawyer, ready for appointment testing.  Yields (db_path, citizen_id, lawyer_id).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_appt.db")
        with patch('auth.DB_NAME', db_path):
            auth.init_db()

            # Register citizen
            auth.register_user(
                "Citizen", "Test Citizen", "citizen@test.com", "pass12345",
                "0100000000", 30, "Cairo", "1 Citizen St"
            )
            # Register lawyer
            auth.register_user(
                "Lawyer", "Test Lawyer", "lawyer@test.com", "pass12345",
                "0200000000", 45, "Cairo", "2 Law St",
                specialty="Civil Law", bio="Expert in civil disputes."
            )

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Users WHERE email='citizen@test.com'")
            citizen_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM Users WHERE email='lawyer@test.com'")
            lawyer_id = cursor.fetchone()[0]
            # Approve the lawyer so they appear in the directory
            cursor.execute(
                "UPDATE Users SET verified_status='Approved' WHERE id=?", (lawyer_id,)
            )
            conn.commit()
            conn.close()

            yield db_path, citizen_id, lawyer_id


# ==========================================
# APPOINTMENT SYSTEM TESTS
# ==========================================

class TestAppointments:

    def test_send_appointment_happy_path(self, temp_db_with_users):
        """HAPPY PATH: A citizen sends an appointment request and it appears in the lawyer's list."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(
            citizen_id, lawyer_id, "I need help with a property dispute."
        )
        appointments = auth.get_lawyer_appointments(lawyer_id)
        assert len(appointments) >= 1
        assert appointments[0]["message"] == "I need help with a property dispute."

    def test_new_appointment_status_is_pending(self, temp_db_with_users):
        """A freshly sent appointment must have 'Pending' as its default status."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Consultation needed.")
        appointments = auth.get_lawyer_appointments(lawyer_id)
        assert appointments[0]["status"] == "Pending"

    def test_respond_accept_appointment(self, temp_db_with_users):
        """HAPPY PATH: A lawyer accepts a request — status changes to 'Accepted'."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Accept this please.")
        appt_id = auth.get_lawyer_appointments(lawyer_id)[0]["id"]

        auth.respond_to_appointment(appt_id, "Accepted", "Available on Wednesday at 3pm.")

        updated = auth.get_lawyer_appointments(lawyer_id)
        assert updated[0]["status"] == "Accepted"
        assert updated[0]["response"] == "Available on Wednesday at 3pm."

    def test_respond_reject_appointment(self, temp_db_with_users):
        """NEGATIVE TEST: A lawyer rejects a request — status changes to 'Rejected'."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Please review my case.")
        appt_id = auth.get_lawyer_appointments(lawyer_id)[0]["id"]

        auth.respond_to_appointment(appt_id, "Rejected", "Unavailable this month.")

        updated = auth.get_lawyer_appointments(lawyer_id)
        assert updated[0]["status"] == "Rejected"
        assert updated[0]["response"] == "Unavailable this month."

    def test_citizen_sees_their_appointments(self, temp_db_with_users):
        """A citizen's sent requests must appear when querying get_citizen_appointments."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Citizen view test message.")
        citizen_appts = auth.get_citizen_appointments(citizen_id)
        assert len(citizen_appts) >= 1
        assert citizen_appts[0]["message"] == "Citizen view test message."

    def test_citizen_appointment_shows_lawyer_name(self, temp_db_with_users):
        """The citizen's appointment record must include the lawyer's name."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Name check request.")
        citizen_appts = auth.get_citizen_appointments(citizen_id)
        assert citizen_appts[0]["lawyer_name"] == "Test Lawyer"

    def test_lawyer_appointment_shows_citizen_name(self, temp_db_with_users):
        """The lawyer's appointment record must include the citizen's name."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Lawyer name check.")
        lawyer_appts = auth.get_lawyer_appointments(lawyer_id)
        assert lawyer_appts[0]["citizen_name"] == "Test Citizen"

    def test_multiple_appointments_all_returned(self, temp_db_with_users):
        """EDGE CASE: A citizen sending three requests — all three should be returned."""
        _, citizen_id, lawyer_id = temp_db_with_users
        for i in range(3):
            auth.send_appointment_request(citizen_id, lawyer_id, f"Request number {i + 1}")
        appointments = auth.get_lawyer_appointments(lawyer_id)
        assert len(appointments) == 3

    def test_get_appointments_for_unknown_lawyer_returns_empty(self, temp_db_with_users):
        """NEGATIVE TEST: Querying appointments for a non-existent lawyer ID returns []."""
        appointments = auth.get_lawyer_appointments(999999)
        assert appointments == []

    def test_get_appointments_for_unknown_citizen_returns_empty(self, temp_db_with_users):
        """NEGATIVE TEST: Querying appointments for a non-existent citizen ID returns []."""
        appointments = auth.get_citizen_appointments(999999)
        assert appointments == []

    def test_appointment_response_has_no_details_before_responding(self, temp_db_with_users):
        """EDGE CASE: A new appointment should have no response details (None) before the lawyer replies."""
        _, citizen_id, lawyer_id = temp_db_with_users
        auth.send_appointment_request(citizen_id, lawyer_id, "Still pending.")
        appointment = auth.get_lawyer_appointments(lawyer_id)[0]
        assert appointment["response"] is None
