# 🚀 KnowLaw AI - Developer Setup Guide

Because this repository contains sensitive passwords and massive AI databases, those files were intentionally blocked from uploading to GitHub for security reasons. 

If you just downloaded or cloned this project to your PC, **the app will crash if you try to run it immediately.** You must follow these exact steps to rebuild the missing files and databases on your local machine.

---

## 🛠️ Phase 1: System Prerequisites

Before running any Python code, you must install the following core AI engines on your computer:

### 1. Install Ollama (The AI Brain)
- Download and install [Ollama](https://ollama.com/).
- Open your terminal and run: `ollama pull llama3:8b`
- Keep Ollama running in the background (`ollama serve`).

### 2. Install Tesseract OCR (Document Reading)
- Download the Windows installer from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
- **CRITICAL:** During the installation wizard, you MUST expand the "Additional language data" dropdown and check the box for **Arabic**.
- Install it to the default path: `C:\Program Files\Tesseract-OCR`

> ⚠️ **PATH CONFIGURATION WARNING**  
> If you installed Tesseract on a Mac, Linux, or a custom drive (like `D:\`), you MUST open `App.py` and change **Line 28** to match your actual installation path:  
> `TESSERACT_CMD_PATH = r"Your\Custom\Path\Here\tesseract.exe"`

---

## 📂 Phase 2: Rebuilding Missing Files

### 1. Create the Secret `.env` File
GitHub blocked our `.env` file to protect our passwords. You need to recreate it:
1. Find the file named `.env.example` in the project folder.
2. Rename it to exactly `.env` (remove the `.example` part).
3. Open it in a text editor and fill in your real Gmail address and a **Gmail App Password**. *(If you leave it blank, the user authentication and password-reset system will crash).*

### 2. Install Python Dependencies
Open your terminal inside the project folder and run:
```powershell
pip install -r requirements.txt
```

---

## 🧠 Phase 3: Rebuilding the Databases

GitHub also blocked our massive databases. You need to tell your computer to generate them locally.

### 1. Build the SQLite User Database
This creates the `knowlaw.db` file which stores users, lawyers, and appointments.
```powershell
python database_setup.py
```

### 2. Build the AI Vector Database (RAG)
This script reads the 5,340 laws inside the `cleaned_datasets/` folder and mathematically converts them into a Chroma vector database (the `law_db` folder).
```powershell
python "brain_AI_databese(vector).py"
```
*(Note: This step may take 15-30 minutes depending on your CPU/GPU, as it uses the BGE-M3 embedding model to process thousands of legal articles).*

---

## ▶️ Phase 4: Run the Application!

Once the `.env` file is created, the databases are built, and Ollama is running, the app is finally ready:

```powershell
streamlit run App.py
```
