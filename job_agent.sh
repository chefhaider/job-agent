#!/bin/bash
# Exit on first error, unset vars cause errors, pipe failures propagate
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_DIR="/home/chefhaider/Repositories/job_automation"
LOG_FILE="${PROJECT_DIR}/pipeline.log"
# 🔍 Find your exact path by running: conda activate jap && which python
CONDA_PYTHON="/home/chefhaider/miniconda3/envs/jap/bin/python"

# ── Helpers ───────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

# ── Setup ─────────────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"



# ── Randomized Execution Window (00:00 - 00:30) ──────────────────────────────
CURRENT_HOUR=$(date +%H)
if [[ "$CURRENT_HOUR" == "00" ]]; then
    RANDOM_DELAY=$(( RANDOM % 1801 ))  # 0 to 1800 seconds
    MIN_DELAY=$(( RANDOM_DELAY / 60 ))
    SEC_DELAY=$(( RANDOM_DELAY % 60 ))
    log "⏱️  Random delay: ${MIN_DELAY}m ${SEC_DELAY}s"
    log "⏳ Sleeping until pipeline starts..."
    sleep "$RANDOM_DELAY"
else
    log "ℹ️  Triggered outside midnight window (hour: $CURRENT_HOUR). Running immediately."
fi

log "🚀 Pipeline started at $(date '+%H:%M:%S')"




# ── Pipeline Steps ────────────────────────────────────────────────────────────
log "📥 Step 1: Scraping LinkedIn jobs..."
"$CONDA_PYTHON" linkedin.py --headless --output jobs.csv >> "$LOG_FILE" 2>&1

log "📊 Step 2: Ranking jobs..."
"$CONDA_PYTHON" rank_jobs.py >> "$LOG_FILE" 2>&1

log "📝 Step 3: Extracting job descriptions..."
"$CONDA_PYTHON" job_description.py --headless --limit 20 >> "$LOG_FILE" 2>&1

log "🎓 Step 4: Building resumes..."
"$CONDA_PYTHON" resume_builder.py >> "$LOG_FILE" 2>&1

log "🎓 Step 4.2: Building resumes..."
"$CONDA_PYTHON" cover_letter.py >> "$LOG_FILE" 2>&1

log "📧 Step 5: Sending email report..."
"$CONDA_PYTHON" email_report.py >> "$LOG_FILE" 2>&1

log "✅ Pipeline completed successfully"

