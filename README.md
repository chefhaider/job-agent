<div align="center">

# 🤖 Job Agent

### An end-to-end pipeline that scrapes LinkedIn jobs, ranks them with AI, and auto-generates a tailored résumé + cover letter for each — then emails you a daily report.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-scraping-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Groq](https://img.shields.io/badge/Groq-LLM-F55036)](https://groq.com/)
[![GitHub Models](https://img.shields.io/badge/GitHub-Models-181717?logo=github&logoColor=white)](https://github.com/marketplace/models)
[![LaTeX](https://img.shields.io/badge/LaTeX-PDF-008080?logo=latex&logoColor=white)](https://www.latex-project.org/)

</div>

---

## ✨ What it does

Every run, `job-agent` walks through six automated stages:

```
🔎 Scrape  →  📊 Rank  →  📝 Describe  →  🎓 Résumé  →  ✉️ Cover Letter  →  📬 Email
```

1. **Scrape** LinkedIn search results from your list of saved search URLs.
2. **Rank** the scraped jobs by relevance to your profile using an LLM.
3. **Describe** — visit each top job and extract the full "About the job" text.
4. **Build résumés** — generate a tailored LaTeX résumé per job and compile it to PDF.
5. **Build cover letters** — generate a tailored LaTeX cover letter per job and compile to PDF.
6. **Email** a single HTML report summarizing every job, listing the generated résumé/PDF path for each.

---

## 🧠 Models & APIs per stage

| # | Stage | Script | Provider | Model(s) (fallback order) | Credential |
|:-:|-------|--------|----------|---------------------------|------------|
| 1 | Scrape jobs | `linkedin.py` | Playwright (browser) | — | — |
| 2 | Rank jobs | `rank_jobs.py` | Google Gemini → Groq | `gemini-2.5-flash`, `gemini-3.1-flash-lite` → `llama-3.3-70b-versatile` | `GOOGLE_API_KEY`, `GROQ_API_KEY` |
| 3 | Job descriptions | `job_description.py` | Playwright (browser) | — | — |
| 4 | Build résumés | `resume_builder.py` | GitHub Models (OpenAI SDK) | `gpt-4o`, `phi-4-reasoning`, `gpt-4o-mini`, `phi-4-mini-instruct` | `GITHUB_TOKEN` |
| 4.2 | Build cover letters | `cover_letter.py` | Google Gemini → Groq | `gemini-2.5-flash`, `gemini-3.1-flash-lite` → `llama-3.3-70b-versatile`, `openai/gpt-oss-120b` | `GOOGLE_API_KEY2`, `GROQ_API_KEY` |
| 5 | Email report | `email_report.py` | SMTP (Gmail) | — | `GMAIL_APP` |

> Every LLM stage **cascades through fallbacks** — if the primary model is rate-limited or fails, it automatically tries the next one.

---

## 📁 Project structure

```
job-agent/
├── job_agent.sh          # 🚀 Main entry point — runs the full 6-stage pipeline
├── target_urls.csv       # 📥 Your LinkedIn search URLs (input)
├── .env                  # 🔑 Secrets & config (gitignored — create from .env.example)
├── .env.example          # 📋 Template for .env
│
├── src/                  # 🧩 Active pipeline code
│   ├── linkedin.py           # Stage 1 — scrape job listings
│   ├── scraper.py            #   └─ LinkedIn scraping engine
│   ├── parser.py             #   └─ HTML → JobListing parser
│   ├── stealth_config.py     #   └─ anti-bot browser hardening
│   ├── utils.py              #   └─ CSV I/O + target-URL loading
│   ├── rank_jobs.py          # Stage 2 — AI relevance ranking
│   ├── job_description.py    # Stage 3 — scrape full descriptions
│   ├── resume_builder.py     # Stage 4 — tailored résumé → PDF
│   ├── cover_letter.py       # Stage 4.2 — tailored cover letter → PDF
│   └── email_report.py       # Stage 5 — HTML email report
│
├── templates/            # 🎨 LaTeX templates, prompts & assets
│   ├── main.tex              # résumé LaTeX scaffold
│   ├── cover_letter.tex      # cover-letter LaTeX scaffold
│   ├── resume_prompt.txt     # LLM prompt for résumés
│   ├── cover_letter_prompt.txt
│   └── bg12.jpg              # background image used by the templates
│
├── output/               # 📦 Generated CSVs, JSON, and PDFs
└── temp/                 # 🗄️ Parked / unused files (alt implementations, scratch)
```

---

## 🚀 Quick start

### 1. Prerequisites

- **Python 3.10+** (a conda env is recommended)
- **A LaTeX toolchain** with `latexmk` (e.g. TeX Live / MiKTeX) on your `PATH`
- **Google Chrome / Chromium** (Playwright drives a real browser)

### 2. Install dependencies

```bash
pip install playwright google-generativeai groq openai pandas beautifulsoup4
python -m playwright install chromium
```

### 3. Configure secrets

```bash
cp .env.example .env
```

Then fill in `.env`:

```ini
# ── LLM API keys ──
GOOGLE_API_KEY=your_gemini_key            # rank_jobs.py
GOOGLE_API_KEY2=your_second_gemini_key    # cover_letter.py
GROQ_API_KEY=your_groq_key                # Groq fallback
GITHUB_TOKEN=your_github_models_token     # resume_builder.py
GEMINI_SESSION_FILE=/tmp/gemini_chat_session.json

# ── Email report ──
SENDER_EMAIL=you@gmail.com
RECEIVER_EMAIL=you@gmail.com
GMAIL_APP=your_16_char_gmail_app_password # https://myaccount.google.com/apppasswords
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 4. Add your job searches

Edit `target_urls.csv` — one row per LinkedIn job-search URL:

```csv
search_query,url
Machine Learning Germany,https://www.linkedin.com/jobs/search/?keywords=Machine%20Learning%20Engineer&...
Work Student ML,https://www.linkedin.com/jobs/search/?keywords=work%20student%20data&...
```

### 5. Run the pipeline

Open `job_agent.sh` and set `PROJECT_DIR` and `CONDA_PYTHON` to match your machine, then:

```bash
./job_agent.sh
```

The script loads `.env`, runs all six stages, and logs progress to `pipeline.log`.

---

## 🧪 Running stages individually

Each stage is a standalone script (run from the project root so relative paths resolve):

```bash
python src/linkedin.py --headless --output jobs.csv      # 1 · scrape
python src/rank_jobs.py                                   # 2 · rank
python src/job_description.py --headless --limit 20       # 3 · descriptions
python src/resume_builder.py                              # 4 · résumés
python src/cover_letter.py                                # 4.2 · cover letters
python src/email_report.py                                # 5 · email
```

<details>
<summary><b>Useful flags</b></summary>

| Script | Flag | Description | Default |
|--------|------|-------------|---------|
| `linkedin.py` | `--urls` | CSV of search URLs | `target_urls.csv` |
| | `--pages` | pages scraped per search | `2` |
| | `--headless` | run without a visible browser | off |
| | `-o, --output` | output CSV name | auto-timestamped |
| | `--delay` | seconds between searches | `5` |
| `job_description.py` | `-i, --input` | input CSV | `output/jobs_sorted.csv` |
| | `-o, --output` | output JSON | `output/job_descriptions.json` |
| | `--limit` | max jobs to process | all |
| | `--headless` | run without a visible browser | off |
| | `--delay` | seconds between requests | `6` |

</details>

---

## 🔄 Data flow

```
target_urls.csv
      │  linkedin.py
      ▼
output/jobs.csv
      │  rank_jobs.py
      ▼
output/jobs_sorted.csv
      │  job_description.py
      ▼
output/job_descriptions.json ──┐
      │  resume_builder.py      │  cover_letter.py
      ▼                         ▼
output/*.pdf (résumés)     output/*_cover.pdf
      └──────────┬──────────────┘
                 │  email_report.py
                 ▼
        📬 HTML summary email
```

`job_descriptions.json` is the spine of the pipeline — each stage enriches it in place (adding `resume_file_path`, cover-letter paths, etc.) before the email step reads it.

---

## 🔐 Security notes

- **`.env` is gitignored** — never commit real keys. Share only `.env.example`.
- `GMAIL_APP` must be a **Gmail App Password** (requires 2FA), not your account password.
- Scraping is throttled with randomized delays and stealth browser settings, but use it responsibly and within LinkedIn's terms.

---

## 🗄️ The `temp/` folder

Parked, non-pipeline files kept for reference — e.g. `resume_builder.py` (the previous Gemini/Groq résumé builder, before the switch to GitHub Models), alternative rankers, and scratch notebooks. Nothing here is imported or executed by `job_agent.sh`.

---

<div align="center">
<sub>Built for automating the job hunt — scrape less, apply smarter.</sub>
</div>
