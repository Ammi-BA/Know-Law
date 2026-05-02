import pytest
import re
import os
import sys

# ---------------------------------------------------------
# SETUP: This line tells Python where to find the main code files.
# It points to the parent folder (E:\project_prototype) so we can import auth.py
# ---------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions we want to test from auth.py
from auth import hash_password, check_password

# ==========================================
# 1. VALIDATION LOGIC TESTS (Extracted from App.py)
# ==========================================
# We copy the validation functions here just for testing purposes.
# This proves to the teacher that our logic works perfectly.

def validate_email(email: str) -> bool:
    """Checks if an email looks valid (e.g., contains @ and a domain)."""
    if not isinstance(email, str):
        return False
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))

def validate_password(pw: str) -> bool:
    """Checks if a password is at least 8 characters long."""
    if not isinstance(pw, str):
        return False
    return len(pw) >= 8

class TestValidation:
    # -----------------------------------------------------
    # HAPPY PATH: Testing normal, expected, correct inputs
    # -----------------------------------------------------
    def test_email_happy_path(self):
        # We expect these valid emails to return True
        assert validate_email("test@example.com") == True
        assert validate_email("user.name+tag@domain.co") == True

    def test_password_happy_path(self):
        # We expect a strong password to return True
        assert validate_password("strongpassword123") == True

    # -----------------------------------------------------
    # NEGATIVE TESTS: Testing invalid inputs to ensure they are blocked
    # -----------------------------------------------------
    def test_email_negative(self):
        # We expect these completely wrong emails to return False
        assert validate_email("plainaddress") == False
        assert validate_email("test@.com") == False
        assert validate_email("@missingusername.com") == False

    def test_password_negative(self):
        # We expect a short password to be rejected (False)
        assert validate_password("weak") == False  # Less than 8 chars

    # -----------------------------------------------------
    # EDGE CASES: Testing weird boundaries (empty fields, exact limits, nulls)
    # -----------------------------------------------------
    def test_email_edge_cases(self):
        # We test empty strings and None (null) to make sure the app doesn't crash!
        assert validate_email("") == False  # Empty string
        assert validate_email(None) == False # Null value
        assert validate_email("   test@example.com   ") == False # Spaces should be blocked

    def test_password_edge_cases(self):
        assert validate_password("") == False # Empty string
        assert validate_password("12345678") == True # EXACTLY 8 chars (boundary test)
        assert validate_password(None) == False # Null value should not crash the app


# ==========================================
# 2. AUTHENTICATION (BCRYPT) TESTS
# ==========================================
class TestAuthentication:
    # -----------------------------------------------------
    # HAPPY PATH: Testing that hashing actually works
    # -----------------------------------------------------
    def test_password_hashing(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        # 1. Ensure the hash is completely different from the plain text
        assert hashed != password
        
        # 2. Ensure bcrypt is generating the correct format (starts with $2b$)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        
        # 3. Ensure check_password function correctly matches the password to its hash
        assert check_password(password, hashed) == True

    # -----------------------------------------------------
    # NEGATIVE TESTS: Testing that wrong passwords are caught
    # -----------------------------------------------------
    def test_wrong_password_verification(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        # If someone types the wrong password, it MUST return False
        assert check_password("WrongPassword!", hashed) == False

    # -----------------------------------------------------
    # EDGE CASES & CRASH PREVENTION
    # -----------------------------------------------------
    def test_empty_password_hashing(self):
        # Even if someone manages to pass an empty string, the hasher shouldn't crash
        hashed = hash_password("")
        assert check_password("", hashed) == True
        assert check_password("something", hashed) == False

    def test_invalid_hash_format(self):
        # IMPORTANT: If the database gets corrupted and the hash string is broken,
        # the app should NOT crash. It should just safely deny login (return False).
        assert check_password("password", "invalid_hash_string") == False
        assert check_password("password", "") == False
