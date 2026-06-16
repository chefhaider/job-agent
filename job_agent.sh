#!/bin/bash
# Exit on first error, unset vars cause errors, pipe failures propagate
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_DIR="/home/chefhaider/Repositories/job-agent"
LOG_FILE="${PROJECT_DIR}/pipeline.log"
# 🔍 Find your exact path by running: conda activate jap && which python
CONDA_PYTHON="/home/chefhaider/miniconda3/envs/jap/bin/python"

# ── Helpers ───────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

# ── Setup ─────────────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"

# Load secrets/config from .env (exported to all python subprocesses)
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.env"
    set +a
else
    log "⚠️  No .env file found at ${PROJECT_DIR}/.env — relying on existing environment."
fi



# ── Randomized Execution Window (00:00 - 00:30) ──────────────────────────────
#CURRENT_HOUR=$(date +%H)
#if [[ "$CURRENT_HOUR" == "00" ]]; then
#    RANDOM_DELAY=$(( RANDOM % 1801 ))  # 0 to 1800 seconds
#    MIN_DELAY=$(( RANDOM_DELAY / 60 ))
#    SEC_DELAY=$(( RANDOM_DELAY % 60 ))
#    log "⏱️  Random delay: ${MIN_DELAY}m ${SEC_DELAY}s"
#    log "⏳ Sleeping until pipeline starts..."
#    sleep "$RANDOM_DELAY"
#else
#    log "ℹ️  Triggered outside midnight window (hour: $CURRENT_HOUR). Running immediately."
#fi

log "🚀 Pipeline started at $(date '+%H:%M:%S')"




# ── Pipeline Steps ────────────────────────────────────────────────────────────
log "📥 Step 1: Scraping LinkedIn jobs..."
"$CONDA_PYTHON" src/linkedin.py --headless --output jobs.csv >> "$LOG_FILE" 2>&1

log "📊 Step 2: Ranking jobs..."
"$CONDA_PYTHON" src/rank_jobs.py >> "$LOG_FILE" 2>&1

log "📝 Step 3: Extracting job descriptions..."
"$CONDA_PYTHON" src/job_description.py --headless --limit 20 >> "$LOG_FILE" 2>&1

log "🎓 Step 4: Building resumes..."
"$CONDA_PYTHON" src/resume_builder.py >> "$LOG_FILE" 2>&1

log "🎓 Step 4.2: Building cover letter..."
"$CONDA_PYTHON" src/cover_letter.py >> "$LOG_FILE" 2>&1

log "📧 Step 5: Sending email report..."
"$CONDA_PYTHON" src/email_report.py >> "$LOG_FILE" 2>&1

log "✅ Pipeline completed successfully"

