import os
import json
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Optional
import google.generativeai as genai
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
SESSION_FILE = os.environ.get("GEMINI_SESSION_FILE", "/tmp/gemini_chat_session.json")

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash-lite"]
GROQ_MODEL = "llama-3.3-70b-versatile"

CSV_FILE = "linkedin/output/jobs.csv"  # columns: company, job_title, link

MY_PROFILE = """
I am a mahcine learning engineer with roughly three years of expereince, in my last semester of my msc AI program. 
I have experince in vast array of tools and sub domains in the following order pf expertise: CV, mlops, audio processing, NLP,ai in health care, data engineering, data analytics, full stack development for ai and llm.
Heres my preference germany>outside of germany. equal preference to fulltime and working student positions.
With only three years of experince entry level roles suits me better.
""".strip()

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_job_description(url: str, timeout: int = 10) -> str:
    """Scrape plain text from a job posting URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # Collapse whitespace and truncate to ~3000 chars to save tokens
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)[:3000]
    except Exception as e:
        return f"[Could not fetch description: {e}]"


def build_prompt(company: str, title: str, description: str) -> str:
    return f"""
You are a career advisor. Given the candidate profile and a job posting, score how
relevant this job is for the candidate on a scale of 0–100, where:
  100 = perfect match
    0 = completely irrelevant

Return ONLY a JSON object with two keys:
  "score"  : integer 0-100
  "reason" : one-sentence explanation (max 20 words)

Example output:
{{"score": 85, "reason": "Strong Python/AWS match; lacks required ML experience."}}

---
CANDIDATE PROFILE:
{MY_PROFILE}

---
JOB POSTING:
Company  : {company}
Job Title: {title}

Description:
{description}
""".strip()


def parse_score_response(text: str) -> dict:
    """Extract JSON from model response, tolerating markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        text = "\n".join(text.splitlines()[1:])
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to find the first {...} block
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end:
            return json.loads(text[start:end])
        raise ValueError(f"Cannot parse JSON from: {text!r}")


# ── LLM Callers ───────────────────────────────────────────────────────────────

def call_gemini(prompt: str, model_name: str) -> str:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.text


def call_groq(prompt: str) -> str:
    client = Groq(api_key=GROQ_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content


def score_job(prompt: str) -> dict:
    """
    Try each Gemini model first, then fall back to Groq.
    Returns {"score": int, "reason": str, "model_used": str}
    """
    # 1️⃣ Try Gemini models in order
    for model_name in GEMINI_MODELS:
        try:
            print(f"    → Trying Gemini [{model_name}] …", end=" ", flush=True)
            raw = call_gemini(prompt, model_name)
            result = parse_score_response(raw)
            result["model_used"] = f"gemini/{model_name}"
            print(f"✓  score={result['score']}")
            return result
        except Exception as e:
            print(f"✗  ({e})")
            time.sleep(1)  # brief pause before retry

    # 2️⃣ Fall back to Groq
    try:
        print(f"    → Trying Groq [{GROQ_MODEL}] …", end=" ", flush=True)
        raw = call_groq(prompt)
        result = parse_score_response(raw)
        result["model_used"] = f"groq/{GROQ_MODEL}"
        print(f"✓  score={result['score']}")
        return result
    except Exception as e:
        print(f"✗  ({e})")
        return {"score": -1, "reason": "All models failed.", "model_used": "none"}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load CSV  (expected columns: company, job_title, link)
    df = pd.read_csv(CSV_FILE)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")


    scores, reasons, models_used = [], [], []

    for idx, row in df.iterrows():
        company   = str(row["company_name"]).strip()
        title     = str(row["job_title"]).strip()
        link      = str(row["job_url"]).strip()

        print(f"\n[{idx + 1}/{len(df)}] {company} — {title}")
        print(f"    Fetching job description …")
        description = fetch_job_description(link)

        prompt = build_prompt(company, title, description)
        result = score_job(prompt)

        scores.append(result["score"])
        reasons.append(result["reason"])
        models_used.append(result["model_used"])

        time.sleep(0.5)  # rate-limit courtesy pause

    # Attach results and sort
    df["score"]      = scores
    df["reason"]     = reasons
    df["model_used"] = models_used

    df_sorted = (
        df[df["score"] >= 0]          # drop failed rows to the bottom
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )

    # Keep failed rows at the bottom
    df_failed = df[df["score"] < 0].reset_index(drop=True)
    df_final  = pd.concat([df_sorted, df_failed], ignore_index=True)

    # Save output
    output_file = "jobs_ranked.csv"
    df_final.to_csv(output_file, index=False)
    print(f"\n{'═' * 60}")
    print(f"✅  Saved ranked results → {output_file}")
    print(f"{'═' * 60}\n")

    # Pretty-print top results
    print(df_final[["score", "company", "job_title", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()