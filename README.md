# KnowLaw AI
### Egyptian Legal AI System | Graduation Project

An intelligent legal assistant for Egyptian law, powered by RAG (Retrieval-Augmented Generation),
Arabic NLP, and two fine-tuned AI models trained on 5,340 cleaned Egyptian law articles.

---

## Features

| Feature | Description |
|---|---|
| ⚖️ **Legal Chatbot** | Ask any question about Egyptian law in Arabic or English |
| 📄 **Document Analysis** | Upload scanned documents for OCR text extraction, chat with them, and generate instant AI summaries. |
| ✍️ **Contract Generator** | Generate complete bilingual (Arabic & English) legal contracts based on user input. |
| 👨‍⚖️ **Lawyer Directory** | Browse, filter and contact approved Egyptian lawyers |
| 📋 **Appointments** | Citizens send requests to lawyers; lawyers accept/decline with responses |
| 🔐 **Secure Auth** | Login / register with bcrypt-hashed passwords, role-based access (Citizen / Lawyer / Admin) |

---

## AI Models Used

| Component | Model | Status | Purpose |
|---|---|---|---|
| Embedding (Retrieval) | Fine-Tuned BGE-M3 | ✅ **ACTIVE** | Domain-adapted on Egyptian law — converts questions & articles to vectors. MRR +49.63% vs base. |
| LLM | `llama3:8b` via Ollama | ✅ **ACTIVE** | Generates legal answers and Arabic contracts |
| OCR | Tesseract (`ara+eng`) | ✅ **ACTIVE** | Reads Arabic text from scanned document images |
| Legal Classifier | Fine-Tuned AraBERT v2 | ✅ **ACTIVE** | Classifies each question into 1 of 18 law categories — shown as badge before every answer (91.23% accuracy) |

---

## Quick Start

### 1. Install dependencies
```powershell
pip install -r requirements.txt
```

### 2. Set up environment variables
Copy `.env.example` to `.env` and fill in your values:
```
ADMIN_EMAIL=admin@knowlaw.com
ADMIN_PASSWORD=your_secure_password
```

### 3. Set up the database (run once)
```powershell
python database_setup.py
```

### 4. Build the vector database (run once — takes ~20 min)
```powershell
python "brain_AI_databese(vector).py"
```
> Make sure Ollama is installed and running: `ollama serve`  
> Pull the LLM: `ollama pull llama3:8b`

### 5. Run the app
```powershell
streamlit run App.py
```

---

## Project Structure

```
e:\project_prototype\
│
├── App.py                           Main Streamlit application
├── auth.py                          Authentication, user management, appointments
├── vault_manager.py                 Chat history (SQLite)
├── database_setup.py                Creates database tables and default admin
├── brain_AI_databese(vector).py     Builds Chroma vector DB from law CSVs
├── generate_data.py                 Generates sample lawyer data (lawyers.csv)
│
├── knowlaw.db                       SQLite database (auto-created)
├── lawyers.csv                      Lawyer directory data
├── .env                             Environment variables (not committed)
├── .env.example                     Template for .env
├── requirements.txt                 Python dependencies
│
├── law_db/                          Chroma vector database (auto-created by brain script)
│
├── fine_tuning/                     AI Model Training Research
│   ├── arabert_legal_classifier.py  Fine-Tuning 2: AraBERT legal topic classifier
│   ├── bge_m3_finetune.py           Fine-Tuning 1: BGE-M3 Egyptian law domain adaptation
│   ├── requirements_finetuning.txt  AraBERT pip requirements
│   ├── requirements_bge_finetuning.txt  BGE-M3 pip requirements
│   └── outputs/
│       ├── best_model/              Saved AraBERT classifier (91.23% accuracy)
│       ├── confusion_matrix.png     AraBERT test set confusion matrix
│       ├── learning_curves.png      AraBERT training curves (loss / accuracy / F1)
│       ├── final_metrics.json       AraBERT real metrics from training run
│       ├── training_log.txt         AraBERT full training log
│       └── bge_m3_finetuned/
│           ├── model/               Saved fine-tuned BGE-M3 checkpoint
│           ├── training_curves.png  BGE-M3 before/after comparison chart
│           ├── eval_metrics.json    BGE-M3 real metrics (MRR +49.63%)
│           └── training_log.txt     BGE-M3 training log
│
├── model_benchmarks/                Academic Documentation
│   ├── Model_Comparison_Report.md   Model selection report (all 3-model comparisons + metrics)
│   └── Architectural_Plan.md        System architecture + data flow + fine-tuning explanation
│
├── my_laws/                         Legacy CSV folder (original, unclean — superseded by cleaned_datasets)
│
├── LLM/                             Ollama installer (system software — can be moved out of project)
└── OCR/                             Tesseract installer (system software — can be moved out of project)
```

---

## Dataset

- **Location:** `e:\data_set for egyptianlaw\cleaned_datasets\`
- **Size:** 5,340 cleaned law article rows across 18 CSV files
- **Cleaning script:** `e:\data_set for egyptianlaw\clean_and_optimize_datasets.py`
- **Original (raw):** `e:\project_prototype\my_laws\` (kept as backup reference)

### Law Categories Covered
Civil Law · Commercial Law · Companies Law · Criminal Procedure · Penalty Law ·
Labor & Constitutional · Family Law · Investment Law · Banking Law · Capital Markets Law ·
Data Protection Law · Cyber Crimes Law · Civil & Commercial Procedures · State Council Law ·
Competition Law · Inheritance Law · Landlord & Tenant Law · Consumer Protection Law

---

## Fine-Tuning Results (Real Measured Numbers)

### Fine-Tuning 1 — BGE-M3 Domain Adaptation
| Metric | Before | After | Improvement |
|---|---|---|---|
| Avg Cosine Similarity | 0.461 | 0.586 | +27.24% |
| MRR@10 | 0.316 | 0.473 | **+49.63%** |

### Fine-Tuning 2 — AraBERT Legal Classifier (18 classes)
| Metric | Score |
|---|---|
| Test Accuracy | **91.23%** |
| Macro F1 | **0.8387** |
| Weighted F1 | **0.912** |
| Best Epoch | 4 of 5 |

---

## Technology Stack

| Technology | Version | Role |
|---|---|---|
| Python | 3.11 | Language |
| Streamlit | Latest | Web UI |
| LangChain | Latest | RAG pipeline |
| Chroma | Latest | Vector DB |
| Ollama | Latest | Local LLM serving |
| Llama 3 8B | Meta 2024 | Answer generation & contracts |
| Fine-Tuned BGE-M3 | Custom (Egyptian law) | **Active** embedding model — retrieval |
| Fine-Tuned AraBERT v2 | Custom (18 categories) | **Active** legal topic classifier |
| Tesseract OCR | 5.x | Arabic OCR |
| SQLite | Built-in | User/chat/appointment DB |
| bcrypt | Latest | Password hashing |
| smtplib / Gmail SMTP | Built-in | Password reset emails |
| PyTorch | 2.2+ | Fine-tuning |
| Transformers | 4.40+ | AraBERT fine-tuning |
| sentence-transformers | 2.7+ | BGE-M3 fine-tuning |

---

## Academic Documentation

See `model_benchmarks/` folder:
- **`Model_Comparison_Report.md`** — Full model comparison: 3 models tested per feature, all metrics, justifications, and both fine-tuning sections with real measured results
- **`Architectural_Plan.md`** — Complete system architecture, data flow diagrams, and explanation of the difference between RAG retrieval and fine-tuning

---

*KnowLaw AI — Making Egyptian law accessible to every citizen*
