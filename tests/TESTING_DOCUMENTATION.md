# Testing Documentation

## Testing Framework & Tools

We implemented all unit tests using **`pytest`**.  
Each test file uses **temporary, isolated SQLite databases** (via `pytest` fixtures and `unittest.mock.patch`) so tests never touch the real `knowlaw.db` and can be run in any order without side-effects.

---

## Test Files Overview

| File | Module Under Test | Tests |
|------|-------------------|-------|
| `test_auth.py` | `auth.py` | Email/password validation, bcrypt hashing, legacy SHA-256 |
| `test_vault.py` | `vault_manager.py` | Save/load chats, upsert, empty data, session-type filtering |
| `test_database_setup.py` | `database_setup.py` | Schema creation, idempotency, permission error |
| `test_rag_database.py` | `brain_AI_databese(vector).py` | CSV loading, empty folder, bad columns |
| `test_user_management.py` | `auth.py` | Register, login, admin approval/rejection |
| `test_appointments.py` | `auth.py` | Full appointment lifecycle, status transitions |
| `test_password_reset.py` | `auth.py` | Token creation, expiry, reset execution, email sending |
| `test_lawyer_directory.py` | `auth.py` | Directory search, city/specialty filters |
| `test_vault_extended.py` | `vault_manager.py` | Delete chat, Arabic content, session isolation, ordering |

---

## 1. Core Vault Management Tests (`test_vault.py`)

Covers secure saving and loading of AI chat histories.

### Scenario A: Saving and Loading Chats
- **Happy Path:** A user finishes a chat with the AI. The system saves the JSON messages. When the user visits their dashboard later, the system perfectly retrieves the chat history using `load_chat()`, preserving all text.
- **Negative Test:** The system tries to load a chat using a completely random or non-existent ID. The system handles this gracefully and returns an empty list `[]` instead of throwing a database "Not Found" exception.
- **Edge Case (Upserting):** The user updates an existing chat. Instead of creating a duplicate row in the database, the system recognizes the `session_name` and safely updates the existing row. We tested this by saving the same chat twice and verifying only one row exists.
- **Edge Case (Empty Data):** A chat session is created but contains zero messages. The system safely stores the empty list and retrieves it as `[]` without corrupting the database.

---

## 2. Authentication & Validation Tests (`test_auth.py`)

Core logic used when a citizen or lawyer registers or logs in.

### Scenario B: Email Validation
- **Happy Path:** The user enters a standard email like `test@example.com`. The system returns `True` and accepts the registration.
- **Negative Test:** The user accidentally types `plainaddress` (missing the @ symbol and domain). The system catches this, returns `False`, and blocks registration.
- **Edge Case:** The user submits a completely empty string `""` or a null `None` value. The system does not crash; it safely returns `False`.

### Scenario C: Password Validation
- **Happy Path:** The user types a strong password like `strongpassword123`. The system sees it is over 8 characters and returns `True`.
- **Negative Test:** The user types `weak`. The system rejects it for being under 8 characters and returns `False`.
- **Edge Case:** The user submits exactly 8 characters `12345678`. The system correctly accepts it (`True`). If the user submits `None`, the system safely rejects it without throwing a Python error.

### Scenario D: Password Hashing (bcrypt)
- **Happy Path:** The system receives a password during registration. It generates a complex `$2b$` bcrypt hash. When the user logs in with the same password, the `check_password` function returns `True`.
- **Negative Test:** The user tries to log in with `WrongPassword!`. The `check_password` function correctly returns `False` and blocks login.
- **Edge Case (Corrupted Hash):** The system encounters an old, corrupted, or completely invalid hash format in the database. Instead of crashing the application, `check_password` safely catches the exception and returns `False`.
- **Edge Case (Legacy SHA-256):** Accounts created before bcrypt was adopted are stored as SHA-256 hex digests. The `check_password` function detects the absence of the `$2b$` prefix and falls back to SHA-256 comparison, so existing users are not locked out after the upgrade.

---

## 3. RAG Vector Database Tests (`test_rag_database.py`)

Tests the data pipeline that builds the AI search engine.

### Scenario E: AI Data Pipeline
- **Happy Path:** Loading a folder with a valid Egyptian law CSV correctly parses the text and source columns into a DataFrame.
- **Edge Case (Empty Folder):** Passing an empty folder correctly returns an empty DataFrame without causing the system to crash.
- **Negative Test (Bad Data):** Passing a CSV missing the required "text" columns safely skips the file without throwing an unhandled `KeyError`.

---

## 4. Database Setup Tests (`test_database_setup.py`)

Tests the initialization of the SQLite architecture.

### Scenario F: Architecture Initialization
- **Happy Path:** Running the setup script successfully builds all 6 required tables (Users, Vault, Appointments, etc.) and injects the default Admin account.
- **Edge Case (Idempotency):** Running the setup script *twice* does not crash or duplicate the Admin account.
- **Negative Test (Permission Denied):** Simulating a server permission error when creating the Vault folder ensures the system bubbles up the error safely rather than silently failing.

---

## 5. User Registration & Login Tests (`test_user_management.py`)

End-to-end tests for the registration and login flows, with an isolated temp database.

### Scenario G: User Registration
- **Happy Path (Citizen):** A new citizen registers with valid data. `register_user()` returns `True` and the account is immediately set to `Approved`.
- **Happy Path (Lawyer):** A lawyer registers with a specialty and bio. `register_user()` returns `True` and the account is set to `Pending` awaiting admin review.
- **Negative Test (Duplicate Email):** Attempting to register a second account with an already-used email returns `False` without throwing an unhandled database exception.
- **Edge Case (Lawyer Profile Row):** Registering a lawyer must also create a corresponding row in the `Lawyer_Profiles` table with the correct specialty.
- **Edge Case (Default Specialty):** If a lawyer registers without specifying a specialty, the value defaults to `"Not Specified"` rather than inserting `NULL`.

### Scenario H: User Login
- **Happy Path:** A registered citizen logs in with the correct password. The function returns a dict containing the correct `role` and `full_name`.
- **Negative Test (Wrong Password):** Logging in with the correct email but wrong password returns `None`.
- **Negative Test (Nonexistent Email):** Logging in with an email that was never registered returns `None` without crashing.
- **Edge Case (Admin Login):** The default Admin account injected by `init_db()` must be immediately usable — login with `admin@knowlaw.com` / `admin123` must succeed.

### Scenario I: Admin Lawyer Approval Workflow
- **Happy Path (Approve):** After `approve_lawyer(id)` is called, the lawyer no longer appears in `get_pending_lawyers()` and their `verified_status` in the Users table is `"Approved"`.
- **Negative Test (Reject):** After `reject_lawyer(id)` is called, the lawyer's record is completely removed from both `Users` and `Lawyer_Profiles` tables.
- **Edge Case (No Pending Lawyers):** `get_pending_lawyers()` returns an empty list when no lawyers are awaiting review.

---

## 6. Appointment System Tests (`test_appointments.py`)

Full lifecycle tests for the citizen–lawyer appointment workflow.

### Scenario J: Appointment Lifecycle
- **Happy Path (Create):** A citizen calls `send_appointment_request()`. The appointment immediately appears in `get_lawyer_appointments()` with a `status` of `"Pending"` and `response` of `None`.
- **Happy Path (Accept):** A lawyer calls `respond_to_appointment()` with status `"Accepted"`. The appointment record is updated; `get_lawyer_appointments()` returns `"Accepted"` and the response text.
- **Negative Test (Reject):** The lawyer calls `respond_to_appointment()` with status `"Rejected"`. The record reflects `"Rejected"` and the reason text.
- **Citizen View:** `get_citizen_appointments()` returns the same appointment from the citizen's perspective, including the lawyer's name.
- **Lawyer View:** `get_lawyer_appointments()` returns the appointment with the citizen's name.
- **Multiple Appointments:** Sending three requests creates three separate appointment records, all returned by a single query.
- **Edge Case (No Appointments):** Querying by a user ID that has no appointments returns `[]` without any database exception.
- **Edge Case (No Response Yet):** A new appointment must have a `None` response field before the lawyer has replied.

---

## 7. Password Reset Flow Tests (`test_password_reset.py`)

Token-based password reset covering creation, validation, execution, and email sending.

### Scenario K: Token Creation
- **Happy Path:** `create_password_reset_token()` for a registered email returns a non-empty URL-safe token string that is persisted in the `Password_Resets` table.
- **Negative Test:** Calling the function with an email that does not exist in the database returns `None`.
- **Edge Case (Replacement):** Requesting a second token for the same email invalidates the first token; only the newest token remains valid.

### Scenario L: Token Validation
- **Happy Path:** `validate_reset_token()` with a freshly created token returns the correct email address.
- **Negative Test (Expired):** A token whose `expires_at` timestamp has been manually back-dated to the past returns `None`.
- **Negative Test (Fake Token):** A random string that was never stored in the database returns `None`.
- **Edge Case (Empty String):** An empty-string token returns `None` without raising an exception.

### Scenario M: Reset Execution
- **Happy Path:** `reset_password()` with a valid token returns `True`, and the user can subsequently log in with the new password.
- **Old Password Blocked:** After a successful reset, the old password is rejected by `login_user()`.
- **Token Consumed:** The token is deleted from `Password_Resets` after a successful reset; attempting to reuse it returns `False`.
- **Negative Test (Invalid Token):** `reset_password()` with a fake token returns `False` and leaves the password unchanged.

### Scenario N: Email Sending
- **Negative Test (Not Configured):** When `EMAIL_SENDER` is empty, `send_reset_email()` immediately returns `(False, "…not configured…")` without attempting a network connection.
- **Happy Path (Mocked SMTP):** With `smtplib.SMTP` mocked, the function completes and returns `(True, "")`.
- **Negative Test (Auth Failure):** When the mocked SMTP server raises `SMTPAuthenticationError`, the function returns `(False, "…authentication…")`.

---

## 8. Lawyer Directory Tests (`test_lawyer_directory.py`)

Search and filter functionality for the public lawyer directory.

### Scenario O: Directory Search & Filtering
- **Happy Path (No Filters):** `get_approved_lawyers()` with no arguments returns all approved lawyers.
- **Filter by City:** Passing `city="Cairo"` returns only lawyers located in Cairo.
- **Filter by Specialty:** Passing `specialty="Civil Law"` returns only civil lawyers.
- **Combined Filter:** Passing both `city` and `specialty` narrows the result to a single matching lawyer.
- **Name Search:** The `search` parameter performs a partial, case-insensitive name match (`LIKE %query%`).
- **Negative Test (Non-existent City):** Filtering by a city with no lawyers returns `[]`.
- **Negative Test (Non-existent Specialty):** Filtering by a specialty no approved lawyer holds returns `[]`.
- **Pending Excluded:** A lawyer in `Pending` status must never appear in the directory results.
- **Edge Case (Required Fields):** Every record returned must contain all required keys: `id`, `name`, `city`, `phone`, `specialty`, `bio`.
- **Edge Case (Empty Database):** A freshly initialized database with no approved lawyers returns `[]`.

---

## 9. Extended Vault Tests (`test_vault_extended.py`)

Additional tests for deletion, Arabic content, session isolation, and result ordering.

### Scenario P: Chat Deletion
- **Happy Path:** Calling `delete_chat(id)` makes `load_chat(id)` return `[]` and removes the entry from `get_user_chats()`.
- **Selective Delete:** Deleting one session leaves all other sessions for the same user intact.
- **Edge Case (Non-existent ID):** Deleting an ID that was never stored must complete silently without raising any exception.

### Scenario Q: Arabic & Special Character Content
- **Arabic Preservation:** Messages containing full Arabic text (e.g., "ما هو قانون العقوبات؟") are stored and retrieved byte-for-byte identically, with no encoding corruption.
- **Mixed Arabic/English:** Messages mixing Arabic and Latin characters, plus Arabic-Indic numerals, survive the JSON serialisation/deserialisation round-trip without change.
- **Special Characters:** Messages containing JSON-sensitive characters (`"`, `'`, `—`, `©`) are preserved exactly after save and load.

### Scenario R: Session Type Isolation
- **All Types Independent:** Saving one `chat`, one `ocr`, and one `contract` session for the same user — each type's `get_user_chats()` call returns exactly one record.
- **Negative Test (Wrong Type):** Querying a session type the user never used returns `[]`.
- **Same Name, Different Types:** Two sessions with the same `session_name` but different `session_type` values coexist without collision; loading each by ID returns its own content.

### Scenario S: Result Ordering
- **Newest First:** `get_user_chats()` returns sessions sorted by `updated_at` descending — the most recently saved session is always at index 0.
- **Upsert Reorders:** When an older session is upserted (saved again), its `updated_at` timestamp is refreshed and it moves to the top of the list.

---
