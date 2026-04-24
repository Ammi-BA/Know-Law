# KnowLaw AI — System Architecture Plan
## How the Entire Project Works — Full Technical Explanation

**Project:** KnowLaw AI  
**Student:** [Your Name]  
**Date:** April 2026

---

## Current Active Model Status

> Both fine-tuned models are now **fully integrated and active** in the running application. The base BGE-M3 is no longer used.

```
ACTIVE MODEL 1 — FINE-TUNED BGE-M3 (Egyptian Law Adapted)
  Path:   fine_tuning/outputs/bge_m3_finetuned/model/
  Used in: App.py → load_engine() → embedding model for all retrieval
           brain_AI_databese(vector).py → builds the law_db/ vector database
  Job:    Converts every law article and user question to a 1,024-number vector
  Improvement: MRR +49.63% over the base BAAI/bge-m3 model
  Status: ✅ ACTIVE — replaces base BGE-M3 completely

ACTIVE MODEL 2 — FINE-TUNED ARABERT v2 (Legal Classifier)
  Path:   fine_tuning/outputs/best_model/
  Used in: App.py → classify_question() → called for every chatbot message
  Job:    Reads the user's question → predicts which of 18 law categories it belongs to
           → Shows "📚 Legal Area: Landlord & Tenant Law" badge before every answer
  Accuracy: 91.23% on test set, Macro F1 = 0.839
  Status: ✅ ACTIVE — runs on every question automatically

RETIRED — BASE BGE-M3 (BAAI/bge-m3)
  Status: ❌ No longer used in the application
  Note:   Used during the benchmarking phase to select the best base model.
          The fine-tuned version replaced it entirely.
```

**How both models work together in the chatbot (every question):**
```
User question:  "ما هي حقوق المستأجر إذا أخل المؤجر بعقد الإيجار؟"
       │
       ├─► FINE-TUNED ARABERT ──► "📚 Legal Area: Landlord & Tenant Law"  (shown instantly)
       │
       └─► FINE-TUNED BGE-M3 ──► 1,024-vector ──► Chroma DB search
                                       │
                                  Top 5 law articles (retrieved)
                                       │
                                  Llama 3 8B reads articles + generates answer
                                       │
                                  Streamed response to user
```

---

## Q: "Why did we need the base BGE-M3 at all?"

The base model was used in **Phase 1 (benchmarking)**: we tested BAAI/bge-m3 vs multilingual-e5-large vs mpnet-base-v2 to pick the best architecture. BGE-M3 won. Then in **Phase 2 (fine-tuning)**, we took the winning architecture and trained it further on Egyptian law data. The base model was a stepping stone — the fine-tuned version is the final product.

---



## System Overview

KnowLaw AI is a Streamlit web app that serves as an AI-powered legal assistant for Egyptian citizens. It runs entirely locally — no external API calls, no internet for inference.

### User Roles
| Role | Capabilities |
|---|---|
| **Citizen** | Chatbot, document analysis, contract generation, lawyer directory, appointments |
| **Lawyer** | Manage appointment requests, use all AI tools |
| **Admin** | Approve/reject lawyer registrations, view pending accounts |

---

## Background Process Flow — Every Feature Explained

### PROCESS 1: User Registration

**What you see:** A form asking for name, email, password, city, etc.

**What happens in the background:**

```
Step 1: User fills form and clicks "Create Account"
        → Streamlit sends form data to Python

Step 2: validate_email() checks format with regex pattern
        validate_password() checks length ≥ 8 characters
        → If invalid: show error, stop here

Step 3: auth.register_user() is called:
        → bcrypt.hashpw(password, bcrypt.gensalt())
           Generates a unique salt + hashes the password
           Result: "$2b$12$..." — a 60-character bcrypt string
           The original password is NEVER stored

Step 4: SQLite INSERT into Users table:
        INSERT INTO Users (role, full_name, email, password_hash, ...) VALUES (...)
        → If email already exists: IntegrityError → "email already registered"
        → If role = "Lawyer": also INSERT into Lawyer_Profiles with specialty + bio
                               AND set verified_status = 'Pending'
        → If role = "Citizen": set verified_status = 'Approved' immediately

Step 5: Return True → show success message
```

---

### PROCESS 2: User Login

**What you see:** Email + password fields, Login button.

**Background flow:**

```
Step 1: User enters email + password, clicks Login

Step 2: auth.login_user(email, password) called:
        → SELECT id, role, full_name, verified_status, password_hash
          FROM Users WHERE email = ?
        → If no row found: return None → "Incorrect email or password"

Step 3: check_password(plain, stored_hash):
        → If stored_hash starts with "$2b$": bcrypt.checkpw(plain, hash)
          (modern bcrypt comparison — timing-safe, can't be brute-forced easily)
        → If stored_hash is 64 hex chars: SHA-256 fallback (legacy accounts)
        → Returns True or False

Step 4: If True AND status == 'Approved':
        → Set st.session_state.logged_in = True
        → Set st.session_state.user_info = {id, role, full_name, status}
        → st.rerun() — page reloads, now shows the dashboard

Step 5: If status == 'Pending' (Lawyer):
        → Show "awaiting admin approval" warning, don't log in
```

---

### PROCESS 3: Password Reset via Email

**What you see:** "Forgot password?" button under login form.

**Background flow:**

```
Step 1: User clicks "Forgot password?" → email input appears

Step 2: User enters email → auth.create_password_reset_token(email):
        → SELECT from Users WHERE email = ? → check if email exists
        → secrets.token_urlsafe(32) → generate 43-character secure token
          Example: "xK9mN2pL8qR5vW1jY4tA7cF0eH3bU6sI_dGzXnOm"
        → DELETE any existing token for this email (only 1 active at a time)
        → INSERT INTO Password_Resets (email, token, expires_at=now+30min)

Step 3: auth.send_reset_email(email, token):
        → Build reset URL: http://localhost:8501/?reset_token=xK9m...
        → Create HTML email with button linking to that URL
        → smtplib.SMTP("smtp.gmail.com", 587)
          → server.starttls()  (encrypt the connection)
          → server.login(EMAIL_SENDER, EMAIL_PASSWORD)
          → server.sendmail() → email arrives in user's inbox

Step 4: User clicks link in email
        → Browser opens: http://localhost:8501/?reset_token=xK9m...
        → App reads st.query_params["reset_token"]
        → Stores token in session_state, clears URL params

Step 5: App detects pending_reset_token in session_state:
        → auth.validate_reset_token(token):
           SELECT email, expires_at FROM Password_Resets WHERE token = ?
           Compare expires_at with datetime.utcnow()
           → If expired: show "link expired" error
           → If valid: show "set new password" form

Step 6: User enters new password:
        → auth.reset_password(token, new_password):
           hash_password(new_password) → bcrypt hash
           UPDATE Users SET password_hash = ? WHERE email = ?
           DELETE FROM Password_Resets WHERE token = ?
        → Password updated, user directed to login
```

---

### PROCESS 4: Legal Chatbot (RAG Pipeline)

**What you see:** A chat interface where you type a question and get a legal answer.

**Background flow — this is the core of the system:**

```
PREREQUISITE (done once before app runs):
  brain_AI_databese(vector).py reads all 18 CSV files (5,340 law articles)
  Each article → BGE-M3 model → 1,024-dimensional vector
  All vectors stored in Chroma DB (law_db/ folder)

RUNTIME — when user sends a message:

Step 1: User types: "ما هي حقوق المستأجر إذا أخل المؤجر بعقد الإيجار؟"
        Message added to messages list, st.rerun() triggers response

Step 1.5: ARABERT CLASSIFICATION — UI Legal Badge:
        classify_question(query) determines the legal area.
        → If lang != "ar", passing to Llama 3 first: "Translate this to Arabic"
        → Feeds the Arabic translation into AraBERT to predict the correct legal category
        → Displays the badge (e.g. 📚 Legal Area: Labor Law)

Step 2: load_engine() returns cached (embedding_model, llm)
        get_vector_db(embedding_model) returns the pre-built Chroma DB
        vectorstore = Chroma(persist_directory="law_db", embedding_function=bge_m3)

Step 3: RETRIEVAL — find relevant law articles:
        embedding_model.embed_query("ما هي حقوق المستأجر...")
        → Fine-tuned BGE-M3 converts the question to a 1,024-number vector
        
        vectorstore.as_retriever(search_kwargs={"k": 5}).invoke(question)
        → Chroma calculates cosine similarity between query vector and all 5,340 stored vectors
        → cosine_similarity(A, B) = (A · B) / (|A| × |B|)
        → Returns top 5 law articles (highest similarity scores)

Step 4: CONVERSATIONAL MEMORY — build context-aware prompt:
        get_legal_prompt(query, history=messages_general)
        → Takes the last 4 messages from the session state
        → Escapes { } in history text to avoid LangChain template crashes
        → Injects them as "previous conversation" context into the system prompt
        → This allows follow-up questions like "اشرح أكثر" or "Give me an example"
        → Also instructs the LLM to output a **المصادر:** (Sources) section at the end

Step 5: CONTEXT BUILDING — assemble the prompt:
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        Prompt template filled with:
          - Chat history (last 4 messages, escaped)
          - Retrieved law articles as context
          - The current question
          - Rules enforcing citations and disclaimer

Step 6: GENERATION — Llama 3 8B reads the prompt:
        llm.stream(prompt) opens a streaming connection to Ollama (running locally)
        Ollama runs Llama 3 8B on GPU
        → Graceful Offline Check: wrapped in a try...except Exception net
        → If Ollama is off, catches ConnectionError cleanly and alerts the user
        → If online, Tokens generated one by one → streamed to the browser in real-time
        Each chunk: box.markdown(full_response + "▌")

Step 7: Response complete → save to chat history:
        vault_manager.save_chat(user_id, session_name, messages, session_type="chat")
        → JSON serialises the full message list
        → User can reload this conversation later from the visible 'Past Chats' expander on the page.
```

---

### PROCESS 5: Document Analysis (OCR + In-Memory RAG)

**What you see:** Upload a PDF or image, then ask questions about it.

**Background flow:**

```
Step 1: User uploads file (PDF or image):
        uploaded_file = st.file_uploader(...)
        → Check file extension

Step 2a: If PDF (.pdf):
         pypdf.PdfReader(uploaded_file)
         text = "".join([page.extract_text() for page in reader.pages])
         → Extracts text directly (no OCR needed for digital PDFs)

Step 2b: If Image (.jpg / .jpeg / .png):
         image = Image.open(uploaded_file)  ← PIL/Pillow opens the image
         text = pytesseract.image_to_string(image, lang="ara+eng")
         → Tesseract loads Arabic+English language models (tessdata/ara.traineddata)
         → LSTM neural network reads the image pixel by pixel
         → Outputs Unicode Arabic text
         → Handles right-to-left Arabic reading direction

Step 3: Text splitting:
         RecursiveCharacterTextSplitter(chunk_size=800, overlap=100)
         → Splits the full extracted text into overlapping chunks of ~800 characters
         → Overlap of 100 chars ensures no law article is split mid-sentence

Step 4: In-memory vector DB for this document:
         BGE-M3 embeds each chunk → vector
         Chroma.from_documents(chunks, embedding_model)
         → Creates a TEMPORARY in-memory database (NOT saved to disk)
         → Stored in st.session_state.active_doc_retriever
         → Deleted when user uploads a new document or leaves the page

Step 5: User asks a question about the document:
         → Same RAG pipeline as Process 4 but uses the in-memory DB
         → The strict KnowLaw system prompt is used:
            "استند فقط وحصريًا على النصوص الموجودة في السياق أدناه"
            (Answer ONLY from the uploaded document — no external knowledge)
         → Llama 3 streams the answer

Step 6: Rapid Summarization (Optional shortcut):
         → User clicks "✨ Summarize Document"
         → Appended prompt: "قم بتلخيص هذا المستند بوضوح واذكر أبرز النقاط الأساسية..."
         → Llama-3 bypasses chat input and instantly streams a summarized breakdown of the legal text
         → Session saved with session_type="ocr" in DB.
```

---

### PROCESS 6: Contract Generation

**What you see:** A form with specific fields per contract type (parties, amounts, dates, etc.)

**Background flow:**

```
Step 1: User selects contract type and fills all fields:
        - Lease: landlord, tenant, property address, rent, duration, deposit, etc.
        - Employment: employer, employee, job title, salary, hours, leave, etc.
        - Sales: seller, buyer, item description, price, payment method, etc.
        - Contractor: client, contractor, project description, value, timeline, etc.

Step 2: Validation:
        required_ok = all mandatory fields (marked *) are non-empty
        → If missing fields: show error, do not proceed

Step 3: Structured Prompt assembly (Arabic or English):
        User selects language (Arabic / English) from the UI toggle.
        All field values are injected into the dynamic language-specific template:
        If Arabic: "أنت محامي متخصص... صغ عقد إيجار كاملاً..."
        If English: "You are an expert lawyer... Draft a complete Legal Lease Contract..."
        - Landlord: Ahmed Mohamed
        - Tenant: Sara Ali
        - Rent: 5000 EGP
        - etc.

Step 4: Llama 3 8B generates the contract:
        llm.stream(prompt) → Ollama → GPU → streamed tokens
        No retrieval used here — Llama uses its training knowledge of
        Egyptian contract law, guided strictly by the structured prompt
        → The more fields filled, the more legally complete the contract

Step 5: Download:
        full_contract.encode("utf-8") → .txt file
        Filename: e.g. "Lease_Ahmed Mohamed_Sara Ali.txt"
        → User downloads and can print + sign the contract
```

---

### PROCESS 7: Lawyer Appointments

**What you see:** Citizen sends a request to a lawyer; lawyer sees it on their dashboard.

**Background flow:**

```
CITIZEN SIDE:
Step 1: Citizen browses directory (SELECT from Users + Lawyer_Profiles
        WHERE role='Lawyer' AND verified_status='Approved')
        → Filter by city, specialty, name search applied in SQL WHERE clauses

Step 2: Citizen clicks "Request Appointment" on a lawyer card
        → Text area for message opens

Step 3: auth.send_appointment_request(citizen_id, lawyer_id, message):
        INSERT INTO Appointments (citizen_id, lawyer_id, request_message, status='Pending')
        → Row saved in SQLite

LAWYER SIDE:
Step 4: Lawyer logs in → appointments page
        auth.get_lawyer_appointments(lawyer_id):
        SELECT a.*, u.full_name, u.phone FROM Appointments a
        JOIN Users u ON a.citizen_id = u.id
        WHERE a.lawyer_id = ? ORDER BY created_at DESC

Step 5: Lawyer sees the request:
        - Clicks "✅ Accept" → form submit with note
        - Clicks "❌ Decline" → form submit with note
        auth.respond_to_appointment(appt_id, "Accepted", note):
        UPDATE Appointments SET status='Accepted', response_details=note WHERE id=?

Step 6: Citizen refreshes appointments page:
        auth.get_citizen_appointments(citizen_id)
        → Same query but from citizen's side
        → Green "Accepted" / Red "Declined" badge visible
        → Lawyer's response note shown
```

---

### PROCESS 8: Fine-Tuning 1 — BGE-M3 Domain Adaptation

**Script:** `fine_tuning/bge_m3_finetune.py`

**Background flow:**

```
Step 1: Load all 18 law CSVs from cleaned_datasets/
        → Create (source_label, article_text) training pairs
        → Each pair = one positive training example
        → 1,500 pairs created → 1,275 train / 225 validation (85/15 split)

Step 2: Load base BAAI/bge-m3 model into GPU memory (~2.1 GB VRAM)

Step 3: Training loop — MultipleNegativesRankingLoss (Contrastive Learning):
        For each batch of 4 pairs:
          [("Civil Law Art. 1", "يسري هذا القانون..."),
           ("Penalty Law Art. 5", "يعاقب بالحبس..."),
           ...]
        
        The model encodes both anchor (label) and positive (text) → vectors
        
        Loss formula (InfoNCE):
          For each anchor i:
            L_i = -log( sim(anchor_i, positive_i) / Σ sim(anchor_i, all_j) )
          
          sim() = cosine similarity = (A · B) / (|A| × |B|)
        
        The model is penalized if:
          → sim(anchor, wrong_article) is high (false match)
          → sim(anchor, correct_article) is low (missed match)

Step 4: After each epoch: evaluate on 225 validation pairs
        Measure: average cosine similarity and MRR@10
        Save epoch metrics to eval_metrics.json

Step 5: After 2 epochs, save the fine-tuned model:
        model.save("fine_tuning/outputs/bge_m3_finetuned/model/")
        → Contains config.json, model weights (.safetensors), tokenizer files

RESULTS:
  Before: cos_sim=0.461, MRR=0.316
  After:  cos_sim=0.586, MRR=0.473
  Improvement: +27.24% cosine, +49.63% MRR
```

---

### PROCESS 9: Fine-Tuning 2 — AraBERT Legal Classifier

**Script:** `fine_tuning/arabert_legal_classifier.py`

**Background flow:**

```
Step 1: Load and merge all 18 law CSVs
        Each row has: text (law article), label (law category name)
        Total: 5,320 rows across 18 categories
        
        LabelEncoder converts text labels to integers:
          "Civil Law" → 0, "Commercial Law" → 1, ... "State Council Law" → 17

Step 2: Split dataset:
        train_test_split(test_size=0.30, stratify=labels)
        → 3,724 train rows
        → 1,596 temp rows → split again 50/50 →
          798 validation rows + 798 test rows

Step 3: Tokenization with AraBERT tokenizer:
        tokenizer = AutoTokenizer.from_pretrained("aubmindlab/bert-base-arabertv2")
        For each text:
          tokens = tokenizer(text, max_length=256, padding=True, truncation=True)
          → Converts Arabic words to subword token IDs
          → Adds [CLS] at start, [SEP] at end
          → Pads to 256 tokens if shorter, truncates if longer

Step 4: Model architecture:
        AutoModelForSequenceClassification(num_labels=18)
        → AraBERT encoder: 12 Transformer layers, 768 hidden units, 12 attention heads
        → [CLS] token representation extracted (768-dimensional vector)
        → Linear(768 → 18) classification head added on top
        → Softmax → probability distribution over 18 categories
        → argmax → predicted category

Step 5: Training loop (5 epochs):
        Optimizer: AdamW(lr=2e-5, weight_decay=0.01)
        Scheduler: get_linear_schedule_with_warmup (warmup = 10% of steps)
        Loss: CrossEntropyLoss
        
        For each batch of 16 examples:
          forward pass → logits → loss
          backward pass → compute gradients
          optimizer.step() → update model weights
          scheduler.step() → reduce learning rate linearly
        
        After each epoch:
          Evaluate on 798 validation rows
          Compute accuracy and macro F1
          If val_F1 > best_val_F1: save model checkpoint (best_model/)

Step 6: Final test evaluation on 798 test rows (never seen during training):
        Results logged to test_classification_report.txt + final_metrics.json
        Confusion matrix saved as confusion_matrix.png

REAL RESULTS (from my training run):
  Best epoch: 4 (Val F1 = 0.8535)
  Test Accuracy: 91.23%
  Test Macro F1: 0.8387
```

---

## Complete Technology Stack

| Category | Technology | How it's used |
|---|---|---|
| Web Framework | Streamlit | All UI pages and state management |
| Database | SQLite (knowlaw.db) | Users, chat history, appointments, reset tokens |
| Vector Database | Chroma | Stores fine-tuned BGE-M3 embeddings of 5,340 law articles |
| **Embedding Model** | **Fine-Tuned BGE-M3** | ✅ **ACTIVE** — Egyptian-law-adapted model, replaces base BGE-M3 (+49.63% MRR) |
| **Legal Classifier** | **Fine-Tuned AraBERT v2** | ✅ **ACTIVE** — classifies every question into 1 of 18 law categories, shown as badge |
| Large Language Model | Llama 3 8B via Ollama | Generates answers and Arabic contracts |
| OCR Engine | Tesseract 5.x (ara+eng) | Reads Arabic text from scanned images |
| PDF Reader | pypdf | Extracts text from digital PDF files |
| RAG Framework | LangChain | Connects retrieval pipeline to generation |
| Language Detection | langdetect | Detects Arabic vs English questions |
| Password Security | bcrypt | Salted password hashing + verification |
| Email (Password Reset) | smtplib + Gmail SMTP | Sends reset emails with secure one-time tokens |
| Training Framework | PyTorch + Transformers | Used for both fine-tuning scripts |
| Data Processing | pandas, numpy | CSV loading, splitting, cleaning |

---

## Project Folder Structure

```
e:\project_prototype\
│
├── App.py                          ← Main Streamlit app (all UI + routing)
├── auth.py                         ← Login, register, appointments, password reset
├── vault_manager.py                ← Chat history save/load/delete
├── database_setup.py               ← DB table creation (run once)
├── brain_AI_databese(vector).py    ← Vector DB builder (run once, ~20 min)
├── generate_data.py                ← Generates sample lawyers.csv
│
├── knowlaw.db                      ← SQLite database (auto-created)
├── lawyers.csv                     ← Lawyer directory seed data
├── .env                            ← Secrets (not shared — add to .gitignore)
├── .env.example                    ← Template showing all required variables
├── requirements.txt                ← Python dependencies for main app
├── README.md                       ← Project overview + quick start
│
├── law_db/                         ← Chroma vector DB (auto-created by brain script)
│
├── fine_tuning/
│   ├── bge_m3_finetune.py          ← Fine-Tuning 1: BGE-M3 domain adaptation
│   ├── arabert_legal_classifier.py ← Fine-Tuning 2: AraBERT legal classifier
│   ├── requirements_bge_finetuning.txt
│   ├── requirements_finetuning.txt
│   └── outputs/
│       ├── best_model/             ← AraBERT trained weights (91.23% accuracy)
│       ├── bge_m3_finetuned/model/ ← BGE-M3 fine-tuned weights (MRR +49.63%)
│       ├── confusion_matrix.png    ← AraBERT per-class heatmap
│       ├── learning_curves.png     ← AraBERT loss/accuracy per epoch
│       ├── final_metrics.json      ← AraBERT real training numbers
│       └── bge_m3_finetuned/
│           ├── eval_metrics.json   ← BGE-M3 before/after numbers
│           └── training_curves.png ← BGE-M3 similarity improvement chart
│
├── model_benchmarks/
│   ├── Model_Comparison_Report.md  ← 3-model comparison for each feature + metrics
│   └── Architectural_Plan.md       ← This document
│
├── my_laws/                        ← Legacy CSVs (original, unclean — kept as backup)
├── LLM/                            ← Ollama installer (system software)
└── OCR/                            ← Tesseract installer (system software)
```

---

## Production Deployment Checklist

Both fine-tuned models are already integrated in the code. The only required step before running:

**✅ Done automatically** (code is updated):
- Fine-Tuned BGE-M3 path set in `App.py` and `brain_AI_databese(vector).py`
- AraBERT classifier loads from `fine_tuning/outputs/best_model/` on every startup
- Classification badge shows before every chatbot answer

**⏳ Action required — rebuild the vector database:**
```powershell
python "brain_AI_databese(vector).py"
```
> This re-embeds all 5,340 Egyptian law articles using the fine-tuned BGE-M3.
> Takes ~15–20 minutes. Run once — the result is saved in `law_db/`.

**After rebuild, your system uses:**
- Fine-Tuned BGE-M3 → every law article retrieved with Egyptian legal vocabulary understanding
- Fine-Tuned AraBERT → every question tagged with its law category automatically
- Llama 3 8B → answers generated from the retrieved articles
- Tesseract OCR → scanned documents converted to text
