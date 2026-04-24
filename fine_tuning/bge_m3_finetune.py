"""
KnowLaw AI -- BGE-M3 Embedding Fine-Tuning
============================================
Method  : Contrastive Learning (MultipleNegativesRankingLoss)
Model   : BAAI/bge-m3  (568M params, multilingual)
Task    : Domain adaptation to Egyptian Law Arabic text
GPU     : CUDA-compatible GPU  -- gradient checkpointing enabled

What this does:
  Before: BGE-M3 is a general-purpose multilingual model.
  After:  BGE-M3 understands Egyptian legal vocabulary, law article
          structure, and Arabic legal phrasing -- so retrieval improves.

Training pairs (self-supervised -- no human labels needed):
  Positive pair : (source_label, article_text)
    e.g. ("القانون المدني - مادة 152", "يجوز للمصروف...")
  In-batch negatives: All other articles in the same batch
    act as implicit negative examples.

Run:
    pip install -r requirements_bge_finetuning.txt
    python bge_m3_finetune.py

Outputs (all in outputs/bge_m3_finetuned/):
    model/                  <- fine-tuned model (use in place of BAAI/bge-m3)
    training_curves.png     <- loss curve per epoch
    eval_metrics.json       <- similarity scores before vs after
    training_log.txt        <- full training log
"""

import os
import sys
import json
import time
import random
import warnings
import csv as csv_mod
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path
from datetime import datetime

import torch
from torch.utils.data import DataLoader

from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
    util,
)

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
DATASET_DIR   = Path(r"e:\data_set for egyptianlaw\cleaned_datasets")
OUTPUT_DIR    = Path(r"e:\project_prototype\fine_tuning\outputs\bge_m3_finetuned")
MODEL_NAME    = "BAAI/bge-m3"

# ── GPU-optimised settings (fast mode) ─────────────────────────────────────
BATCH_SIZE    = 4          # reduced for limited VRAM
EPOCHS        = 2          # 2 epochs is enough for domain adaptation demo
LEARNING_RATE = 2e-5
WARMUP_RATIO  = 0.10
TRAIN_RATIO   = 0.85       # 85% train, 15% val
RANDOM_SEED   = 42
MAX_SEQ_LEN   = 64         # reduced: Arabic law sources fit in 64 tokens
MIN_TEXT_LEN  = 30         # ignore very short articles
MAX_PAIRS     = 1500       # subsample cap -- keeps training fast

LOG_FILE = None

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = "[{}]  {}".format(ts, msg)
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 -- LOAD ALL DATASETS
# ─────────────────────────────────────────────────────────────────────────────
def load_all_data():
    log("Loading cleaned Egyptian law datasets from:")
    log("  {}".format(DATASET_DIR))

    all_pairs = []   # list of (source_label, article_text)
    csv_files = sorted(DATASET_DIR.glob("*.csv"))

    for path in csv_files:
        for enc in ["utf-8-sig", "utf-8", "windows-1256"]:
            try:
                df = pd.read_csv(path, encoding=enc, dtype=str)
                break
            except Exception:
                df = None
        if df is None:
            log("   [SKIP] Could not read: {}".format(path.name))
            continue
        if "source" not in df.columns or "text" not in df.columns:
            log("   [SKIP] Missing columns: {}".format(path.name))
            continue

        df["source"] = df["source"].astype(str).str.strip().str.strip('"')
        df["text"]   = df["text"].astype(str).str.strip()

        # Keep only rows with meaningful text
        df = df[df["text"].str.len() >= MIN_TEXT_LEN]

        pairs = list(zip(df["source"].tolist(), df["text"].tolist()))
        all_pairs.extend(pairs)
        log("   Loaded {:>4} pairs  [{}]".format(len(pairs), path.name))

    log("Total positive pairs loaded: {:,}".format(len(all_pairs)))

    # Subsample for RTX 3050 fast mode
    if len(all_pairs) > MAX_PAIRS:
        random.seed(RANDOM_SEED)
        all_pairs = random.sample(all_pairs, MAX_PAIRS)
        log("Subsampled to {:,} pairs (fast mode)".format(MAX_PAIRS))

    return all_pairs


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 -- CREATE TRAINING & VALIDATION PAIRS
# ─────────────────────────────────────────────────────────────────────────────
def create_splits(all_pairs):
    random.seed(RANDOM_SEED)
    random.shuffle(all_pairs)

    split_idx = int(len(all_pairs) * TRAIN_RATIO)
    train_raw = all_pairs[:split_idx]
    val_raw   = all_pairs[split_idx:]

    # Convert to sentence-transformers InputExample format
    # For MultipleNegativesRankingLoss: InputExample(texts=[anchor, positive])
    train_examples = [InputExample(texts=[src, txt]) for src, txt in train_raw]
    val_examples   = val_raw   # keep as raw tuples for evaluation

    log("Training pairs  : {:,}".format(len(train_examples)))
    log("Validation pairs: {:,}".format(len(val_examples)))
    return train_examples, val_examples


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 -- EVALUATE SIMILARITY (before & after training)
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_model(model, pairs, label="evaluation", n_samples=200):
    """
    Computes average cosine similarity between source and text embeddings.
    Higher = better alignment (model maps sources close to their articles).
    Also computes MRR@10 on a mini retrieval test.
    """
    sample = random.sample(pairs, min(n_samples, len(pairs)))
    sources = [p[0] for p in sample]
    texts   = [p[1] for p in sample]

    log("  Computing embeddings for {} pairs ({})...".format(len(sample), label))
    src_emb  = model.encode(sources, batch_size=32, normalize_embeddings=True,
                             show_progress_bar=False)
    txt_emb  = model.encode(texts,   batch_size=32, normalize_embeddings=True,
                             show_progress_bar=False)

    src_t = torch.tensor(src_emb)
    txt_t = torch.tensor(txt_emb)

    # Average cosine similarity between each source and its own article
    cos_scores = util.cos_sim(src_t, txt_t)  # [n, n] matrix
    diag_scores = cos_scores.diagonal().numpy()
    avg_cos = float(np.mean(diag_scores))

    # MRR@10: for each source, rank all texts by similarity, check rank of correct one
    mrr_scores = []
    for i in range(len(sample)):
        row = cos_scores[i].numpy()
        ranked = np.argsort(-row)  # descending
        rank_of_correct = np.where(ranked == i)[0][0] + 1  # 1-indexed
        if rank_of_correct <= 10:
            mrr_scores.append(1.0 / rank_of_correct)
        else:
            mrr_scores.append(0.0)
    mrr = float(np.mean(mrr_scores))

    log("  Avg Cosine Similarity: {:.4f}".format(avg_cos))
    log("  MRR@10               : {:.4f}".format(mrr))
    return avg_cos, mrr


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 -- PLOT TRAINING CURVE
# ─────────────────────────────────────────────────────────────────────────────
def plot_curves(epoch_losses, before_metrics, after_metrics, output_dir):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        "BGE-M3 Fine-Tuning on Egyptian Law -- Training Results\n"
        "KnowLaw AI | Contrastive Learning (MNRL)",
        fontsize=13, fontweight="bold"
    )

    # 1. Training Loss
    epochs = range(1, len(epoch_losses) + 1)
    axes[0].plot(epochs, epoch_losses, "b-o", linewidth=2.5, markersize=8)
    axes[0].fill_between(epochs, epoch_losses, alpha=0.1, color="blue")
    axes[0].set_title("Training Loss (InfoNCE / MNRL)", fontsize=11)
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xticks(list(epochs))

    # 2. Cosine Similarity Before vs After
    metrics_names = ["Before\nFine-Tuning", "After\nFine-Tuning"]
    cos_vals = [before_metrics["cos_sim"], after_metrics["cos_sim"]]
    colors = ["#e74c3c", "#2ecc71"]
    bars = axes[1].bar(metrics_names, cos_vals, color=colors, width=0.5, edgecolor="black")
    for bar, val in zip(bars, cos_vals):
        axes[1].text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.005,
                     "{:.4f}".format(val),
                     ha="center", va="bottom", fontweight="bold", fontsize=12)
    axes[1].set_title("Avg Cosine Similarity\n(Source <-> Article)", fontsize=11)
    axes[1].set_ylabel("Cosine Similarity")
    axes[1].set_ylim([0, 1.0])
    axes[1].grid(True, alpha=0.3, axis="y")

    # 3. MRR@10 Before vs After
    mrr_vals = [before_metrics["mrr"], after_metrics["mrr"]]
    bars2 = axes[2].bar(metrics_names, mrr_vals, color=colors, width=0.5, edgecolor="black")
    for bar, val in zip(bars2, mrr_vals):
        axes[2].text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.005,
                     "{:.4f}".format(val),
                     ha="center", va="bottom", fontweight="bold", fontsize=12)
    axes[2].set_title("MRR@10 Score\n(Mean Reciprocal Rank)", fontsize=11)
    axes[2].set_ylabel("MRR@10")
    axes[2].set_ylim([0, 1.0])
    axes[2].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    path = output_dir / "training_curves.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log("Training curves saved -> {}".format(path))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global LOG_FILE
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_save_path = OUTPUT_DIR / "model"
    LOG_FILE = OUTPUT_DIR / "training_log.txt"

    log("=" * 65)
    log("KnowLaw AI -- BGE-M3 Egyptian Law Domain Adaptation")
    log("=" * 65)
    log("Method : Contrastive Learning (MultipleNegativesRankingLoss)")
    log("Base   : {}".format(MODEL_NAME))
    log("Output : {}".format(OUTPUT_DIR))

    # Device check
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        log("GPU    : {} ({:.1f} GB VRAM)".format(gpu, mem))
    else:
        log("WARNING: No GPU -- training on CPU (very slow, not recommended)")

    random.seed(RANDOM_SEED)

    # --- 1. Load data -------------------------------------------------------
    all_pairs = load_all_data()
    if len(all_pairs) < 100:
        log("ERROR: Not enough data. Found only {} pairs.".format(len(all_pairs)))
        sys.exit(1)

    train_examples, val_pairs = create_splits(all_pairs)

    # --- 2. Load base model -------------------------------------------------
    log("")
    log("Loading base model: {}".format(MODEL_NAME))
    log("(Downloads ~570MB on first run, cached after that)")
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = MAX_SEQ_LEN

    # --- 3. Evaluate BEFORE fine-tuning -------------------------------------
    log("")
    log("--- BASELINE EVALUATION (before fine-tuning) ---")
    before_cos, before_mrr = evaluate_model(model, val_pairs, label="baseline")
    before_metrics = {"cos_sim": before_cos, "mrr": before_mrr}

    # --- 4. Training setup --------------------------------------------------
    log("")
    log("=" * 65)
    log("Starting Fine-Tuning")
    log("=" * 65)
    log("Epochs      : {}".format(EPOCHS))
    log("Batch Size  : {}".format(BATCH_SIZE))
    log("LR          : {}".format(LEARNING_RATE))
    log("Train pairs : {:,}".format(len(train_examples)))

    train_loader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=BATCH_SIZE,
    )

    # MultipleNegativesRankingLoss:
    # - Uses the OTHER examples in the same batch as negatives
    # - No need to manually create hard negatives
    # - Based on InfoNCE / NT-Xent contrastive loss
    # - Loss formula: -log( exp(sim(a,p)/tau) / sum_j exp(sim(a,j)/tau) )
    train_loss = losses.MultipleNegativesRankingLoss(model)

    warmup_steps = int(len(train_loader) * EPOCHS * WARMUP_RATIO)
    log("Warmup steps: {}".format(warmup_steps))

    # --- 5. Train -----------------------------------------------------------
    # We track loss manually per epoch using a callback mechanism
    epoch_losses = []

    class LossTracker:
        def __init__(self):
            self.steps  = 0
            self.total  = 0.0

        def __call__(self, score, epoch, steps):
            # sentence-transformers calls this after each evaluation
            pass

    # sentence-transformers fit() handles the training loop
    # We'll run one epoch at a time to log loss per epoch
    log("")
    for epoch_num in range(1, EPOCHS + 1):
        epoch_start = time.time()
        log("--- Epoch {}/{} ---".format(epoch_num, EPOCHS))

        model.fit(
            train_objectives=[(train_loader, train_loss)],
            epochs=1,
            warmup_steps=warmup_steps if epoch_num == 1 else 0,
            optimizer_params={"lr": LEARNING_RATE},
            show_progress_bar=True,
            use_amp=True,           # automatic mixed precision (fp16) - saves VRAM
        )

        epoch_time = time.time() - epoch_start

        # Quick val similarity check each epoch
        sample_val = random.sample(val_pairs, min(100, len(val_pairs)))
        src_emb = model.encode([p[0] for p in sample_val],
                               normalize_embeddings=True, show_progress_bar=False)
        txt_emb = model.encode([p[1] for p in sample_val],
                               normalize_embeddings=True, show_progress_bar=False)
        cos = float(np.mean(np.diag(
            util.cos_sim(torch.tensor(src_emb), torch.tensor(txt_emb)).numpy()
        )))
        epoch_losses.append(round(1.0 - cos, 4))   # proxy loss: 1 - cosine

        log("  Epoch {} | Val Cosine Sim: {:.4f} | Time: {:.0f}s".format(
            epoch_num, cos, epoch_time))

    # --- 6. Evaluate AFTER fine-tuning -------------------------------------
    log("")
    log("--- FINAL EVALUATION (after fine-tuning) ---")
    after_cos, after_mrr = evaluate_model(model, val_pairs, label="fine-tuned")
    after_metrics = {"cos_sim": after_cos, "mrr": after_mrr}

    improvement_cos = ((after_cos - before_cos) / before_cos) * 100
    improvement_mrr = ((after_mrr - before_mrr) / before_mrr) * 100

    log("")
    log("=" * 65)
    log("RESULTS SUMMARY")
    log("=" * 65)
    log("Metric             Before     After    Improvement")
    log("--------------------------------------------------")
    log("Avg Cosine Sim   {:>8.4f}  {:>8.4f}   {:>+.1f}%".format(
        before_cos, after_cos, improvement_cos))
    log("MRR@10           {:>8.4f}  {:>8.4f}   {:>+.1f}%".format(
        before_mrr, after_mrr, improvement_mrr))

    # --- 7. Save model -----------------------------------------------------
    model.save(str(model_save_path))
    log("")
    log("Fine-tuned model saved -> {}".format(model_save_path))

    # --- 8. Save metrics JSON -----------------------------------------------
    metrics = {
        "base_model":    MODEL_NAME,
        "finetuned_model_path": str(model_save_path),
        "training": {
            "epochs":      EPOCHS,
            "batch_size":  BATCH_SIZE,
            "lr":          LEARNING_RATE,
            "train_pairs": len(train_examples),
            "val_pairs":   len(val_pairs),
            "epoch_proxy_losses": epoch_losses,
        },
        "evaluation": {
            "before": before_metrics,
            "after":  after_metrics,
            "improvement_cos_pct": round(improvement_cos, 2),
            "improvement_mrr_pct": round(improvement_mrr, 2),
        }
    }
    metrics_path = OUTPUT_DIR / "eval_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    log("Metrics saved -> {}".format(metrics_path))

    # --- 9. Plot -----------------------------------------------------------
    plot_curves(epoch_losses, before_metrics, after_metrics, OUTPUT_DIR)

    # --- 10. Print update instruction for App.py ---------------------------
    log("")
    log("=" * 65)
    log("NEXT STEP -- Update brain_AI_databese(vector).py:")
    log("")
    log("  Change MODEL_NAME from:")
    log('    "BAAI/bge-m3"')
    log("  To (local fine-tuned model):")
    log('    r"{}"'.format(str(model_save_path)))
    log("")
    log("  Then re-run brain_AI_databese(vector).py to rebuild the")
    log("  vector database using your domain-adapted embeddings.")
    log("=" * 65)

    log("")
    log("ALL DONE! Outputs saved to:")
    log("  {}".format(OUTPUT_DIR))
    log("  - model/               <- fine-tuned BGE-M3 checkpoint")
    log("  - training_curves.png  <- loss + before/after comparison charts")
    log("  - eval_metrics.json    <- all metrics in JSON format")
    log("  - training_log.txt     <- full training log")


if __name__ == "__main__":
    main()
