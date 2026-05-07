import pytest
import os
import sys
import sqlite3
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import auth


@pytest.fixture
def temp_db_with_lawyers():
    """
    Sets up an isolated temp database containing three pre-approved lawyers:
    - Cairo / Criminal Law
    - Alexandria / Civil Law
    - Cairo / Civil Law
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_directory.db")
        with patch('auth.DB_NAME', db_path):
            auth.init_db()

            lawyers = [
                ("Cairo Criminal Lawyer",   "cairo_criminal@test.com",  "Cairo",       "Criminal Law"),
                ("Alex Civil Lawyer",        "alex_civil@test.com",      "Alexandria",  "Civil Law"),
                ("Cairo Civil Lawyer",       "cairo_civil@test.com",     "Cairo",       "Civil Law"),
            ]
            for name, email, city, specialty in lawyers:
                auth.register_user(
                    "Lawyer", name, email, "pass12345",
                    "0110000000", 38, city, "Law Street",
                    specialty=specialty, bio=f"{specialty} specialist."
                )

            # Approve all three lawyers
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET verified_status='Approved' WHERE role='Lawyer'")
            conn.commit()
            conn.close()

            yield db_path


# ==========================================
# LAWYER DIRECTORY TESTS
# ==========================================

class TestLawyerDirectory:

    def test_get_all_approved_lawyers_happy_path(self, temp_db_with_lawyers):
        """HAPPY PATH: Calling with no filters must return all approved lawyers."""
        lawyers = auth.get_approved_lawyers()
        assert len(lawyers) == 3

    def test_filter_by_city(self, temp_db_with_lawyers):
        """HAPPY PATH: Filtering by city='Cairo' must return only Cairo lawyers."""
        cairo_lawyers = auth.get_approved_lawyers(city="Cairo")
        assert len(cairo_lawyers) == 2
        for lawyer in cairo_lawyers:
            assert lawyer["city"] == "Cairo"

    def test_filter_by_specialty(self, temp_db_with_lawyers):
        """HAPPY PATH: Filtering by specialty='Civil Law' must return only civil lawyers."""
        civil_lawyers = auth.get_approved_lawyers(specialty="Civil Law")
        assert len(civil_lawyers) == 2
        for lawyer in civil_lawyers:
            assert lawyer["specialty"] == "Civil Law"

    def test_filter_by_city_and_specialty_combined(self, temp_db_with_lawyers):
        """Combining city and specialty filters must narrow results to a single match."""
        results = auth.get_approved_lawyers(city="Cairo", specialty="Civil Law")
        assert len(results) == 1
        assert results[0]["name"] == "Cairo Civil Lawyer"

    def test_search_by_name_partial_match(self, temp_db_with_lawyers):
        """Search must support partial name matching (LIKE %query%)."""
        results = auth.get_approved_lawyers(search="Alex")
        assert len(results) == 1
        assert "Alex" in results[0]["name"]

    def test_filter_returns_empty_for_nonexistent_city(self, temp_db_with_lawyers):
        """NEGATIVE TEST: Filtering by a city with no lawyers must return an empty list."""
        results = auth.get_approved_lawyers(city="Aswan")
        assert results == []

    def test_filter_returns_empty_for_nonexistent_specialty(self, temp_db_with_lawyers):
        """NEGATIVE TEST: Filtering by a specialty that no approved lawyer holds returns []."""
        results = auth.get_approved_lawyers(specialty="Maritime Law")
        assert results == []

    def test_pending_lawyer_excluded_from_directory(self, temp_db_with_lawyers):
        """NEGATIVE TEST: A newly registered (Pending) lawyer must NOT appear in directory results."""
        auth.register_user(
            "Lawyer", "Still Pending", "pending@test.com", "pass12345",
            "0199999999", 30, "Cairo", "Pending Blvd",
            specialty="Family Law", bio="Pending."
        )
        lawyers = auth.get_approved_lawyers()
        names = [l["name"] for l in lawyers]
        assert "Still Pending" not in names

    def test_result_contains_required_fields(self, temp_db_with_lawyers):
        """EDGE CASE: Every returned lawyer dict must include all expected keys."""
        lawyers = auth.get_approved_lawyers()
        required_keys = {"id", "name", "city", "phone", "specialty", "bio"}
        for lawyer in lawyers:
            assert required_keys.issubset(lawyer.keys()), (
                f"Missing keys in lawyer record: {required_keys - lawyer.keys()}"
            )

    def test_search_is_case_insensitive_in_sql(self, temp_db_with_lawyers):
        """EDGE CASE: Name search should work regardless of how the name was stored (LIKE matching)."""
        # 'cairo' lowercase should still match 'Cairo Criminal Lawyer'
        results = auth.get_approved_lawyers(search="cairo")
        assert len(results) >= 1

    def test_empty_database_returns_empty_list(self):
        """EDGE CASE: A fresh database with no approved lawyers must return an empty list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "empty_dir.db")
            with patch('auth.DB_NAME', db_path):
                auth.init_db()
                results = auth.get_approved_lawyers()
                assert results == []
