"""
KnowLaw AI -- AraBERT Legal Domain Classifier
Fine-Tuning Pipeline (Train / Validate / Test)
================================================
Model   : aubmindlab/bert-base-arabertv2
Task    : Multi-class Arabic legal text classification
GPU     : CUDA-compatible GPU
Dataset : Cleaned Egyptian Law Dataset (5,340 rows, 18 CSV files)

Run:
    pip install transformers datasets torch scikit-learn pandas matplotlib seaborn
    python arabert_legal_classifier.py
"""

import os
import csv
import json
import time
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend -- safe on all systems
import matplotlib.pyplot as plt
import seaborn as sns

from pathlib import Path
from datetime import datetime

import torch
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup,
)
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
DATASET_DIR   = Path(__file__).parent.parent / "cleaned_datasets"
OUTPUT_DIR    = Path(__file__).parent / "outputs"
MODEL_NAME    = "aubmindlab/bert-base-arabertv2"
MAX_LEN       = 256       # max tokens (covers 98% of Arabic law article texts)
BATCH_SIZE    = 16        # safe for most GPUs
EPOCHS        = 5
LEARNING_RATE = 2e-5
WEIGHT_DECAY  = 0.01
WARMUP_RATIO  = 0.10      # 10% of total steps for warmup
TRAIN_RATIO   = 0.70
VAL_RATIO     = 0.15
TEST_RATIO    = 0.15      # must sum to 1.0
RANDOM_SEED   = 42
MIN_SAMPLES_PER_CLASS = 30   # drop classes with fewer samples

# Law category label map (CSV filename prefix -> human-readable domain)
LABEL_MAP = {
    "final_datset_for_civil_law":                       "Civil Law",
    "commircial_law_final_dataset":                     "Commercial Law",
    "dataset_companies_law":                            "Companies Law",
    "final_dataset_for_Criminal_Procedure":             "Criminal Procedure",
    "finished_dataset_for_penalty_law":                 "Penalty Law",
    "final_dataset_for_labor_constitution":             "Labor & Constitutional",
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

# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Logging
# ─────────────────────────────────────────────────────────────────────────────
LOG_FILE = None

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = "[{}]  {}".format(ts, msg)
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 -- LOAD & LABEL DATASET
# ─────────────────────────────────────────────────────────────────────────────
def load_dataset():
    log("Loading cleaned Egyptian law datasets...")
    all_rows = []
    csv_files = sorted(DATASET_DIR.glob("*.csv"))
    for path in csv_files:
        stem = path.stem
        label = None
        for key, name in LABEL_MAP.items():
            if stem.lower().startswith(key.lower()) or key.lower() in stem.lower():
                label = name
                break
        if label is None:
            label = stem.replace("_", " ").title()

        for enc in ["utf-8-sig", "utf-8", "windows-1256"]:
            try:
                df = pd.read_csv(path, encoding=enc, dtype=str)
                break
            except Exception:
                df = None
        if df is None or "text" not in df.columns:
            continue

        df = df[["text"]].copy()
        df["text"] = df["text"].astype(str).str.strip()
        df = df[df["text"].str.len() > 20]  # drop very short
        df["label"] = label
        all_rows.append(df)
        log("   Loaded {:>4} rows  [{}]  ->  {}".format(len(df), path.name, label))

    full_df = pd.concat(all_rows, ignore_index=True)
    log("Total rows loaded: {:,}".format(len(full_df)))

    # Drop classes with too few samples
    class_counts = full_df["label"].value_counts()
    valid_classes = class_counts[class_counts >= MIN_SAMPLES_PER_CLASS].index
    dropped = class_counts[class_counts < MIN_SAMPLES_PER_CLASS]
    if len(dropped):
        log("Dropping classes with < {} samples: {}".format(
            MIN_SAMPLES_PER_CLASS, dropped.to_dict()))
    full_df = full_df[full_df["label"].isin(valid_classes)].reset_index(drop=True)
    log("Final dataset: {:,} rows across {} classes".format(
        len(full_df), full_df["label"].nunique()))
    return full_df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 -- ENCODE LABELS & SPLIT
# ─────────────────────────────────────────────────────────────────────────────
def encode_and_split(df):
    le = LabelEncoder()
    df["label_id"] = le.fit_transform(df["label"])
    n_classes = len(le.classes_)
    log("Label encoding: {} classes".format(n_classes))
    for i, c in enumerate(le.classes_):
        log("   {:>2}  {}".format(i, c))

    # First split off test set, then split remainder into train/val
    X = df["text"].values
    y = df["label_id"].values

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=TEST_RATIO, random_state=RANDOM_SEED, stratify=y)
    val_relative = VAL_RATIO / (TRAIN_RATIO + VAL_RATIO)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_relative,
        random_state=RANDOM_SEED, stratify=y_trainval)

    log("Split  -  Train: {:,}  |  Val: {:,}  |  Test: {:,}".format(
        len(X_train), len(X_val), len(X_test)))
    return (X_train, y_train), (X_val, y_val), (X_test, y_test), le, n_classes


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 -- PyTorch DATASET
# ─────────────────────────────────────────────────────────────────────────────
class ArabicLegalDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts     = texts
        self.labels    = labels
        self.tokenizer = tokenizer
        self.max_len   = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "label":          torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 -- EVALUATION HELPER
# ─────────────────────────────────────────────────────────────────────────────
def evaluate(model, loader, device, criterion):
    model.eval()
    total_loss = 0.0
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            ids   = batch["input_ids"].to(device)
            mask  = batch["attention_mask"].to(device)
            labs  = batch["label"].to(device)
            out   = model(input_ids=ids, attention_mask=mask)
            loss  = criterion(out.logits, labs)
            total_loss += loss.item()
            preds = out.logits.argmax(dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labs.cpu().numpy())
    avg_loss = total_loss / len(loader)
    acc      = accuracy_score(all_labels, all_preds)
    f1       = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    return avg_loss, acc, f1, all_preds, all_labels


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 -- PLOTS
# ─────────────────────────────────────────────────────────────────────────────
def plot_learning_curves(history, output_dir):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("AraBERT Fine-Tuning -- Learning Curves\nKnowLaw AI (Egyptian Legal Classifier)",
                 fontsize=14, fontweight="bold")

    epochs = range(1, len(history["train_loss"]) + 1)

    # Loss
    axes[0].plot(epochs, history["train_loss"], "b-o", label="Train Loss", linewidth=2)
    axes[0].plot(epochs, history["val_loss"],   "r-o", label="Val Loss",   linewidth=2)
    axes[0].set_title("Cross-Entropy Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Accuracy
    axes[1].plot(epochs, [a * 100 for a in history["val_acc"]], "g-o",
                 label="Val Accuracy", linewidth=2)
    axes[1].axhline(y=max(history["val_acc"]) * 100, color="g", linestyle="--", alpha=0.5)
    axes[1].set_title("Validation Accuracy (%)")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_ylim([0, 100])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Macro F1
    axes[2].plot(epochs, history["val_f1"], "m-o", label="Val Macro F1", linewidth=2)
    axes[2].axhline(y=max(history["val_f1"]), color="m", linestyle="--", alpha=0.5)
    axes[2].set_title("Validation Macro F1 Score")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("Macro F1")
    axes[2].set_ylim([0, 1])
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    path = output_dir / "learning_curves.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log("Learning curves saved -> {}".format(path))


def plot_confusion_matrix(y_true, y_pred, class_names, output_dir):
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    n = len(class_names)
    figsize = max(12, n * 0.9)
    fig, ax = plt.subplots(figsize=(figsize, figsize * 0.8))
    sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names,
                ax=ax, linewidths=0.5)
    ax.set_ylabel("True Label", fontsize=12)
    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_title("Confusion Matrix (Normalised) -- Test Set\nAraBERT Legal Classifier", fontsize=13)
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    path = output_dir / "confusion_matrix.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log("Confusion matrix saved -> {}".format(path))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TRAINING LOOP
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global LOG_FILE
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = OUTPUT_DIR / "training_log.txt"

    log("=" * 65)
    log("KnowLaw AI -- AraBERT Legal Domain Classifier")
    log("=" * 65)

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem  = torch.cuda.get_device_properties(0).total_memory / 1e9
        log("GPU: {} ({:.1f} GB VRAM)".format(gpu_name, gpu_mem))
    else:
        log("WARNING: No GPU found -- training on CPU (will be slow)")

    torch.manual_seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    # ----- Load data --------------------------------------------------------
    df = load_dataset()
    (X_train, y_train), (X_val, y_val), (X_test, y_test), le, n_classes = \
        encode_and_split(df)

    # Save label mapping
    label_map_path = OUTPUT_DIR / "label_mapping.json"
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump({str(i): c for i, c in enumerate(le.classes_)}, f,
                  ensure_ascii=False, indent=2)
    log("Label map saved -> {}".format(label_map_path))

    # ----- Tokeniser + DataLoaders ------------------------------------------
    log("Loading tokeniser: {}".format(MODEL_NAME))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_ds = ArabicLegalDataset(X_train, y_train, tokenizer, MAX_LEN)
    val_ds   = ArabicLegalDataset(X_val,   y_val,   tokenizer, MAX_LEN)
    test_ds  = ArabicLegalDataset(X_test,  y_test,  tokenizer, MAX_LEN)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False,
                              num_workers=0, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False,
                              num_workers=0, pin_memory=True)

    # ----- Model ------------------------------------------------------------
    log("Loading model: {}".format(MODEL_NAME))
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=n_classes, ignore_mismatched_sizes=True)
    model = model.to(device)
    total_params = sum(p.numel() for p in model.parameters()) / 1e6
    log("Model parameters: {:.1f}M".format(total_params))

    # ----- Optimiser + Scheduler + Loss -------------------------------------
    total_steps  = len(train_loader) * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)
    log("Total training steps: {:,}  |  Warmup steps: {:,}".format(
        total_steps, warmup_steps))

    optimizer  = AdamW(model.parameters(), lr=LEARNING_RATE,
                       weight_decay=WEIGHT_DECAY)
    scheduler  = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps,
        num_training_steps=total_steps)
    criterion  = torch.nn.CrossEntropyLoss()

    # ----- Training Loop ----------------------------------------------------
    log("=" * 65)
    log("Starting training ({} epochs)...".format(EPOCHS))
    log("=" * 65)

    history = {"train_loss": [], "val_loss": [], "val_acc": [], "val_f1": []}
    best_val_f1   = 0.0
    best_epoch    = 0
    best_model_path = OUTPUT_DIR / "best_model"

    for epoch in range(1, EPOCHS + 1):
        epoch_start = time.time()
        model.train()
        train_loss_total = 0.0

        for step, batch in enumerate(train_loader, 1):
            ids   = batch["input_ids"].to(device)
            mask  = batch["attention_mask"].to(device)
            labs  = batch["label"].to(device)

            optimizer.zero_grad()
            out   = model(input_ids=ids, attention_mask=mask)
            loss  = criterion(out.logits, labs)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            train_loss_total += loss.item()

            if step % 50 == 0 or step == len(train_loader):
                avg = train_loss_total / step
                log("  Epoch {}/{} | Step {:>4}/{} | Train Loss: {:.4f}".format(
                    epoch, EPOCHS, step, len(train_loader), avg))

        avg_train_loss = train_loss_total / len(train_loader)

        # Validation
        val_loss, val_acc, val_f1, _, _ = evaluate(model, val_loader, device, criterion)
        elapsed = time.time() - epoch_start

        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)

        log("")
        log("EPOCH {}/{} SUMMARY  ({:.0f}s)".format(epoch, EPOCHS, elapsed))
        log("  Train Loss : {:.4f}".format(avg_train_loss))
        log("  Val Loss   : {:.4f}".format(val_loss))
        log("  Val Acc    : {:.2f}%".format(val_acc * 100))
        log("  Val F1     : {:.4f}".format(val_f1))
        log("")

        # Save best model
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch  = epoch
            model.save_pretrained(best_model_path)
            tokenizer.save_pretrained(best_model_path)
            log("  ** New best model saved (Val F1={:.4f}) **".format(val_f1))

    log("=" * 65)
    log("Training complete. Best Val F1: {:.4f} at Epoch {}".format(
        best_val_f1, best_epoch))
    log("=" * 65)

    # ----- Final Test Evaluation --------------------------------------------
    log("Loading best model for test evaluation...")
    best_model = AutoModelForSequenceClassification.from_pretrained(
        best_model_path)
    best_model = best_model.to(device)

    test_loss, test_acc, test_f1, y_pred, y_true = evaluate(
        best_model, test_loader, device, criterion)

    log("")
    log("=" * 65)
    log("TEST SET RESULTS")
    log("=" * 65)
    log("  Test Loss     : {:.4f}".format(test_loss))
    log("  Test Accuracy : {:.2f}%".format(test_acc * 100))
    log("  Test Macro F1 : {:.4f}".format(test_f1))
    log("")

    report = classification_report(
        y_true, y_pred, target_names=le.classes_, zero_division=0)
    log("Per-Class Classification Report:")
    for line in report.split("\n"):
        log("  " + line)

    # Save report
    report_path = OUTPUT_DIR / "test_classification_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("KnowLaw AI -- AraBERT Legal Classifier\n")
        f.write("Test Set Classification Report\n")
        f.write("=" * 60 + "\n")
        f.write("Test Accuracy : {:.2f}%\n".format(test_acc * 100))
        f.write("Test Macro F1 : {:.4f}\n\n".format(test_f1))
        f.write(report)
    log("Report saved -> {}".format(report_path))

    # Save metrics JSON
    metrics_path = OUTPUT_DIR / "final_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "model":          MODEL_NAME,
            "best_epoch":     best_epoch,
            "best_val_f1":    round(best_val_f1, 4),
            "test_accuracy":  round(test_acc, 4),
            "test_macro_f1":  round(test_f1, 4),
            "n_classes":      n_classes,
            "train_samples":  len(X_train),
            "val_samples":    len(X_val),
            "test_samples":   len(X_test),
            "history":        history,
        }, f, indent=2)
    log("Metrics JSON saved -> {}".format(metrics_path))

    # ----- Plots ------------------------------------------------------------
    plot_learning_curves(history, OUTPUT_DIR)
    plot_confusion_matrix(y_true, y_pred, list(le.classes_), OUTPUT_DIR)

    log("")
    log("=" * 65)
    log("ALL DONE! Find your outputs at:")
    log("  {}".format(OUTPUT_DIR))
    log("  - best_model/          <- saved model checkpoint")
    log("  - learning_curves.png  <- loss, accuracy, F1 curves")
    log("  - confusion_matrix.png <- normalised confusion matrix")
    log("  - test_classification_report.txt")
    log("  - final_metrics.json")
    log("  - label_mapping.json")
    log("  - training_log.txt")
    log("=" * 65)


if __name__ == "__main__":
    main()
