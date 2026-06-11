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





# ── Pipeline Steps ────────────────────────────────────────────────────────────
#log "📥 Step 1: Scraping LinkedIn jobs..."
#"$CONDA_PYTHON" linkedin.py --headless --output jobs.csv >> "$LOG_FILE" 2>&1
#
#log "📊 Step 2: Ranking jobs..."
#"$CONDA_PYTHON" rank_jobs.py >> "$LOG_FILE" 2>&1
#
#log "📝 Step 3: Extracting job descriptions..."
#"$CONDA_PYTHON" job_description.py --headless --limit 20 >> "$LOG_FILE" 2>&1
#

#log "🎓 Step 4: Building resumes..."
#"$CONDA_PYTHON" resume_builder_gpt.py >> "$LOG_FILE" 2>&1
#
#log "🎓 Step 4.2: Building resumes..."
#"$CONDA_PYTHON" cover_letter.py >> "$LOG_FILE" 2>&1
#
log "📧 Step 5: Sending email report..."
"$CONDA_PYTHON" email_report.py >> "$LOG_FILE" 2>&1

log "✅ Pipeline completed successfully"

