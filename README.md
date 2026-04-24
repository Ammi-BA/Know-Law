# KnowLaw AI
### Egyptian Legal AI System | Graduation Project

An intelligent legal assistant for Egyptian law, powered by RAG (Retrieval-Augmented Generation),
Arabic NLP, and two fine-tuned AI models trained on 5,340 cleaned Egyptian law articles.

---

## 📂 Repository Structure (Where to Start)
If you are reading the code for the first time, we recommend reading the Python logic files in order from top to bottom.

### 1. Core Application Logic
| File Name | Purpose |
| :--- | :--- |
| **`App.py`** | **(Start Here)** The main Streamlit user interface and routing logic. |
| **`auth.py`** | Security module (User login, Registration, Password hashing, Appointments). |
| **`database_setup.py`** | SQLite schema builder. Creates the local user tables. |
| **`brain_AI_databese(vector).py`** | AI Engine. Builds the vector database for Llama 3 to search. |
| **`vault_manager.py`** | Helper functions for saving and loading chat history. |
| **`generate_data.py`** | Optional placeholder. The Lawyer Directory is populated through the app's registration and admin approval flow. |

### 2. Configuration & Setup
| File Name | Purpose |
| :--- | :--- |
| **`SETUP_GUIDE.md`** | Detailed installation instructions for new developers cloning the repository. |
| **`requirements.txt`** | Python dependencies required to run the app (`pip install -r`). |
| **`.env.example`** | Template for environment variables (passwords and API keys). |
| **`.gitignore`** | Tells GitHub to block sensitive files (like databases and passwords). |

### 3. Data & Databases
| Folder / File Name | Purpose |
| :--- | :--- |
| **`cleaned_datasets/`** | The 5,340 cleaned Egyptian law articles used for the AI. |
| **`law_db/`** | *(Generated locally)* The Chroma vector database built from the CSVs. |
| **`knowlaw.db`** | *(Generated locally)* SQLite database storing users and chat history. |
| **`my_laws/`** | Legacy folder containing the original, uncleaned datasets. |

### 4. Research & Fine-Tuning
| Folder Name | Purpose |
| :--- | :--- |
| **`model_benchmarks/`** | Academic reports comparing models and explaining the system architecture. |
| **`fine_tuning/`** | The Python scripts and graphs used to custom train AraBERT and BGE-M3. |

---

## Dataset

- **Location:** `cleaned_datasets/` (Included in this repository)
- **Size:** 5,340 cleaned Egyptian law article rows across 18 CSV files
- **Original (raw):** `my_laws/` (kept as backup reference for comparison)

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
