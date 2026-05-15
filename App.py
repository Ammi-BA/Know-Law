"""
=============================================================================
App.py (MAIN ENTRY POINT)
=============================================================================
This is the core frontend and routing application for KnowLaw AI.
If you are new to the project, start reading here!

This file controls the Streamlit user interface, navigation between pages,
and calls the backend AI models (Llama 3, AraBERT, BGE-M3) when users 
interact with the Chatbot, OCR, or Contract Generator.
"""
import streamlit as st
import os
import re
import torch
import pandas as pd
import pypdf
import pytesseract
from PIL import Image

# Contract V&V
from contract_validator import ContractValidator

# AraT5 Contract Generator
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# LangChain
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langdetect import detect, LangDetectException

# Custom modules
import auth
import vault_manager

# ==========================================
# 0. TESSERACT CONFIGURATION
# ==========================================
TESSERACT_CMD_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_CMD_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH

# ==========================================
# 1. PAGE CONFIG & GLOBAL STYLING
# ==========================================
st.set_page_config(
    page_title="KnowLaw AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    /* Safe font application that doesn't break Streamlit material icons */
    html, body, p, h1, h2, h3, h4, h5, h6, label { 
        font-family: 'Inter', sans-serif !important; 
    }

    /* Hide Streamlit's default header anchor link icons (🔗) */
    [data-testid="stHeaderActionElements"],   /* Streamlit >= 1.30 */
    .st-emotion-cache-1104e1,                 /* Streamlit <= 1.29 */
    a.header-anchor {                         /* Fallback */
        display: none !important;
    }

    /* ── Base ── */
    .stApp {
        background: linear-gradient(160deg, #0d1117 0%, #131924 60%, #0d1117 100%) !important;
        color: #c9d1d9 !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #111827 !important;
        border-right: 1px solid #21262d !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: #1c2333 !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
        text-align: left !important;
        font-weight: 400 !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #21262d !important;
        border-color: #388bfd !important;
        transform: none !important;
    }

    /* ── Typography ── */
    h1, h2, h3, h4, h5, h6 { color: #e6edf3 !important; }
    p, li { color: #c9d1d9 !important; }

    /* ── Hide Streamlit chrome ── */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(31,111,235,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 5px 18px rgba(56,139,253,0.45) !important;
        background: linear-gradient(135deg, #388bfd, #58a6ff) !important;
    }
    .stButton > button:active { transform: translateY(0) !important; }

    /* ── Inputs ── */
    .stTextInput  > div > div > input,
    .stTextArea   > div > div > textarea,
    .stNumberInput > div > div > input {
        background: #1c2333 !important;
        color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
    }
    .stTextInput  > div > div > input:focus,
    .stTextArea   > div > div > textarea:focus {
        border-color: #388bfd !important;
        box-shadow: 0 0 0 3px rgba(56,139,253,0.15) !important;
    }
    .stSelectbox > div > div {
        background: #1c2333 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: #e6edf3 !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #161b27 !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 4px !important;
    }
    .stTabs [data-baseweb="tab"] { color: #8b949e !important; border-radius: 7px !important; }
    .stTabs [aria-selected="true"] {
        background: #1f6feb !important;
        color: #ffffff !important;
    }

    /* ── Chat ── */
    [data-testid="stChatMessage"] {
        background: #161f2e !important;
        border: 1px solid #21262d !important;
        border-radius: 12px !important;
        margin-bottom: 6px !important;
    }

    /* ── Metrics ── */
    [data-testid="metric-container"] {
        background: #1c2333 !important;
        border: 1px solid #30363d !important;
        border-radius: 12px !important;
        padding: 1rem 1.5rem !important;
    }

    /* ── Divider ── */
    hr { border-color: #21262d !important; }

    /* ── Custom classes ── */
    .header-bar {
        font-size: 22px;
        font-weight: 700;
        color: #58a6ff !important;
        border-bottom: 1px solid #21262d;
        padding-bottom: 10px;
        margin-bottom: 16px;
    }
    .feature-card {
        background: #161f2e;
        border: 1px solid #21262d;
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .feature-card:hover {
        border-color: #388bfd;
        box-shadow: 0 4px 20px rgba(56,139,253,0.12);
    }
    .stat-card {
        background: linear-gradient(135deg, #161f2e, #1c2d47);
        border: 1px solid #21262d;
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        height: 100%;
    }
    .stat-number { font-size: 2.4rem; font-weight: 800; color: #58a6ff; }
    .stat-label  { color: #8b949e; font-size: 0.85rem; margin-top: 4px; }
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-pending  { background: #92400e; color: #fcd34d; }
    .badge-accepted { background: #14532d; color: #4ade80; }
    .badge-declined { background: #450a0a; color: #f87171; }
    .appt-card {
        background: #161f2e;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
    }
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #58a6ff 0%, #388bfd 50%, #79c0ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.1;
    }
    .hero-sub { color: #8b949e; font-size: 1.1rem; margin-top: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GLOBAL SESSION STATE (initialise all keys upfront)
# ==========================================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_FOLDER = os.path.join(BASE_DIR, "law_db")

_DEFAULTS = {
    "page":                  "home",
    "logged_in":             False,
    "user_info":             None,
    "current_session_name":  None,
    "messages_general":      [],
    "messages_doc":          [],
    "active_doc_retriever":  None,
    "last_doc_name":         None,
    "ai_loaded":             False,
    "show_forgot":           False,   # controls Forgot Password UI visibility
    "pending_reset_token":   None,    # token extracted from reset URL
    "reset_email_sent":      False,   # prevents re-sending on rerun
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Handle password-reset deep-link (?reset_token=...) ─────────────────────
_qp = st.query_params
_reset_token_param = _qp.get("reset_token", None)
if _reset_token_param and not st.session_state.logged_in:
    st.session_state["pending_reset_token"] = _reset_token_param
    st.query_params.clear()

# ==========================================
# 3. CORE AI COMPONENTS (cached — load once)
# ==========================================
@st.cache_resource
def load_engine():
    """
    Loads the FINE-TUNED BGE-M3 embedding model and Llama 3 LLM.
    Fine-tuned on Egyptian law dataset — MRR improved +49.63% vs base model.
    Model path MUST match the one used in brain_AI_databese(vector).py.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── Fine-Tuned BGE-M3 (domain-adapted on Egyptian law) ──────────────────
    FINETUNED_EMBED_PATH = os.path.join(
        BASE_DIR, "fine_tuning", "outputs", "bge_m3_finetuned", "model"
    )
    # Fall back to base model if fine-tuned model not found
    embed_model_path = FINETUNED_EMBED_PATH if os.path.isdir(FINETUNED_EMBED_PATH) else "BAAI/bge-m3"

    embed_model = HuggingFaceEmbeddings(
        model_name=embed_model_path,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    llm = ChatOllama(model="llama3:8b", temperature=0.1)
    return embed_model, llm


@st.cache_resource
def load_arabert_classifier():
    """
    Loads the fine-tuned AraBERT legal topic classifier.
    Classifies Arabic legal text into 18 Egyptian law categories.
    Fine-tuned on our dataset: 91.23% accuracy, Macro F1 = 0.839.
    Returns (model, tokenizer, label_map) or (None, None, None) if not found.
    """
    import json
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    MODEL_PATH  = os.path.join(BASE_DIR, "fine_tuning", "outputs", "best_model")
    LABEL_PATH  = os.path.join(BASE_DIR, "fine_tuning", "outputs", "label_mapping.json")

    if not os.path.isdir(MODEL_PATH) or not os.path.isfile(LABEL_PATH):
        return None, None, None

    try:
        tokenizer  = AutoTokenizer.from_pretrained(MODEL_PATH)
        clf_model  = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
        clf_model.eval()
        with open(LABEL_PATH, "r", encoding="utf-8") as f:
            label_map = json.load(f)   # {"0": "Banking Law", ...}
        return clf_model, tokenizer, label_map
    except Exception:
        return None, None, None


@st.cache_resource
def load_arat5_generator():
    """
    Loads the fine-tuned AraT5 contract generator model.
    Model fine-tuned on 2,000 Egyptian contract pairs (10 epochs, train_loss=0.0864).
    Saved at outputs/arat5_contract_generator/best_model relative to repo root.
    Returns (model, tokenizer) or (None, None) if the model directory is not found.
    """
    # Primary path: same directory as App.py (works for main project)
    MODEL_PATH = os.path.join(BASE_DIR, "outputs", "arat5_contract_generator", "best_model")

    # Fallback: walk up from BASE_DIR for git worktree environments
    if not os.path.isdir(MODEL_PATH):
        parent = os.path.dirname(BASE_DIR)
        for _ in range(5):
            candidate = os.path.join(parent, "outputs", "arat5_contract_generator", "best_model")
            if os.path.isdir(candidate):
                MODEL_PATH = candidate
                break
            parent = os.path.dirname(parent)

    if not os.path.isdir(MODEL_PATH):
        return None, None
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)
        model.eval()
        return model, tokenizer
    except Exception:
        return None, None


def classify_question(text: str) -> str | None:
    """
    Run AraBERT classifier on `text`.
    If text is not Arabic, it uses the local Llama 3 model to translate it to Arabic first,
    ensuring AraBERT can accurately classify the legal area regardless of the input language.
    Returns the predicted Egyptian law category label, or None if unavailable.
    torch is imported at top-level — no repeated import overhead.
    """
    clf_model, tokenizer, label_map = load_arabert_classifier()
    if clf_model is None:
        return None
        
    try:
        lang = detect(text)
        if lang != "ar":
            # Translate English/French/etc. to Arabic using Llama 3 before classifying
            _, llm = load_engine()
            translate_prompt = f"ترجم هذا النص بدقة إلى اللغة العربية. اكتب الترجمة فقط ولا تكتب أي كلمة أخرى:\n{text}"
            translated = llm.invoke(translate_prompt)
            text = translated.content.strip()
    except Exception:
        pass

    inputs = tokenizer(
        text, return_tensors="pt",
        max_length=128, truncation=True, padding=True
    )
    with torch.no_grad():
        logits = clf_model(**inputs).logits
    pred_idx = int(torch.argmax(logits, dim=1).item())
    return label_map.get(str(pred_idx), None)


# Show spinner ONLY on first load (not on every rerun / button click)
if not st.session_state.ai_loaded:
    with st.spinner("⚡ Initialising AI engine… (first load only)"):
        embedding_model, llm        = load_engine()
        _clf, _tok, _lmap           = load_arabert_classifier()
        _arat5_model, _arat5_tok    = load_arat5_generator()
    st.session_state.ai_loaded = True
    _ft_path = os.path.join(BASE_DIR, "fine_tuning", "outputs", "bge_m3_finetuned", "model")
    if os.path.isdir(_ft_path):
        st.toast("✅ Fine-tuned BGE-M3 loaded (Egyptian law adapted)", icon="🧠")
    else:
        st.toast("⚠️ Fine-tuned BGE-M3 not found — using base model", icon="⚠️")
    if _clf is not None:
        st.toast("✅ AraBERT classifier loaded (18 law categories)", icon="⚖️")
    if _arat5_model is not None:
        st.toast("✅ AraT5 Contract Generator loaded", icon="✍️")
else:
    embedding_model, llm = load_engine()
    _arat5_model, _arat5_tok = load_arat5_generator()



@st.cache_resource
def get_vector_db(_emb):
    """
    Loads the Chroma vector DB.
    Underscore prefix on _emb tells Streamlit NOT to hash the model object.
    Returns None if the DB folder doesn't exist.
    """
    if not os.path.exists(DB_FOLDER):
        return None
    return Chroma(persist_directory=DB_FOLDER, embedding_function=_emb)


main_db = get_vector_db(embedding_model)

# ==========================================
# 4. HELPER FUNCTIONS & PROMPTS
# ==========================================

def extract_text_from_file(uploaded_file) -> str | None:
    """Extracts text from PDF (PyPDF) or image (Tesseract OCR)."""
    ftype = uploaded_file.type
    if ftype == "application/pdf":
        try:
            reader = pypdf.PdfReader(uploaded_file)
            return "".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            return None
    elif ftype in ("image/png", "image/jpeg"):
        try:
            return pytesseract.image_to_string(Image.open(uploaded_file), lang="ara+eng")
        except Exception:
            return None
    return None


def create_temp_retriever(file_text: str):
    """
    Splits text into overlapping chunks and builds a temporary in-memory
    Chroma vector store for document-level Q&A.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks   = splitter.split_text(file_text)
    docs     = [Document(page_content=c) for c in chunks if c.strip()]
    if not docs:
        return None
    temp_db = Chroma.from_documents(documents=docs, embedding=embedding_model)
    return temp_db.as_retriever(search_kwargs={"k": 5})


def get_legal_prompt(query: str, history: list = None) -> ChatPromptTemplate:
    """Returns a language-appropriate system prompt with optional chat history memory."""
    try:
        lang = detect(query)
    except LangDetectException:
        lang = "ar"

    history_str = ""
    if history and len(history) > 1:
        # Get the last 4 messages (excluding the current one just added)
        recent = history[-5:-1]
        for m in recent:
            role = "المستخدم" if m["role"] == "user" else "KnowLaw AI"
            # Escape { } so LangChain's template parser doesn't crash on legal text
            safe_content = m["content"].replace("{", "{{").replace("}", "}}")
            history_str += f"- {role}: {safe_content}\n"

    if lang == "ar":
        tpl = (
            "أنت مستشار قانوني مصري ذكي ومنظم وموثوق. أجب على السؤال بناءً على 'السياق' المقدم فقط.\n\n"
        )
        if history_str:
            tpl += f"سجل المحادثة السابقة (استخدمه لفهم سياق السؤال الحالي فقط):\n{history_str}\n\n"
            
        tpl += (
            "السياق القانوني المتاح (نصوص مواد قانونية):\n{context}\n\n"
            "السؤال: {question}\n\n"
            "قواعد الإجابة:\n"
            "1. اجعل إجابتك واضحة، منظمة، وفي نقاط إن أمكن.\n"
            "2. إذا كان السؤال مجرد تحية أو سؤالاً عادياً لا علاقة له بالقانون (مثل 'كيف حالك' أو 'أين محادثاتي')، فأجب بشكل طبيعي وتجاهل كتابة قسم المصادر وقسم التنويه.\n"
            "3. أما إذا كان سؤالاً قانونياً، فيجب عليك إضافة قسم بعنوان '**المصادر:**' في النهاية واكتب فيه أسماء ملفات السياق التي استندت إليها بالضبط.\n"
            "4. في حال الإجابة القانونية، اختتم دائماً بـ: '*تنويه: هذه المعلومات معرفية ولا تُعدّ مشورة قانونية.*'"
        )
    else:
        tpl = (
            "You are a knowledgeable Egyptian Legal Advisor. Answer the question based ONLY on "
            "the context provided, in a clear and organized manner.\n\n"
        )
        if history_str:
            tpl += f"Previous Conversation History (for context only):\n{history_str}\n\n"
            
        tpl += (
            "Available Legal Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Rules:\n"
            "1. If the question is a casual greeting or unrelated to law (like 'Hello' or 'Where are my chats'), just answer naturally and completely ignore the Sources and Disclaimer rules.\n"
            "2. If it is a legal question, at the very end of your response, add a '**Sources:**' section listing the source files you used from the context.\n"
            "3. If it is a legal question, always conclude with: '*Disclaimer: This information is educational and does not constitute legal advice.*'"
        )
    return ChatPromptTemplate.from_template(tpl)


def get_doc_prompt(history: list = None) -> ChatPromptTemplate:
    """Strict prompt for document analysis with chat memory."""
    history_str = ""
    if history and len(history) > 1:
        recent = history[-5:-1]
        for m in recent:
            role = "المستخدم" if m["role"] == "user" else "KnowLaw AI"
            # Escape { } so LangChain's template parser doesn't crash on legal text
            safe_content = m["content"].replace("{", "{{").replace("}", "}}")
            history_str += f"- {role}: {safe_content}\n"
            
    tpl = """أنت مساعد قانوني خبير ومتخصص في القانون المصري يعمل ضمن منظومة KnowLaw AI.

**قواعد صارمة:**
1. ممنوع تقديم المشورة القانونية: لا تخبر المستخدم أبدًا "يجب عليك..." أو "ستربح القضية".
2. الالتزام بالمصادر: استند إجابتك فقط وحصريًا على النصوص الموجودة في "السياق" أدناه المعطى من مستند المستخدم.
3. الإجابة باللغة العربية الفصحى.
4. التذييل الإلزامي: اختتم دائماً إجابتك بـ: "*تنويه: هذه المعلومات معرفية ولا تعتبر مشورة قانونية.*"\n\n"""

    if history_str:
        tpl += f"سجل المحادثة السابقة:\n{history_str}\n\n"

    tpl += """السياق المستخرج من المستند المرفوع:
{context}

سؤال المستخدم:
{question}"""
    return ChatPromptTemplate.from_template(tpl)


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[المصدر: {d.metadata.get('source', 'المستند')}]\n{d.page_content}"
        for d in docs
    )


# ── Legal category map: CSV filename stem → human-readable label ──────────────
# Keys MUST match the actual CSV filenames in cleaned_datasets/ exactly.
_FILE_TO_CATEGORY = {
    "final_datset_for_civil_law":                       "Civil Law",
    "commircial_law_final_dataset":                     "Commercial Law",
    "dataset_companies_law":                            "Companies Law",
    "final_dataset_for_Criminal_Procedure":             "Criminal Procedure",
    "finished_dataset_for_penalty_law":                 "Penalty Law",
    "final_dataset_for_labor_constitution":             "Labor & Constitutional Law",
    "finished_dataset_for_family_law2":                 "Family Law",
    "final_dataset_for_invesment":                      "Investment Law",
    "finished_dataset_for_main_bank":                   "Banking Law",
    "law_for_money_capital":                            "Capital Markets Law",
    "Data_Protection_Law_dataset":                      "Data Protection Law",
    "final_dataset_for_cyber_crimes":                   "Cyber Crimes Law",
    "finished_dataset_for_civil_comircial_procedures":  "Civil & Commercial Procedures",
    "finished_dataset_for_magles_eldawla":              "State Council Law",
    "final_dataset_fro_Protection_of_Competition":      "Competition Law",
    "final_dataset_law_of_inhertince":                  "Inheritance Law",
    "landord_lawnew-old":                               "Landlord & Tenant Law",
    "final_dataset_for_Consumer_Protection_Law":        "Consumer Protection Law",
}


def get_category_from_docs(docs: list) -> str | None:
    """
    Determines the legal badge from the metadata of the retrieved documents.
    This is more accurate than classifying the question itself because it reads
    the actual law files that Chroma returned — the answer ALWAYS comes from
    those files, so the badge correctly reflects the legal area used.
    Returns the most frequently appearing law category, or None.
    """
    from collections import Counter
    stems = [
        doc.metadata.get("file", "").replace(".csv", "")
        for doc in docs
        if doc.metadata.get("file", "")
    ]
    if not stems:
        return None
    most_common_stem = Counter(stems).most_common(1)[0][0]
    return _FILE_TO_CATEGORY.get(
        most_common_stem,
        most_common_stem.replace("_", " ").title()  # fallback: prettify the filename
    )


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def validate_password(pw: str) -> bool:
    return len(pw) >= 8


def go_home():
    st.session_state.page = "home"
    st.rerun()


def stream_llm(chain, query: str) -> str:
    """Streams LLM output token by token and returns the full response."""
    box      = st.empty()
    full     = ""
    try:
        for chunk in chain.stream(query):
            full += chunk
            box.markdown(full + "▌")
        box.markdown(full)
    except Exception:
        box.error("⚠️ **عذراً، محرك الذكاء الاصطناعي لا يعمل (AI Engine Offline):** يرجى التأكد من تشغيل خادم Ollama في الخلفية.")
        st.stop()
    return full


# ==========================================
# 5. TOP NAV BAR (shown when logged in)
# ==========================================
def show_nav():
    user = st.session_state.user_info
    role_icon = {"Admin": "👑", "Lawyer": "👨‍⚖️", "Citizen": "👤"}.get(user["role"], "👤")

    c_logo, c_user, c_btns, c_logout = st.columns([4, 3, 4, 1])
    c_logo.markdown(
        f'<div class="header-bar">⚖️ KnowLaw AI</div>',
        unsafe_allow_html=True,
    )
    c_user.markdown(f"**{role_icon} {user['full_name']}** `{user['role']}`")

    with c_btns:
        btn_count = 3 if user["role"] == "Admin" else 2
        nav_cols = st.columns(btn_count)
        if nav_cols[0].button("🏠", key="nav_home",   help="Home"):
            st.session_state.page = "home"; st.rerun()
        if nav_cols[1].button("📋", key="nav_appts",  help="Appointments"):
            st.session_state.page = "appointments"; st.rerun()
        if user["role"] == "Admin":
            if nav_cols[2].button("⚙️", key="nav_admin", help="Admin Panel"):
                st.session_state.page = "admin"; st.rerun()

    if c_logout.button("🚪", key="nav_logout", help="Logout"):
        st.session_state.clear()   # wipe ALL keys including dynamic contact_{id} forms
        st.rerun()

    st.divider()


# ==========================================
# 6. AUTH — LOGIN / REGISTER
# ==========================================
if not st.session_state.logged_in:

    # Hero
    st.markdown("""
    <div style="text-align:center; padding: 3rem 0 2rem 0;">
        <div style="font-size:4rem; margin-bottom:0.5rem;">⚖️</div>
        <h1 class="hero-title">KnowLaw AI</h1>
        <p class="hero-sub">مستشارك القانوني الذكي | Your Intelligent Egyptian Legal Companion</p>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:

        # ── Password Reset via URL token ────────────────────────────────────────
        if st.session_state.get("pending_reset_token"):
            token = st.session_state["pending_reset_token"]
            email_for_token = auth.validate_reset_token(token)
            if not email_for_token:
                st.error("❌ This password reset link has expired or is invalid. Please request a new one.")
                st.session_state.pop("pending_reset_token", None)
            else:
                st.success(f"✅ Verified! Set a new password for **{email_for_token}**")
                with st.form("reset_pw_form"):
                    new_pw  = st.text_input("🔒 New Password", type="password", placeholder="Min 8 characters")
                    new_pw2 = st.text_input("🔒 Confirm Password", type="password", placeholder="Repeat new password")
                    if st.form_submit_button("✅ Set New Password", use_container_width=True):
                        if not validate_password(new_pw):
                            st.error("Password must be at least 8 characters.")
                        elif new_pw != new_pw2:
                            st.error("Passwords do not match.")
                        else:
                            if auth.reset_password(token, new_pw):
                                st.session_state.pop("pending_reset_token", None)
                                st.success("🎉 Password updated! You can now log in.")
                                st.rerun()
                            else:
                                st.error("❌ Reset failed. The link may have expired.")
            st.stop()

        tab_login, tab_reg = st.tabs(["🔐 Login", "📝 Register"])

        # ── Login ──────────────────────────────────────────────────────────────
        with tab_login:
            with st.form("login_form"):
                email_in = st.text_input("📧 Email", placeholder="you@example.com")
                pass_in  = st.text_input("🔒 Password", type="password", placeholder="Your password")
                if st.form_submit_button("Login →", use_container_width=True):
                    if not email_in or not pass_in:
                        st.error("Please fill in both fields.")
                    else:
                        user = auth.login_user(email_in.strip().lower(), pass_in)
                        if user:
                            if user["status"] == "Pending":
                                st.warning("⏳ Your lawyer account is awaiting admin approval.")
                            else:
                                st.session_state.user_info = user
                                st.session_state.logged_in = True
                                st.session_state.page = "admin" if user["role"] == "Admin" else "home"
                                st.rerun()
                        else:
                            st.error("❌ Incorrect email or password.")

            # Forgot password link (outside the form)
            st.markdown("<div style='text-align:center; margin-top:8px;'>", unsafe_allow_html=True)
            if st.button("🔑 Forgot your password?", key="forgot_pw_btn",
                         help="Send a reset link to your email"):
                st.session_state["show_forgot"] = True
            st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.get("show_forgot"):
                with st.form("forgot_pw_form"):
                    st.markdown("**Enter your registered email to receive a reset link:**")
                    forgot_email = st.text_input("📧 Email", placeholder="you@example.com", key="forgot_email_in")
                    if st.form_submit_button("📨 Send Reset Email", use_container_width=True):
                        if not validate_email(forgot_email):
                            st.error("Please enter a valid email address.")
                        else:
                            token = auth.create_password_reset_token(forgot_email.strip().lower())
                            if token:
                                ok, err = auth.send_reset_email(forgot_email.strip().lower(), token)
                                if ok:
                                    st.success("✅ Reset email sent! Check your inbox (and spam folder). Link expires in 30 minutes.")
                                    st.session_state["show_forgot"] = False
                                else:
                                    st.error(f"❌ Could not send email: {err}")
                                    st.info(f"🔗 **Dev mode** — Reset link (copy manually):\n`?reset_token={token}`")
                            else:
                                # Don't reveal if email exists (security best practice)
                                st.success("✅ If that email is registered, a reset link has been sent.")

        # ── Register ───────────────────────────────────────────────────────────
        with tab_reg:
            with st.form("register_form"):
                role  = st.selectbox("👤 I am a…", ["Citizen", "Lawyer"])
                c1, c2 = st.columns(2)
                name  = c1.text_input("Full Name *",  placeholder="Ahmed Mohamed")
                email = c2.text_input("Email *",      placeholder="you@example.com")
                c3, c4 = st.columns(2)
                pw    = c3.text_input("Password *",   type="password", placeholder="Min 8 characters")
                phone = c4.text_input("Phone",        placeholder="01X XXXX XXXX")
                c5, c6 = st.columns(2)
                age   = c5.number_input("Age", 18, 100, 25)
                city  = c6.text_input("City",         placeholder="Cairo")
                addr  = st.text_input("Address",      placeholder="Street, District")

                spec = bio = None
                if role == "Lawyer":
                    st.info("👨‍⚖️ Lawyer Details — required for approval")
                    spec = st.text_input("Specialty *", placeholder="e.g. Criminal Law")
                    bio  = st.text_area("Professional Bio *",
                                        placeholder="Briefly describe your experience and background…")

                if st.form_submit_button("Create Account →", use_container_width=True):
                    errs = []
                    if not name.strip():                 errs.append("Full name is required.")
                    if not validate_email(email):        errs.append("A valid email address is required.")
                    if not validate_password(pw):        errs.append("Password must be at least 8 characters.")
                    if role == "Lawyer":
                        if not spec or not spec.strip(): errs.append("Specialty is required for Lawyers.")
                        if not bio  or not bio.strip():  errs.append("Professional Bio is required for Lawyers.")

                    if errs:
                        for e in errs: st.error(e)
                    else:
                        ok = auth.register_user(
                            role, name.strip(), email.strip().lower(), pw,
                            phone, age, city, addr, spec, bio,
                        )
                        if ok:
                            msg = ("✅ Registered! Your account is pending admin approval." if role == "Lawyer"
                                   else "✅ Account created! You can now log in.")
                            st.success(msg)
                        else:
                            st.error("❌ That email is already registered.")

    st.stop()

# ==========================================
# 7. APPLICATION — ROUTES
# ==========================================
show_nav()

# ── HOME ──────────────────────────────────────────────────────────────────────
if st.session_state.page == "home":
    user = st.session_state.user_info
    first = user["full_name"].split()[0]

    st.markdown(f"""
    <div style="text-align:center; padding: 1rem 0 2rem 0;">
        <h2 style="font-size:2rem; color:#e6edf3;">Welcome back, {first} 👋</h2>
        <p style="color:#8b949e;">What would you like to do today?</p>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    active_lawyers = len(auth.get_approved_lawyers())
    
    _, s1, s2, s3, _ = st.columns([1, 2, 2, 2, 1])
    s1.markdown(f'<div class="stat-card"><div class="stat-number">📜</div><div class="stat-label">Certified Egyptian Laws</div></div>', unsafe_allow_html=True)
    s2.markdown(f'<div class="stat-card"><div class="stat-number">{active_lawyers}</div><div class="stat-label">Verified Lawyers</div></div>', unsafe_allow_html=True)
    s3.markdown(f'<div class="stat-card"><div class="stat-number">🔒</div><div class="stat-label">Privacy Protected</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature cards — 2 × 2 grid
    _, col_l, col_r, _ = st.columns([0.5, 3, 3, 0.5])

    with col_l:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color:#58a6ff;margin-top:0">🤖 AI Legal Chatbot</h3>
            <p style="color:#8b949e;font-size:.9rem">
                Ask any question about Egyptian law and get instant AI-powered answers
                sourced from our comprehensive legal database.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open Chatbot →", key="hb_chat", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="feature-card">
            <h3 style="color:#58a6ff;margin-top:0">⚖️ Find a Lawyer</h3>
            <p style="color:#8b949e;font-size:.9rem">
                Browse our directory of verified Egyptian lawyers, filter by city
                and specialty, and send appointment requests directly.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("Browse Directory →", key="hb_dir", use_container_width=True):
            st.session_state.page = "directory"; st.rerun()

    with col_r:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color:#58a6ff;margin-top:0">📄 Document Analysis</h3>
            <p style="color:#8b949e;font-size:.9rem">
                Upload a legal PDF or scanned image. KnowLaw AI will extract
                and analyse the text, then answer your questions about it.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("Analyse Document →", key="hb_doc", use_container_width=True):
            st.session_state.page = "document"; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="feature-card">
            <h3 style="color:#58a6ff;margin-top:0">✍️ Contract Generator</h3>
            <p style="color:#8b949e;font-size:.9rem">
                Automatically draft professional Arabic legal contracts — lease,
                employment, sales, and contractor agreements.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("Generate Contract →", key="hb_contract", use_container_width=True):
            st.session_state.page = "contract"; st.rerun()

# ── ADMIN PANEL ───────────────────────────────────────────────────────────────
elif st.session_state.page == "admin":
    if st.session_state.user_info["role"] != "Admin":
        st.error("⛔ Access denied."); st.stop()

    st.markdown("<h1>👑 System Administrator Panel</h1>", unsafe_allow_html=True)
    pending = auth.get_pending_lawyers()

    tab_pend, tab_stats = st.tabs([f"⏳ Pending Approvals ({len(pending)})", "📊 System Overview"])

    with tab_pend:
        if not pending:
            st.success("✅ All caught up — no pending lawyer registrations.")
        for law in pending:
            with st.container(border=True):
                ci, ca = st.columns([4, 1])
                with ci:
                    st.markdown(f"**{law['name']}** | 📧 {law['email']}")
                    st.markdown(f"📍 {law['city']} | ⚖️ {law['specialty']}")
                    st.markdown(f"*{law['bio']}*")
                with ca:
                    if st.button("✅ Approve", key=f"a_{law['id']}", use_container_width=True):
                        auth.approve_lawyer(law["id"]); st.rerun()
                    if st.button("❌ Reject",  key=f"r_{law['id']}", use_container_width=True):
                        auth.reject_lawyer(law["id"]);  st.rerun()

    with tab_stats:
        import sqlite3 as _sq
        import pandas as _pd
        _conn = _sq.connect(auth.DB_NAME)
        
        # Load full tables for visual charts
        _df_users = _pd.read_sql("SELECT role, verified_status FROM Users", _conn)
        _df_laws  = _pd.read_sql("SELECT specialty FROM Lawyer_Profiles", _conn)
        
        _cur  = _conn.cursor()
        _total_users   = len(_df_users)
        _total_citizens= len(_df_users[_df_users["role"] == "Citizen"])
        _total_lawyers = len(_df_users[_df_users["role"] == "Lawyer"])
        _approved_law  = len(_df_users[(_df_users["role"] == "Lawyer") & (_df_users["verified_status"] == "Approved")])
        _total_appts   = _cur.execute("SELECT COUNT(*) FROM Appointments").fetchone()[0]
        _pending_appts = _cur.execute("SELECT COUNT(*) FROM Appointments WHERE status='Pending'").fetchone()[0]
        _total_chats   = _cur.execute("SELECT COUNT(*) FROM Chat_History").fetchone()[0]
        _conn.close()

        st.markdown("### 📊 Live System Statistics")
        m1, m2, m3 = st.columns(3)
        m1.metric("👥 Total Users",      _total_users)
        m2.metric("👤 Citizens",          _total_citizens)
        m3.metric("👨‍⚖️ Lawyers (Total)",  _total_lawyers)
        m4, m5, m6 = st.columns(3)
        m4.metric("✅ Approved Lawyers",  _approved_law)
        m5.metric("📋 Total Appointments",_total_appts)
        m6.metric("⏳ Pending Appts",     _pending_appts)
        st.metric("💬 Saved Chat Sessions", _total_chats)
        
        st.divider()
        st.markdown("### 📈 Visual Analytics")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**User Roles Distribution**")
            if not _df_users.empty:
                st.bar_chart(_df_users["role"].value_counts(), color="#1f6feb")
            else:
                st.info("No data")
                
        with c2:
            st.markdown("**Lawyer Specialties**")
            if not _df_laws.empty:
                st.bar_chart(_df_laws["specialty"].value_counts(), color="#2ea043")
            else:
                st.info("No data")
                
        st.caption("Stats refresh on every page load.")

# ── GENERAL CHAT ──────────────────────────────────────────────────────────────
elif st.session_state.page == "chat":

    past = vault_manager.get_user_chats(st.session_state.user_info["id"], session_type="chat")

    hdr_col, back_col = st.columns([5, 1])
    hdr_col.header("🤖 General Law Chatbot")
    if back_col.button("⬅️ Home", key="chat_home"):
        go_home()

    with st.expander(f"🗄️ Past Chats ({len(past)})", expanded=False):
        col_new, _ = st.columns([1, 4])
        if col_new.button("➕ New Chat", key="new_chat"):
            st.session_state.messages_general     = []
            st.session_state.current_session_name = None
            st.rerun()
        if not past:
            st.caption("No saved chats yet.")
        else:
            for chat in past:
                is_active = (st.session_state.current_session_name == chat["session_name"])
                c_btn, c_del = st.columns([6, 1])
                icon  = "💬" if is_active else "🕐"
                if c_btn.button(f"{icon} {chat['session_name']}", key=f"ch_{chat['id']}", use_container_width=True):
                    st.session_state.messages_general     = vault_manager.load_chat(chat["id"])
                    st.session_state.current_session_name = chat["session_name"]
                    st.rerun()
                if c_del.button("🗑️", key=f"del_{chat['id']}", help="Delete"):
                    vault_manager.delete_chat(chat["id"])
                    if st.session_state.current_session_name == chat["session_name"]:
                        st.session_state.messages_general     = []
                        st.session_state.current_session_name = None
                    st.rerun()

    if not st.session_state.messages_general:
        st.session_state.messages_general = [{
            "role":    "assistant",
            "content": "مرحباً! أنا مستشارك القانوني الذكي. كيف يمكنني مساعدتك اليوم؟\n\n"
                       "Hello! I'm your AI legal assistant. How can I assist you with Egyptian law today?",
        }]

    for msg in st.session_state.messages_general:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("اطرح سؤالك القانوني… / Ask a legal question…"):
        if main_db is None:
            st.error("⚠️ The legal knowledge base is offline. Run `brain_AI_databese(vector).py` to build it first.")
        else:
            st.session_state.messages_general.append({"role": "user", "content": prompt})
            if st.session_state.current_session_name is None:
                clean = re.sub(r'^[\d\s\W]+', '', prompt).strip()
                st.session_state.current_session_name = (clean[:40] + "…") if len(clean) > 40 else (clean or prompt[:40])

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                # ── Retrieve relevant docs first ──────────────────────────────
                retriever = main_db.as_retriever(search_kwargs={"k": 5})
                retrieved_docs = retriever.invoke(prompt)

                # ── Badge: based on retrieved docs (always correct) ───────────
                predicted_category = get_category_from_docs(retrieved_docs)
                if predicted_category:
                    st.markdown(
                        f"""<div style='margin-bottom:10px;'>
                        <span style='background:#1c2d47;border:1px solid #388bfd;
                               color:#79c0ff;padding:4px 14px;border-radius:20px;
                               font-size:0.82rem;font-weight:600;'>
                        📚 Legal Area: {predicted_category}
                        </span></div>""",
                        unsafe_allow_html=True,
                    )

                # ── Generate answer using the same retriever ──────────────────
                chain = (
                    {"context": retriever | format_docs, "question": RunnablePassthrough()}
                    | get_legal_prompt(prompt, st.session_state.messages_general)
                    | llm
                    | StrOutputParser()
                )
                full_resp = stream_llm(chain, prompt)
                st.session_state.messages_general.append({"role": "assistant", "content": full_resp})
                vault_manager.save_chat(
                    st.session_state.user_info["id"],
                    st.session_state.current_session_name,
                    st.session_state.messages_general,
                    session_type="chat",
                )

# ── DOCUMENT ANALYSIS ─────────────────────────────────────────────────────────
elif st.session_state.page == "document":

    hdr_col, back_col = st.columns([5, 1])
    hdr_col.header("📄 Document Analysis & OCR")
    if back_col.button("⬅️ Home", key="doc_back"):
        st.session_state.active_doc_retriever = None
        st.session_state.last_doc_name        = None
        go_home()

    past_ocr = vault_manager.get_user_chats(st.session_state.user_info["id"], session_type="ocr")
    with st.expander(f"🗄️ Past Sessions ({len(past_ocr)})", expanded=False):
        col_new, _ = st.columns([1, 4])
        if col_new.button("➕ New Analysis", key="new_ocr"):
            st.session_state.messages_doc         = []
            st.session_state.active_doc_retriever = None
            st.session_state.last_doc_name        = None
            st.rerun()
        if not past_ocr:
            st.caption("No saved document sessions yet.")
        else:
            for sess in past_ocr:
                is_active = (st.session_state.last_doc_name == sess["session_name"])
                doc_cols  = st.columns([6, 1])
                icon = "📝" if is_active else "📄"
                if doc_cols[0].button(f"{icon} {sess['session_name'][:30]}", key=f"ocr_{sess['id']}", use_container_width=True):
                    st.session_state.messages_doc  = vault_manager.load_chat(sess["id"])
                    st.session_state.last_doc_name = sess["session_name"]
                    st.session_state.active_doc_retriever = None
                    st.rerun()
                if doc_cols[1].button("🗑️", key=f"del_ocr_{sess['id']}", help="Delete"):
                    vault_manager.delete_chat(sess["id"])
                    if st.session_state.last_doc_name == sess["session_name"]:
                        st.session_state.messages_doc  = []
                        st.session_state.last_doc_name = None
                    st.rerun()

    col_up, col_chat = st.columns([1, 2])

    with col_up:
        with st.container(border=True):
            st.subheader("1. Upload")
            uploaded = st.file_uploader("Select PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
            if st.session_state.last_doc_name:
                st.success(f"✅ Active: **{st.session_state.last_doc_name}**")
            if st.button("🗑️ Clear Document & Chat", use_container_width=True, key="clear_doc"):
                st.session_state.messages_doc          = []
                st.session_state.active_doc_retriever  = None
                st.session_state.last_doc_name         = None
                st.rerun()

    if not st.session_state.messages_doc:
        st.session_state.messages_doc = [{
            "role":    "assistant",
            "content": "مرحباً! يرجى رفع مستند قانوني (PDF أو صورة مسحوبة) للبدء.\n\n"
                       "Hello! Upload a legal document (PDF or scanned image) to begin.",
        }]

    if uploaded and st.session_state.last_doc_name != uploaded.name:
        with st.spinner(f"🔍 Analysing {uploaded.name}…"):
            text = extract_text_from_file(uploaded)
            if text and len(text) > 10:
                st.session_state.active_doc_retriever = create_temp_retriever(text)
                st.session_state.last_doc_name        = uploaded.name
                st.session_state.messages_doc.append({
                    "role":    "assistant",
                    "content": f"✅ تم تحليل المستند **{uploaded.name}** بنجاح ({len(text):,} حرف). "
                               "أنا جاهز للإجابة على أسئلتك.",
                })
                st.rerun()
            else:
                st.error("❌ Could not extract readable text. For scanned images, ensure Tesseract OCR is installed.")

    with col_chat:
        st.subheader("2. Chat with Document")
        for msg in st.session_state.messages_doc:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Quick summary button (shows up if doc is active and no long chat history yet)
        if st.session_state.active_doc_retriever and len(st.session_state.messages_doc) <= 2:
            if st.button("✨ Summarize Document / تلخيص المستند", use_container_width=True):
                q = "قم بتلخيص هذا المستند بوضوح واذكر أبرز النقاط الأساسية والأحكام المهمة في شكل نقاط (Bullet points)."
                st.session_state.messages_doc.append({"role": "user", "content": q})
                with st.chat_message("user"):
                    st.markdown(q)
                with st.chat_message("assistant"):
                    chain = (
                        {"context": st.session_state.active_doc_retriever | format_docs,
                         "question": RunnablePassthrough()}
                        | get_doc_prompt(st.session_state.messages_doc)
                        | llm
                        | StrOutputParser()
                    )
                    resp = stream_llm(chain, q)
                    st.session_state.messages_doc.append({"role": "assistant", "content": resp})
                    vault_manager.save_chat(
                        st.session_state.user_info["id"],
                        st.session_state.last_doc_name or "Untitled Document",
                        st.session_state.messages_doc,
                        session_type="ocr",
                    )


        if q := st.chat_input("Ask about the uploaded document…"):
            st.session_state.messages_doc.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                if st.session_state.active_doc_retriever:
                    chain = (
                        {"context": st.session_state.active_doc_retriever | format_docs,
                         "question": RunnablePassthrough()}
                        | get_doc_prompt(st.session_state.messages_doc)
                        | llm
                        | StrOutputParser()
                    )
                    resp = stream_llm(chain, q)
                    st.session_state.messages_doc.append({"role": "assistant", "content": resp})
                    # Save OCR session using the document name as title
                    vault_manager.save_chat(
                        st.session_state.user_info["id"],
                        st.session_state.last_doc_name or "Untitled Document",
                        st.session_state.messages_doc,
                        session_type="ocr",
                    )
                else:
                    st.warning("⚠️ Please upload a document first.")

# ── LAWYER DIRECTORY & BOOKING ─────────────────────────────────────────────────
elif st.session_state.page == "directory":
    if st.button("⬅️ Back", key="dir_back"):
        go_home()

    st.header("⚖️ Find & Contact a Lawyer")

    lawyers = auth.get_approved_lawyers()
    if not lawyers:
        st.info("ℹ️ No approved lawyers are currently registered in the system.")
    else:
        df = pd.DataFrame(lawyers)

        f1, f2, f3 = st.columns(3)
        search_q    = f1.text_input("🔍 Search by Name", placeholder="Lawyer name…")
        city_list   = ["All"] + sorted(df["city"].dropna().unique().tolist())
        spec_list   = ["All"] + sorted(df["specialty"].dropna().unique().tolist())
        city_sel    = f2.selectbox("📍 City",      city_list)
        spec_sel    = f3.selectbox("⚖️ Specialty", spec_list)

        filt = df.copy()
        if city_sel  != "All": filt = filt[filt["city"]      == city_sel]
        if spec_sel  != "All": filt = filt[filt["specialty"] == spec_sel]
        if search_q.strip():   filt = filt[filt["name"].str.contains(search_q, case=False, na=False)]

        st.caption(f"Showing **{len(filt)}** lawyer(s)")

        for _, lw in filt.iterrows():
            with st.container(border=True):
                ci, cb = st.columns([3, 1])
                with ci:
                    st.markdown(f"### {lw['name']}")
                    st.markdown(f"📍 **{lw['city']}** | ⚖️ **{lw['specialty']}** | 📞 {lw['phone']}")
                    st.markdown(f"<p style='color:#8b949e'>{lw['bio']}</p>", unsafe_allow_html=True)

                ckey = f"contact_{lw['id']}"
                with cb:
                    if st.session_state.user_info["role"] == "Citizen":
                        if st.button("📩 Contact", key=f"btn_{lw['id']}", use_container_width=True):
                            st.session_state[ckey] = not st.session_state.get(ckey, False)
                    else:
                        st.caption("Log in as Citizen to send requests.")

            if st.session_state.get(ckey, False):
                with st.form(key=f"form_{lw['id']}"):
                    st.markdown(f"**Send appointment request to {lw['name']}:**")
                    msg = st.text_area(
                        "Describe your legal issue:",
                        placeholder="Briefly describe your situation so the lawyer can understand your needs…",
                    )
                    cs, cc = st.columns(2)
                    submitted = cs.form_submit_button("📤 Send Request",   use_container_width=True)
                    cancelled = cc.form_submit_button("✖ Cancel",          use_container_width=True)

                    if submitted:
                        if msg.strip():
                            auth.send_appointment_request(
                                st.session_state.user_info["id"], lw["id"], msg
                            )
                            st.success(f"✅ Request sent to {lw['name']}!")
                            st.session_state[ckey] = False
                            st.rerun()
                        else:
                            st.error("Please describe your issue before sending.")
                    if cancelled:
                        st.session_state[ckey] = False
                        st.rerun()

# ── APPOINTMENTS DASHBOARD ─────────────────────────────────────────────────────
elif st.session_state.page == "appointments":
    if st.button("⬅️ Back", key="appt_back"):
        go_home()

    user = st.session_state.user_info

    # ── LAWYER VIEW ───────────────────────────────────────────────────────────
    if user["role"] == "Lawyer":
        st.header("📋 My Appointment Requests")
        appts = auth.get_lawyer_appointments(user["id"])

        if not appts:
            st.info("📭 You have no appointment requests yet.")
        else:
            pending_n = sum(1 for a in appts if a["status"] == "Pending")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total",    len(appts))
            m2.metric("Pending",  pending_n)
            m3.metric("Resolved", len(appts) - pending_n)
            st.divider()

            status_filter = st.selectbox("Filter by Status", ["All", "Pending", "Accepted", "Declined"])

            for appt in appts:
                if status_filter != "All" and appt["status"] != status_filter:
                    continue
                badge_cls = {
                    "Pending":  "badge-pending",
                    "Accepted": "badge-accepted",
                    "Declined": "badge-declined",
                }.get(appt["status"], "badge-pending")
                date_str = appt["created_at"][:10] if appt["created_at"] else "N/A"

                with st.container(border=True):
                    ci2, ca2 = st.columns([3, 2])
                    with ci2:
                        st.markdown(f"**👤 {appt['citizen_name']}** | 📞 {appt['citizen_phone']}")
                        st.markdown(
                            f"<span class='badge {badge_cls}'>{appt['status']}</span> "
                            f"<span style='color:#8b949e;font-size:.85rem'>— {date_str}</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Issue:** {appt['message']}")
                        if appt["response"]:
                            st.markdown(f"*Your note:* {appt['response']}")

                    if appt["status"] == "Pending":
                        with ca2:
                            with st.form(key=f"resp_{appt['id']}"):
                                note = st.text_area(
                                    "Response / Notes (optional):",
                                    placeholder="Add a message for the client…",
                                    key=f"note_{appt['id']}",
                                )
                                col_a, col_d = st.columns(2)
                                if col_a.form_submit_button("✅ Accept",  use_container_width=True):
                                    auth.respond_to_appointment(appt["id"], "Accepted", note)
                                    st.rerun()
                                if col_d.form_submit_button("❌ Decline", use_container_width=True):
                                    auth.respond_to_appointment(appt["id"], "Declined", note)
                                    st.rerun()

    # ── CITIZEN VIEW ──────────────────────────────────────────────────────────
    elif user["role"] == "Citizen":
        st.header("📋 My Appointment Requests")
        appts = auth.get_citizen_appointments(user["id"])

        if not appts:
            st.info("📭 You haven't sent any requests yet.")
            if st.button("⚖️ Find a Lawyer", key="find_lw"):
                st.session_state.page = "directory"; st.rerun()
        else:
            for appt in appts:
                badge_cls = {
                    "Pending":  "badge-pending",
                    "Accepted": "badge-accepted",
                    "Declined": "badge-declined",
                }.get(appt["status"], "badge-pending")
                date_str = appt["created_at"][:10] if appt["created_at"] else "N/A"

                with st.container(border=True):
                    st.markdown(f"**👨‍⚖️ {appt['lawyer_name']}** | 📞 {appt['lawyer_phone']}")
                    st.markdown(
                        f"<span class='badge {badge_cls}'>{appt['status']}</span> "
                        f"<span style='color:#8b949e;font-size:.85rem'>— Sent {date_str}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Your Request:** {appt['message']}")
                    if appt["response"]:
                        if appt["status"] == "Accepted":
                            st.success(f"**Lawyer's Response:** {appt['response']}")
                        else:
                            st.warning(f"**Lawyer's Note:** {appt['response']}")

    else:
        st.error("⛔ This page is only for Citizens and Lawyers.")

# ── CONTRACT GENERATOR ────────────────────────────────────────────────────────
elif st.session_state.page == "contract":

    hdr_col, back_col = st.columns([5, 1])
    hdr_col.header("✍️ Automated Contract Generator")
    if back_col.button("⬅️ Home", key="contract_back"):
        st.session_state.pop("_viewing_contract", None)
        go_home()

    past_contracts = vault_manager.get_user_chats(st.session_state.user_info["id"], session_type="contract")
    with st.expander(f"📜 Past Contracts ({len(past_contracts)})", expanded=False):
        if not past_contracts:
            st.caption("No saved contracts yet. Generate one below!")
        else:
            for sess in past_contracts:
                c_cols = st.columns([6, 1])
                if c_cols[0].button(f"📜 {sess['session_name'][:30]}", key=f"cont_{sess['id']}", use_container_width=True):
                    loaded_contract = vault_manager.load_chat(sess["id"])
                    st.session_state["_viewing_contract"] = loaded_contract[0]["content"] if loaded_contract else ""
                    st.session_state["_viewing_contract_name"] = sess["session_name"]
                    st.rerun()
                if c_cols[1].button("🗑️", key=f"del_cont_{sess['id']}", help="Delete"):
                    vault_manager.delete_chat(sess["id"])
                    st.session_state.pop("_viewing_contract", None)
                    st.rerun()

    # ── Show a previously viewed contract ──────────────────────────────────────
    if st.session_state.get("_viewing_contract"):
        st.button("⬅️ Back to Generator", key="contract_back_view",
                  on_click=lambda: st.session_state.pop("_viewing_contract", None))
        st.header(f"📜 {st.session_state.get('_viewing_contract_name', 'Saved Contract')}")
        st.markdown(st.session_state["_viewing_contract"])
        st.download_button("⬇️ Download (.txt)",
                           data=st.session_state["_viewing_contract"].encode("utf-8"),
                           file_name=f"{st.session_state.get('_viewing_contract_name','contract')}.txt",
                           mime="text/plain", use_container_width=True)
        st.stop()

    st.header("✍️ Automated Contract Generator")
    st.markdown("<p style='color:#8b949e;'>Generate professional legal contracts powered by AI.</p>",
                unsafe_allow_html=True)

    # ── Language Selection ──────────────────────────────────────────────────────
    lang_choice = st.radio("🌐 Contract Language / لغة العقد", ["العربية (Arabic)", "English"], horizontal=True, key="contract_lang")
    is_ar = "العربية" in lang_choice

    c_type_options = (
        ["عقد إيجار", "عقد عمل", "عقد بيع", "عقد مقاولة"] if is_ar
        else ["Lease Agreement", "Employment Contract", "Sales Contract", "Contractor Agreement"]
    )
    c_type = st.selectbox("📋 نوع العقد" if is_ar else "📋 Contract Type", c_type_options, key="ctype_sel")

    st.divider()
    contract_data = {}

    # ── Helper: generate contract (AraT5 for Arabic, Llama 3 for English) ──────
    def _generate_and_save(prompt, spinner_msg, sess_title, validator_category=None, arat5_short_prompt=None):
        full_contract = ""
        arat5_m, arat5_t = load_arat5_generator()
        use_arat5 = (is_ar and arat5_short_prompt is not None
                     and arat5_m is not None and arat5_t is not None)

        if use_arat5:
            # AraT5: fine-tuned Egyptian contract generator (Arabic only)
            with st.spinner(spinner_msg):
                try:
                    inputs = arat5_t(
                        arat5_short_prompt,
                        return_tensors="pt",
                        max_length=128,
                        truncation=True,
                        padding=True,
                    )
                    with torch.no_grad():
                        outputs = arat5_m.generate(
                            **inputs,
                            max_new_tokens=512,
                            num_beams=4,
                            early_stopping=True,
                            no_repeat_ngram_size=3,
                        )
                    full_contract = arat5_t.decode(outputs[0], skip_special_tokens=True)
                    st.markdown(full_contract)
                except Exception:
                    use_arat5 = False  # silently fall back to Llama 3

        if not use_arat5:
            # Llama 3 via Ollama: used for English contracts and as fallback
            with st.spinner(spinner_msg):
                box = st.empty()
                try:
                    for chunk in llm.stream(prompt):
                        full_contract += chunk.content
                        box.markdown(full_contract + "▌")
                    box.markdown(full_contract)
                except Exception:
                    st.error("⚠️ **عذراً، محرك الذكاء الاصطناعي لا يعمل (AI Engine Offline):** يرجى التأكد من تشغيل خادم Ollama في الخلفية." if is_ar
                             else "⚠️ **AI Engine Offline:** Please make sure Ollama is running in the background.")
                    st.stop()

        if full_contract:
            vault_manager.save_chat(
                st.session_state.user_info["id"], sess_title,
                [{"role": "assistant", "content": full_contract}],
                session_type="contract",
            )
            # ── Contract V&V (Verification & Validation) ─────────────────────
            if validator_category:
                try:
                    vv = ContractValidator()
                    is_valid, struct_errs, legal_warns = vv.process_ai_output(
                        full_contract, validator_category
                    )
                    if is_valid:
                        st.success("✅ **تحقق العقد:** العقد مكتمل قانونياً ويحتوي على جميع البنود المطلوبة." if is_ar
                                   else "✅ **Contract V&V:** Contract is legally sound — all required clauses present.")
                    else:
                        with st.warning("⚠️ **تحقق العقد:** يُرجى مراجعة التحذيرات أدناه." if is_ar
                                        else "⚠️ **Contract V&V:** Review the validation warnings below."):
                            pass
                        if struct_errs:
                            label = "أخطاء هيكلية:" if is_ar else "Structural Errors:"
                            st.error(f"**{label}** " + " | ".join(struct_errs))
                        if legal_warns:
                            label = "تحذيرات قانونية:" if is_ar else "Legal Warnings:"
                            st.warning(f"**{label}** " + " | ".join(legal_warns))
                except Exception:
                    pass  # Never block contract delivery due to validator failure

        return full_contract

    # ─────────────────────────────────────────────────────────
    # LEASE AGREEMENT
    # ─────────────────────────────────────────────────────────
    if c_type in ("عقد إيجار", "Lease Agreement"):
        st.subheader("🏠 عقد إيجار" if is_ar else "🏠 Lease Agreement")
        with st.container(border=True):
            st.markdown("**🧑 الأطراف**" if is_ar else "**🧑 Parties**")
            c1, c2 = st.columns(2)
            contract_data["landlord"] = c1.text_input("🧑 المؤجر (الطرف الأول) *" if is_ar else "🧑 Landlord (First Party) *", placeholder="الاسم الكامل" if is_ar else "Full name or company")
            contract_data["tenant"]   = c2.text_input("🧑 المستأجر (الطرف الثاني) *" if is_ar else "🧑 Tenant (Second Party) *", placeholder="الاسم الكامل" if is_ar else "Full name")

        with st.container(border=True):
            st.markdown("**🏠 بيانات العقار**" if is_ar else "**🏠 Property Details**")
            c1, c2 = st.columns(2)
            prop_types = ["شقة", "عمارة", "محل تجاري", "مكتب", "مستودع", "أرض"] if is_ar else ["Apartment", "Building", "Store", "Office", "Warehouse", "Land"]
            contract_data["prop_type"]  = c1.selectbox("🏠 نوع العقار" if is_ar else "🏠 Property Type", prop_types)
            contract_data["prop_floor"] = c2.text_input("🏢 الدور / رقم الوحدة" if is_ar else "🏢 Floor / Unit No.", placeholder="مثال: الدور 3، شقة 5" if is_ar else "e.g. Floor 3, Apartment 5")
            contract_data["prop_addr"]  = st.text_input("📍 عنوان العقار *" if is_ar else "📍 Full Property Address *", placeholder="الشارع، الحي، المدينة" if is_ar else "Street, District, City")
            c3, c4 = st.columns(2)
            contract_data["prop_area"]  = c3.text_input("📏 المساحة (م²)" if is_ar else "📏 Area (m²)", placeholder="مثال: 120 م²" if is_ar else "e.g. 120 m²")
            furn_opts = ["غير مؤثث", "مؤثث جزئياً", "مؤثث بالكامل"] if is_ar else ["Unfurnished", "Semi-Furnished", "Fully Furnished"]
            contract_data["furnishing"] = c4.selectbox("🛋️ التأثيث" if is_ar else "🛋️ Furnishing", furn_opts)

        with st.container(border=True):
            st.markdown("**💰 الشروط المالية**" if is_ar else "**💰 Financial Terms**")
            c1, c2, c3 = st.columns(3)
            contract_data["rent_amount"]  = c1.number_input("💵 الإيجار الشهري (ج.م) *" if is_ar else "💵 Monthly Rent (EGP) *", 0, 10_000_000, 5000, step=500)
            contract_data["deposit"]      = c2.number_input("🔒 تأمينات (ج.م)" if is_ar else "🔒 Security Deposit (EGP)", 0, 10_000_000, 10000, step=500)
            contract_data["pay_due_day"]  = c3.number_input("📅 يوم السداد (1–28)" if is_ar else "📅 Payment Due Day (1–28)", 1, 28, 5)
            c4, c5 = st.columns(2)
            contract_data["start_date"]   = c4.date_input("📅 تاريخ البداية" if is_ar else "📅 Start Date")
            contract_data["duration"]     = c5.text_input("⏱️ مدة العقد *" if is_ar else "⏱️ Duration *", placeholder="مثال: سنة واحدة" if is_ar else "e.g. 1 year")
            c6, c7 = st.columns(2)
            contract_data["late_penalty"] = c6.text_input("⚠️ غرامة التأخير" if is_ar else "⚠️ Late Payment Penalty", placeholder="مثال: 2% شهرياً" if is_ar else "e.g. 2% per month")
            contract_data["notice_period"]= c7.text_input("📬 مدة الإخطار" if is_ar else "📬 Notice Period", placeholder="مثال: 30 يوم" if is_ar else "e.g. 30 days")

        with st.container(border=True):
            st.markdown("**💡 الخدمات**" if is_ar else "**💡 Utilities & Extras**")
            c1, c2, c3 = st.columns(3)
            contract_data["util_elec"]  = c1.checkbox("⚡ كهرباء" if is_ar else "⚡ Electricity included")
            contract_data["util_water"] = c2.checkbox("💧 مياه" if is_ar else "💧 Water included")
            contract_data["util_gas"]   = c3.checkbox("🔥 غاز" if is_ar else "🔥 Gas included")
            contract_data["special"]    = st.text_area("📝 شروط إضافية" if is_ar else "📝 Additional Terms", placeholder="أي شروط خاصة..." if is_ar else "Any specific conditions...", height=80)

        required_ok = contract_data["landlord"].strip() and contract_data["tenant"].strip() and contract_data["prop_addr"].strip() and contract_data["duration"].strip()
        if st.button("📄 إنشاء عقد الإيجار" if is_ar else "📄 Generate Lease Contract", use_container_width=True, key="gen_lease"):
            if not required_ok:
                st.error("❌ يرجى ملء جميع الحقول المطلوبة *" if is_ar else "❌ Please fill in all required fields marked with *")
            else:
                util_list = ", ".join(filter(None, [
                    ("كهرباء" if is_ar else "Electricity") if contract_data["util_elec"] else "",
                    ("مياه" if is_ar else "Water") if contract_data["util_water"] else "",
                    ("غاز" if is_ar else "Gas") if contract_data["util_gas"] else "",
                ])) or ("لا توجد خدمات مشمولة" if is_ar else "None")
                if is_ar:
                    prompt = f"""أنت محامي مصري متخصص في عقود الإيجار. صغ عقد إيجار كاملاً ورسمياً باللغة العربية الفصحى بالبيانات الآتية:
- المؤجر (الطرف الأول): {contract_data['landlord']}
- المستأجر (الطرف الثاني): {contract_data['tenant']}
- نوع العقار: {contract_data['prop_type']}
- الدور / الوحدة: {contract_data['prop_floor']}
- عنوان العقار: {contract_data['prop_addr']}
- المساحة: {contract_data['prop_area']}
- حالة التأثيث: {contract_data['furnishing']}
- الإيجار الشهري: {contract_data['rent_amount']} جنيه مصري
- يوم السداد: اليوم {contract_data['pay_due_day']} من كل شهر
- التأمينات: {contract_data['deposit']} جنيه مصري
- تاريخ البدء: {contract_data['start_date']}
- مدة العقد: {contract_data['duration']}
- غرامة التأخير: {contract_data['late_penalty'] or 'لم تحدد'}
- مدة الإخطار: {contract_data['notice_period'] or 'لم تحدد'}
- الخدمات المشمولة: {util_list}
- شروط إضافية: {contract_data['special'] or 'لا توجد'}
اكتب العقد الكامل بجميع بنوده القانونية (التعريفات، الالتزامات، إنهاء العقد، فض النزاعات، التوقيعات). ابدأ مباشرة بنص العقد."""
                else:
                    prompt = f"""You are an expert Egyptian lawyer specializing in lease agreements. Draft a complete, formal lease contract in English based on the following details:
- Landlord (First Party): {contract_data['landlord']}
- Tenant (Second Party): {contract_data['tenant']}
- Property Type: {contract_data['prop_type']}
- Floor / Unit: {contract_data['prop_floor']}
- Property Address: {contract_data['prop_addr']}
- Area: {contract_data['prop_area']}
- Furnishing: {contract_data['furnishing']}
- Monthly Rent: {contract_data['rent_amount']} EGP
- Payment Due Day: Day {contract_data['pay_due_day']} of each month
- Security Deposit: {contract_data['deposit']} EGP
- Start Date: {contract_data['start_date']}
- Duration: {contract_data['duration']}
- Late Penalty: {contract_data['late_penalty'] or 'Not specified'}
- Notice Period: {contract_data['notice_period'] or 'Not specified'}
- Utilities Included: {util_list}
- Additional Terms: {contract_data['special'] or 'None'}
Write the full contract with all legal clauses (definitions, obligations, termination, dispute resolution, signatures). Start directly with the contract text."""
                sess_title = f"{'عقد إيجار' if is_ar else 'Lease'}: {contract_data['landlord']} ↔ {contract_data['tenant']}"
                arat5_prompt = (
                    f"صغ عقد: اكتب عقد إيجار {contract_data['prop_type']} بين "
                    f"الطرف الأول {contract_data['landlord']} والطرف الثاني {contract_data['tenant']} "
                    f"في {contract_data['prop_addr']} لمدة {contract_data['duration']} "
                    f"بإيجار {contract_data['rent_amount']} جنيه شهرياً"
                )
                full_contract = _generate_and_save(prompt, "✍️ جاري صياغة العقد…" if is_ar else "✍️ Drafting your lease contract…", sess_title, validator_category="lease_or_sale", arat5_short_prompt=arat5_prompt)
                st.download_button("⬇️ تحميل العقد (.txt)" if is_ar else "⬇️ Download Contract (.txt)",
                    data=full_contract.encode("utf-8"),
                    file_name=f"Lease_{contract_data['landlord']}_{contract_data['tenant']}.txt",
                    mime="text/plain", use_container_width=True)

    # ─────────────────────────────────────────────────────────
    # EMPLOYMENT CONTRACT
    # ─────────────────────────────────────────────────────────
    elif c_type in ("عقد عمل", "Employment Contract"):
        st.subheader("💼 عقد عمل" if is_ar else "💼 Employment Contract")
        with st.container(border=True):
            st.markdown("**🧑 الأطراف**" if is_ar else "**🧑 Parties**")
            c1, c2 = st.columns(2)
            contract_data["employer"] = c1.text_input("🏢 صاحب العمل *" if is_ar else "🏢 Employer (First Party) *", placeholder="اسم الشركة أو الشخص" if is_ar else "Company / Person name")
            contract_data["employee"] = c2.text_input("🧑 الموظف *" if is_ar else "🧑 Employee (Second Party) *", placeholder="الاسم الكامل" if is_ar else "Full name")

        with st.container(border=True):
            st.markdown("**💼 تفاصيل الوظيفة**" if is_ar else "**💼 Job Details**")
            c1, c2 = st.columns(2)
            contract_data["job_title"]  = c1.text_input("💼 المسمى الوظيفي *" if is_ar else "💼 Job Title *", placeholder="مثال: مهندس برمجيات" if is_ar else "e.g. Software Engineer")
            contract_data["department"] = c2.text_input("🏛️ القسم" if is_ar else "🏛️ Department", placeholder="مثال: التكنولوجيا" if is_ar else "e.g. Technology")
            contract_data["work_location"] = st.text_input("📍 مكان العمل *" if is_ar else "📍 Work Location *", placeholder="المدينة أو العنوان" if is_ar else "City or Full address")
            c3, c4 = st.columns(2)
            contract_data["start_date"]    = c3.date_input("📅 تاريخ بدء العمل" if is_ar else "📅 Start Date")
            kind_opts = ["دائم", "مؤقت", "فترة تجريبية"] if is_ar else ["Permanent", "Fixed-Term", "Probation"]
            contract_data["contract_kind"] = c4.selectbox("📝 نوع العقد" if is_ar else "📝 Contract Type", kind_opts)
            c5, c6 = st.columns(2)
            contract_data["probation"]     = c5.text_input("⏱️ فترة التجربة" if is_ar else "⏱️ Probation Period", placeholder="مثال: 3 أشهر" if is_ar else "e.g. 3 months")
            contract_data["notice_period"] = c6.text_input("📬 مدة الإخطار" if is_ar else "📬 Notice Period", placeholder="مثال: 30 يوم" if is_ar else "e.g. 30 days")

        with st.container(border=True):
            st.markdown("**💰 المكافآت**" if is_ar else "**💰 Compensation**")
            c1, c2, c3 = st.columns(3)
            contract_data["monthly_salary"] = c1.number_input("💵 الراتب الشهري (ج.م) *" if is_ar else "💵 Monthly Salary (EGP) *", 0, 10_000_000, 8000, step=500)
            contract_data["work_hours"]     = c2.number_input("⏰ ساعات العمل يومياً" if is_ar else "⏰ Working Hours/Day", 1, 24, 8)
            contract_data["work_days"]      = c3.number_input("📅 أيام العمل أسبوعياً" if is_ar else "📅 Working Days/Week", 1, 7, 5)
            c4, c5 = st.columns(2)
            contract_data["annual_leave"] = c4.number_input("🏖️ الإجازة السنوية (أيام)" if is_ar else "🏖️ Annual Leave (days)", 0, 365, 21)
            contract_data["social_ins"]   = c5.checkbox("✅ تأمين اجتماعي مشمول" if is_ar else "✅ Social Insurance Included")
            contract_data["benefits"]     = st.text_area("🎁 مزايا إضافية" if is_ar else "🎁 Additional Benefits", placeholder="مثال: بدل مواصلات، تأمين صحي" if is_ar else "e.g. Transport allowance, Health insurance", height=70)

        required_ok = contract_data["employer"].strip() and contract_data["employee"].strip() and contract_data["job_title"].strip()
        if st.button("📄 إنشاء عقد العمل" if is_ar else "📄 Generate Employment Contract", use_container_width=True, key="gen_emp"):
            if not required_ok:
                st.error("❌ يرجى ملء جميع الحقول المطلوبة *" if is_ar else "❌ Please fill in all fields marked with *")
            else:
                social = ("مدرج" if is_ar else "Included") if contract_data['social_ins'] else ("غير مدرج" if is_ar else "Not included")
                if is_ar:
                    prompt = f"""أنت محامي مصري متخصص. صغ عقد عمل كاملاً باللغة العربية الفصحى:
- صاحب العمل (الطرف الأول): {contract_data['employer']}
- الموظف (الطرف الثاني): {contract_data['employee']}
- المسمى الوظيفي: {contract_data['job_title']}
- القسم: {contract_data['department'] or 'لم يحدد'}
- مكان العمل: {contract_data['work_location']}
- تاريخ البدء: {contract_data['start_date']}
- نوع العقد: {contract_data['contract_kind']}
- فترة التجربة: {contract_data['probation'] or 'لا توجد'}
- الراتب الشهري: {contract_data['monthly_salary']} جنيه مصري
- ساعات العمل: {contract_data['work_hours']} ساعات / يومياً
- أيام العمل: {contract_data['work_days']} أيام / أسبوعياً
- الإجازة السنوية: {contract_data['annual_leave']} يوماً
- التأمين الاجتماعي: {social}
- مدة الإخطار: {contract_data['notice_period'] or 'لم تحدد'}
- مزايا إضافية: {contract_data['benefits'] or 'لا توجد'}
اكتب العقد بجميع بنوده القانونية. ابدأ مباشرة بنص العقد."""
                else:
                    prompt = f"""You are an expert Egyptian lawyer. Draft a complete, formal employment contract in English:
- Employer (First Party): {contract_data['employer']}
- Employee (Second Party): {contract_data['employee']}
- Job Title: {contract_data['job_title']}
- Department: {contract_data['department'] or 'Not specified'}
- Work Location: {contract_data['work_location']}
- Start Date: {contract_data['start_date']}
- Contract Type: {contract_data['contract_kind']}
- Probation Period: {contract_data['probation'] or 'None'}
- Monthly Salary: {contract_data['monthly_salary']} EGP
- Working Hours: {contract_data['work_hours']} hours/day
- Working Days: {contract_data['work_days']} days/week
- Annual Leave: {contract_data['annual_leave']} days
- Social Insurance: {social}
- Notice Period: {contract_data['notice_period'] or 'Not specified'}
- Additional Benefits: {contract_data['benefits'] or 'None'}
Write the full contract with all legal clauses. Start directly with the contract text."""
                sess_title = f"{'عقد عمل' if is_ar else 'Employment'}: {contract_data['employer']} ↔ {contract_data['employee']}"
                arat5_prompt = (
                    f"صغ عقد: اكتب عقد عمل بين صاحب العمل {contract_data['employer']} "
                    f"والموظف {contract_data['employee']} لمنصب {contract_data['job_title']} "
                    f"براتب {contract_data['monthly_salary']} جنيه شهرياً في {contract_data['work_location']}"
                )
                full_contract = _generate_and_save(prompt, "✍️ جاري صياغة العقد…" if is_ar else "✍️ Drafting employment contract…", sess_title, validator_category="employment", arat5_short_prompt=arat5_prompt)
                st.download_button("⬇️ تحميل (.txt)" if is_ar else "⬇️ Download (.txt)", data=full_contract.encode("utf-8"),
                    file_name=f"Employment_{contract_data['employer']}_{contract_data['employee']}.txt",
                    mime="text/plain", use_container_width=True)

    # ─────────────────────────────────────────────────────────
    # SALES CONTRACT
    # ─────────────────────────────────────────────────────────
    elif c_type in ("عقد بيع", "Sales Contract"):
        st.subheader("🛒 عقد بيع" if is_ar else "🛒 Sales Contract")
        with st.container(border=True):
            st.markdown("**🧑 الأطراف**" if is_ar else "**🧑 Parties**")
            c1, c2 = st.columns(2)
            contract_data["seller"] = c1.text_input("🧑 البائع *" if is_ar else "🧑 Seller (First Party) *", placeholder="الاسم الكامل" if is_ar else "Full name or company")
            contract_data["buyer"]  = c2.text_input("🧑 المشتري *" if is_ar else "🧑 Buyer (Second Party) *", placeholder="الاسم الكامل" if is_ar else "Full name")

        with st.container(border=True):
            st.markdown("**📦 تفاصيل المبيع**" if is_ar else "**📦 Item / Property Details**")
            c1, c2 = st.columns(2)
            item_opts = ["سيارة", "عقار", "أرض", "بضائع", "معدات", "أخرى"] if is_ar else ["Car", "Real Estate", "Land", "Goods", "Equipment", "Other"]
            contract_data["item_type"] = c1.selectbox("🏷️ نوع البيع" if is_ar else "🏷️ Item Type", item_opts)
            contract_data["item_desc"] = c2.text_input("📝 وصف المبيع *" if is_ar else "📝 Item Description *", placeholder="مثال: تويوتا كورولا 2020" if is_ar else "e.g. Toyota Corolla 2020, White")
            contract_data["item_id"]   = st.text_input("📋 رقم التعريف / التسجيل" if is_ar else "📋 ID / Serial / Registration", placeholder="مثال: لوحة السيارة" if is_ar else "e.g. Car plate / Property doc no.")

        with st.container(border=True):
            st.markdown("**💰 السعر والدفع**" if is_ar else "**💰 Price & Payment**")
            c1, c2 = st.columns(2)
            contract_data["price"] = c1.number_input("💵 سعر البيع (ج.م) *" if is_ar else "💵 Sale Price (EGP) *", 0, 100_000_000, 100000, step=1000)
            pay_opts = ["نقداً", "تحويل بنكي", "تقسيط", "دفعة وأقساط"] if is_ar else ["Cash", "Bank Transfer", "Installments", "Down Payment + Installments"]
            contract_data["payment_method"] = c2.selectbox("💳 طريقة الدفع" if is_ar else "💳 Payment Method", pay_opts)
            contract_data["installment_detail"] = st.text_input("📅 تفاصيل التقسيط" if is_ar else "📅 Installment Details", placeholder="مثال: 12 قسط شهري" if is_ar else "e.g. 12 monthly installments of 5,000 EGP each")
            c3, c4 = st.columns(2)
            contract_data["delivery_date"]  = c3.date_input("📅 تاريخ التسليم" if is_ar else "📅 Delivery Date")
            contract_data["delivery_place"] = c4.text_input("📍 مكان التسليم" if is_ar else "📍 Delivery Location", placeholder="العنوان أو المدينة" if is_ar else "Address or city")
            contract_data["warranty"]       = st.text_input("✅ شروط الضمان" if is_ar else "✅ Warranty Terms", placeholder="مثال: ضمان سنة" if is_ar else "e.g. 1 year warranty on engine")
            contract_data["special"]        = st.text_area("📝 شروط إضافية" if is_ar else "📝 Additional Terms", placeholder="أي شروط خاصة..." if is_ar else "Any specific conditions…", height=70)

        required_ok = contract_data["seller"].strip() and contract_data["buyer"].strip() and contract_data["item_desc"].strip()
        if st.button("📄 إنشاء عقد البيع" if is_ar else "📄 Generate Sales Contract", use_container_width=True, key="gen_sale"):
            if not required_ok:
                st.error("❌ يرجى ملء جميع الحقول المطلوبة *" if is_ar else "❌ Please fill in all fields marked with *")
            else:
                na = "لم يذكر" if is_ar else "Not specified"
                none_txt = "لا توجد" if is_ar else "None"
                if is_ar:
                    prompt = f"""أنت محامي مصري متخصص. صغ عقد بيع كاملاً باللغة العربية الفصحى:
- البائع: {contract_data['seller']} | المشتري: {contract_data['buyer']}
- نوع البيع: {contract_data['item_type']}
- وصف المبيع: {contract_data['item_desc']}
- رقم التعريف / التسجيل: {contract_data['item_id'] or na}
- سعر البيع: {contract_data['price']} جنيه مصري
- طريقة الدفع: {contract_data['payment_method']}
- تفاصيل التقسيط: {contract_data['installment_detail'] or 'لا ينطبق'}
- تاريخ التسليم: {contract_data['delivery_date']}
- مكان التسليم: {contract_data['delivery_place'] or na}
- شروط الضمان: {contract_data['warranty'] or none_txt}
- شروط إضافية: {contract_data['special'] or none_txt}
اكتب العقد بجميع بنوده القانونية. ابدأ مباشرة بنص العقد."""
                else:
                    prompt = f"""You are an expert Egyptian lawyer. Draft a complete, formal sales contract in English:
- Seller: {contract_data['seller']} | Buyer: {contract_data['buyer']}
- Item Type: {contract_data['item_type']}
- Item Description: {contract_data['item_desc']}
- ID / Registration: {contract_data['item_id'] or na}
- Sale Price: {contract_data['price']} EGP
- Payment Method: {contract_data['payment_method']}
- Installment Details: {contract_data['installment_detail'] or 'N/A'}
- Delivery Date: {contract_data['delivery_date']}
- Delivery Location: {contract_data['delivery_place'] or na}
- Warranty Terms: {contract_data['warranty'] or none_txt}
- Additional Terms: {contract_data['special'] or none_txt}
Write the full contract with all legal clauses. Start directly with the contract text."""
                sess_title = f"{'عقد بيع' if is_ar else 'Sales'}: {contract_data['seller']} ↔ {contract_data['buyer']}"
                arat5_prompt = (
                    f"صغ عقد: اكتب عقد بيع {contract_data['item_type']} بين "
                    f"البائع {contract_data['seller']} والمشتري {contract_data['buyer']} "
                    f"بسعر {contract_data['price']} جنيه مصري وصف المبيع: {contract_data['item_desc']}"
                )
                full_contract = _generate_and_save(prompt, "✍️ جاري صياغة العقد…" if is_ar else "✍️ Drafting sales contract…", sess_title, validator_category="lease_or_sale", arat5_short_prompt=arat5_prompt)
                st.download_button("⬇️ تحميل (.txt)" if is_ar else "⬇️ Download (.txt)", data=full_contract.encode("utf-8"),
                    file_name=f"Sales_{contract_data['seller']}_{contract_data['buyer']}.txt",
                    mime="text/plain", use_container_width=True)

    # ─────────────────────────────────────────────────────────
    # CONTRACTOR AGREEMENT
    # ─────────────────────────────────────────────────────────
    else:
        st.subheader("🛠️ عقد مقاولة" if is_ar else "🛠️ Contractor Agreement")
        with st.container(border=True):
            st.markdown("**🧑 الأطراف**" if is_ar else "**🧑 Parties**")
            c1, c2 = st.columns(2)
            contract_data["client"]     = c1.text_input("💼 صاحب العمل *" if is_ar else "💼 Client (First Party) *", placeholder="اسم الشخص أو الشركة" if is_ar else "Person or company name")
            contract_data["contractor"] = c2.text_input("🛠️ المقاول *" if is_ar else "🛠️ Contractor (Second Party) *", placeholder="الاسم أو الشركة" if is_ar else "Name or company")

        with st.container(border=True):
            st.markdown("**🏗️ تفاصيل المشروع**" if is_ar else "**🏗️ Project Details**")
            c1, c2 = st.columns(2)
            proj_opts = ["بناء", "تشطيب وتجديد", "تشطيب داخلي", "بنية تحتية", "صيانة", "أخرى"] if is_ar else ["Building Construction", "Renovation", "Interior Design", "Infrastructure", "Maintenance", "Other"]
            contract_data["proj_type"]     = c1.selectbox("🏗️ نوع المشروع" if is_ar else "🏗️ Project Type", proj_opts)
            contract_data["proj_location"] = c2.text_input("📍 موقع المشروع *" if is_ar else "📍 Project Location *", placeholder="العنوان الكامل" if is_ar else "Full address")
            contract_data["proj_desc"]     = st.text_area("📝 وصف المشروع *" if is_ar else "📝 Project Description *", placeholder="وصف نطاق العمل بالتفصيل..." if is_ar else "Describe the scope of work in detail…", height=80)
            c3, c4 = st.columns(2)
            contract_data["start_date"] = c3.date_input("📅 تاريخ البدء" if is_ar else "📅 Start Date")
            contract_data["end_date"]   = c4.date_input("🏁 تاريخ الانتهاء" if is_ar else "🏁 End Date")

        with st.container(border=True):
            st.markdown("**💰 الشروط المالية**" if is_ar else "**💰 Financial Terms**")
            c1, c2 = st.columns(2)
            contract_data["total_value"]   = c1.number_input("💵 القيمة الإجمالية (ج.م) *" if is_ar else "💵 Total Contract Value (EGP) *", 0, 500_000_000, 50000, step=1000)
            contract_data["delay_penalty"] = c2.text_input("⚠️ غرامة التأخير يومياً" if is_ar else "⚠️ Delay Penalty per Day", placeholder="مثال: 500 ج.م/يوم" if is_ar else "e.g. 500 EGP/day")
            contract_data["pay_schedule"]  = st.text_input("📊 جدول الدفع" if is_ar else "📊 Payment Schedule", placeholder="مثال: 30% مقدم، 40% منتصف، 30% تسليم" if is_ar else "e.g. 30% upfront, 40% on halfway, 30% on completion")
            mat_opts = ["المقاول", "صاحب العمل", "مشترك"] if is_ar else ["Contractor", "Client", "Shared"]
            contract_data["materials"]   = st.selectbox("🧱 مسؤولية المواد" if is_ar else "🧱 Materials Provided By", mat_opts)
            contract_data["quality_std"] = st.text_input("✅ معايير الجودة" if is_ar else "✅ Quality Standards", placeholder="مثال: المواصفات المصرية" if is_ar else "e.g. Egyptian Standard ES 4756")
            contract_data["special"]     = st.text_area("📝 شروط إضافية" if is_ar else "📝 Additional Terms", placeholder="أي شروط خاصة..." if is_ar else "Any specific conditions…", height=70)

        required_ok = contract_data["client"].strip() and contract_data["contractor"].strip() and contract_data["proj_desc"].strip()
        if st.button("📄 إنشاء عقد المقاولة" if is_ar else "📄 Generate Contractor Agreement", use_container_width=True, key="gen_cont"):
            if not required_ok:
                st.error("❌ يرجى ملء جميع الحقول المطلوبة *" if is_ar else "❌ Please fill in all fields marked with *")
            else:
                na = "لم تحدد" if is_ar else "Not specified"
                none_txt = "لا توجد" if is_ar else "None"
                if is_ar:
                    prompt = f"""أنت محامي مصري متخصص. صغ عقد مقاولة كاملاً باللغة العربية الفصحى:
- صاحب العمل (الطرف الأول): {contract_data['client']}
- المقاول (الطرف الثاني): {contract_data['contractor']}
- نوع المشروع: {contract_data['proj_type']}
- موقع المشروع: {contract_data['proj_location']}
- وصف المشروع: {contract_data['proj_desc']}
- تاريخ البدء: {contract_data['start_date']} | تاريخ الانتهاء: {contract_data['end_date']}
- القيمة الإجمالية: {contract_data['total_value']} جنيه مصري
- جدول الدفع: {contract_data['pay_schedule'] or na}
- غرامة التأخير: {contract_data['delay_penalty'] or na}
- مسؤولية مواد البناء: {contract_data['materials']}
- معايير الجودة: {contract_data['quality_std'] or na}
- شروط إضافية: {contract_data['special'] or none_txt}
اكتب العقد بجميع بنوده القانونية. ابدأ مباشرة بنص العقد."""
                else:
                    prompt = f"""You are an expert Egyptian lawyer. Draft a complete, formal contractor agreement in English:
- Client (First Party): {contract_data['client']}
- Contractor (Second Party): {contract_data['contractor']}
- Project Type: {contract_data['proj_type']}
- Project Location: {contract_data['proj_location']}
- Project Description: {contract_data['proj_desc']}
- Start Date: {contract_data['start_date']} | End Date: {contract_data['end_date']}
- Total Value: {contract_data['total_value']} EGP
- Payment Schedule: {contract_data['pay_schedule'] or na}
- Delay Penalty: {contract_data['delay_penalty'] or na}
- Materials Responsibility: {contract_data['materials']}
- Quality Standards: {contract_data['quality_std'] or na}
- Additional Terms: {contract_data['special'] or none_txt}
Write the full contract with all legal clauses. Start directly with the contract text."""
                sess_title = f"{'عقد مقاولة' if is_ar else 'Contractor'}: {contract_data['client']} ↔ {contract_data['contractor']}"
                arat5_prompt = (
                    f"صغ عقد: اكتب عقد مقاولة بين صاحب العمل {contract_data['client']} "
                    f"والمقاول {contract_data['contractor']} لمشروع {contract_data['proj_type']} "
                    f"في {contract_data['proj_location']} بقيمة {contract_data['total_value']} جنيه مصري"
                )
                full_contract = _generate_and_save(prompt, "✍️ جاري صياغة العقد…" if is_ar else "✍️ Drafting contractor agreement…", sess_title, validator_category="partnership", arat5_short_prompt=arat5_prompt)
                st.download_button("⬇️ تحميل (.txt)" if is_ar else "⬇️ Download (.txt)", data=full_contract.encode("utf-8"),
                    file_name=f"Contractor_{contract_data['client']}_{contract_data['contractor']}.txt",
                    mime="text/plain", use_container_width=True)