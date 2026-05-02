# Testing Documentation (ReadMe)


## Testing Framework & Tools
We implemented our unit tests using **`pytest`**

---

## 1. Core Vault Management Tests (`test_vault.py`)

 securely saving and loading AI chat histories and contracts for users.

### Scenario A: Saving and Loading Chats
- **Happy Path:** A user finishes a chat with the AI. The system saves the JSON messages. When the user visits their dashboard later, the system perfectly retrieves the chat history using `load_chat()`, preserving all text.
- **Negative Test:** The system tries to load a chat using a completely random or non-existent ID. The system handles this gracefully and returns an empty list `[]` instead of throwing a database "Not Found" exception.
- **Edge Case (Upserting):** The user updates an existing chat. Instead of creating a duplicate row in the database, the system recognizes the `session_name` and safely updates the existing row. We tested this by saving the same chat twice and verifying only one row exists.
- **Edge Case (Empty Data):** A chat session is created but contains zero messages. The system safely stores the empty list and retrieves it as `[]` without corrupting the database.

---

## 2. Authentication & Validation Tests (`test_auth.py`)

These tests cover the core logic used when a citizen or lawyer tries to register or log into the application.

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
- **Edge Case:** The system encounters an old, corrupted, or completely invalid hash format in the database. Instead of crashing the application, `check_password` safely catches the exception and returns `False`.

---

## 3. RAG Vector Database Tests (`test_rag_database.py`)

Tests the data pipeline that builds the AI search engine (`brain_AI_databese(vector).py`).

### Scenario E: AI Data Pipeline
- **Happy Path:** Loading a folder with a valid Egyptian law CSV correctly parses the text and source columns into a DataFrame.
- **Edge Case (Empty Folder):** Passing an empty folder correctly returns an empty DataFrame without causing the system to crash.
- **Negative Test (Bad Data):** Passing a CSV missing the required "text" columns safely skips the file without throwing an unhandled `KeyError`.

---

## 4. Database Setup Tests (`test_database_setup.py`)

Tests the initialization of the SQLite architecture (`database_setup.py`).

### Scenario F: Architecture Initialization
- **Happy Path:** Running the setup script successfully builds all 6 required tables (Users, Vault, Appointments, etc.) and injects the default Admin account.
- **Edge Case (Idempotency):** Running the setup script *twice* does not crash or duplicate the Admin account.
- **Negative Test (Permission Denied):** Simulating a server permission error when creating the Vault folder ensures the system bubbles up the error safely rather than silently failing.

---

