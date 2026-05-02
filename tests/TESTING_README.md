# 🧪 KnowLaw AI - Testing README

This document is written specifically for you and your team to understand exactly **how the testing code works**. If your teacher asks you "How do these tests work?", you can use this guide to answer confidently!

---

## 🔑 The Golden Rule of Testing: `assert`
If you look at the code inside `test_auth.py` or `test_vault.py`, you will see the word `assert` everywhere. 

**What does `assert` mean?**
`assert` is just Python's way of saying: *"I swear this statement is True. If it is False, crash the test and show a RED FAILED error."*

**Example:**
```python
assert 1 + 1 == 2  # Pytest says "Correct!" (Green PASSED)
assert 1 + 1 == 5  # Pytest says "Wrong!" (Red FAILED)
```

We use `assert` to test our functions. We feed our function fake data, and we `assert` what we expect the answer to be.

---

## 📄 File 1: `test_auth.py` (Validation & Security)
This file tests two things: Input Validation (Emails/Passwords) and Security (Password Hashing).

### Part A: How to read the Validation Tests
Look at this code from the file:
```python
def test_email_happy_path(self):
    assert validate_email("test@example.com") == True
```
- **What it means:** We are swearing (`assert`) that if we give the `validate_email` function a perfect email, it MUST return `True`.

Look at the Negative Test:
```python
def test_email_negative(self):
    assert validate_email("plainaddress") == False
```
- **What it means:** We are swearing (`assert`) that if we give it garbage text (`"plainaddress"`), it MUST return `False` and reject the user.

### Part B: How to read the Security Tests
Look at this code:
```python
def test_password_hashing(self):
    password = "SecurePassword123!"
    hashed = hash_password(password)
    
    assert hashed != password
```
- **What it means:** We generate a hash from a password. Then we `assert hashed != password`. We are swearing that the database version (`hashed`) does **NOT** equal the plain text version. This proves to the teacher that we are protecting user passwords!

---

## 📄 File 2: `test_vault.py` (Database & Memory)
This file tests how the AI saves and remembers chats. It is slightly more complex because it actually talks to the database.

### 1. The Setup & Teardown (Safety First!)
At the very top of `test_vault.py`, you will see `setup_module` and `teardown_module`.
- **`setup_module`**: Runs before the tests start to make sure the database tables exist.
- **`teardown_module`**: This is crucial. It runs after the tests finish and **deletes the fake test user data** from the database so we don't permanently fill your real database with junk data!

### 2. How to read the Happy Path Vault test
```python
def test_save_and_load_chat_happy_path(self):
    session_name = "Test Legal Case"
    messages = [{"role": "user", "content": "Hello"}]
    
    # 1. We save the chat
    vault_manager.save_chat(TEST_USER_ID, session_name, messages, session_type="chat")
    
    # ... later in the code ...
    
    # 2. We load the chat and assert it's correct
    loaded_messages = vault_manager.load_chat(chat_id)
    assert loaded_messages[0]["content"] == "Hello"
```
- **What it means:** We save the word "Hello" to the database. We load it back out. We `assert` that the text we pulled out is still exactly "Hello". This proves data is not getting corrupted in the SQLite database.

### 3. How to read the Edge Case Upsert test
```python
def test_update_existing_chat(self):
    # We save a chat once...
    vault_manager.save_chat(TEST_USER_ID, session_name, messages_v1, session_type="ocr")
    # We save the SAME chat again...
    vault_manager.save_chat(TEST_USER_ID, session_name, messages_v2, session_type="ocr")
    
    # ... we pull the database rows ...
    assert len(upsert_chats) == 1
```
- **What it means:** If a user sends 5 messages in the same AI chat, we don't want to create 5 different database rows. We want to update 1 row. By saving twice and then `assert len(upsert_chats) == 1`, we prove to the teacher that our database updating (Upserting) works flawlessly without creating duplicates!

---

## 📄 File 3: `test_rag_database.py` (AI Search Engine)
This file tests the "Brain" of your RAG system: `brain_AI_databese(vector).py`. It proves to the teacher that your AI can safely read the CSV law files.

### 1. How to read the Edge Case test
Look at this code:
```python
def test_load_all_csvs_edge_case_empty(temp_csv_dir):
    df_result = brain_ai.load_all_csvs(temp_csv_dir)
    assert df_result.empty
```
- **What it means:** We trick the AI by giving it a completely empty folder (`temp_csv_dir`). If the code was badly written, it would crash when trying to read files that don't exist. By using `assert df_result.empty`, we swear that the AI gracefully handles this by returning an empty DataFrame instead of throwing a Python crash error.

### 2. How to read the Negative Test (Bad Data)
```python
def test_load_all_csvs_negative_bad_columns(temp_csv_dir):
    df_result = brain_ai.load_all_csvs(temp_csv_dir)
    assert df_result.empty
```
- **What it means:** We trick the AI by giving it a CSV file that is missing the actual "text" column. We swear (`assert`) that the AI recognizes the file is useless and skips it safely.

---

## 📄 File 4: `test_database_setup.py` (SQLite Architecture)
This file tests `database_setup.py` to ensure your backend tables are created flawlessly. It uses a very advanced Python technique called **"Mocking"** (`unittest.mock.patch`).

### 1. Why do we Mock?
If we ran the setup test on your real `knowlaw.db`, it might accidentally overwrite real user data! So, we use `@patch('database_setup.DB_NAME', db_path)` to **force** the script to create a fake, temporary database instead. This shows the teacher you know how to write safe backend tests.

### 2. How to read the Idempotency Test
```python
def test_setup_database_edge_case_idempotency(temp_db_env):
    database_setup.setup_database() # Run 1
    database_setup.setup_database() # Run 2
    
    assert admin_count == 1
```
- **What it means:** "Idempotency" is a fancy programming word that means "running something twice shouldn't break it." We literally run the setup script twice in a row. Then we `assert admin_count == 1` to prove that it didn't accidentally create two System Admin accounts!

---

### Summary for your Teacher
If asked, tell her: *"We used `pytest` to write automated scripts. Each script feeds a specific scenario (Happy Path, Negative, Edge Case) into our core functions and uses Python's `assert` keyword to mathematically prove that the output matches our exact expectations. We also used `unittest.mock` to safely isolate our database tests from our production data."*
