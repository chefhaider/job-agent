import os
import json
import pandas as pd
import google.generativeai as genai
from groq import Groq

# ── API keys / models ─────────────────────────────────────────────────────────

GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
SESSION_FILE = os.environ.get("GEMINI_SESSION_FILE", "/tmp/gemini_chat_session.json")

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-3.1-flash-lite"]
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Files ─────────────────────────────────────────────────────────────────────

CSV_FILE = "output/jobs.csv"  # columns: company, job_title, link
OUTPUT_CSV = "output/jobs_sorted.csv"

# ── Your professional summary ────────────────────────────────────────────────

MY_PROFILE = """
I am a mahcine learning engineer with roughly three years of expereince, working on my thesis of my msc AI program. 
I have experince in vast array of tools and sub domains in the following order pf expertise:
CV, mlops, audio processing, NLP,ai in health care, data engineering, data analytics, full stack development for ai and llm.
the following roles suite me entry level fulltime, working student, and intern, skip jobs for thesis and alignerr
""".strip()


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(profile: str, df: pd.DataFrame) -> str:
    rows = []
    for i, row in df.iterrows():
        title = str(row["job_title"]).strip()
        company = str(row["company"]).strip() if "company" in df.columns else ""
        rows.append({
            "row_id": int(i),
            "company": company,
            "job_title": title
        })

    return f"""
You are a career assistant.

Given the candidate profile and a list of job titles, sort the jobs from most relevant
to least relevant for the candidate.

Important:
- Return ONLY valid JSON.
- Do NOT include explanations.
- Do NOT include scores.
- Return the rows in sorted order from most relevant to least relevant.

Return JSON in exactly this format:
{{
  "ordered_row_ids": [3, 0, 2, 1]
}}

Candidate profile:
{profile}

Jobs:
{json.dumps(rows, ensure_ascii=False)}
""".strip()


# ── Model callers ─────────────────────────────────────────────────────────────

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


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError(f"Could not parse JSON response: {text}")


def get_ordered_row_ids(prompt: str):
    # Try Gemini models first
    for model_name in GEMINI_MODELS:
        try:
            print(f"Trying Gemini: {model_name}")
            raw = call_gemini(prompt, model_name)
            data = parse_json_response(raw)
            return data["ordered_row_ids"], f"gemini/{model_name}"
        except Exception as e:
            print(f"Failed Gemini {model_name}: {e}")

    # Fallback to Groq
    try:
        print(f"Trying Groq: {GROQ_MODEL}")
        raw = call_groq(prompt)
        data = parse_json_response(raw)
        return data["ordered_row_ids"], f"groq/{GROQ_MODEL}"
    except Exception as e:
        raise RuntimeError(f"All models failed. Last error: {e}")


# ── Sorting ───────────────────────────────────────────────────────────────────

def sort_dataframe_by_llm_order(df: pd.DataFrame, ordered_ids: list) -> pd.DataFrame:
    ordered_ids = [int(x) for x in ordered_ids]

    # Keep only valid row ids
    valid_ids = [i for i in ordered_ids if i in df.index]

    # Append any missing rows at the end
    missing_ids = [i for i in df.index if i not in valid_ids]
    final_ids = valid_ids + missing_ids

    return df.loc[final_ids].reset_index(drop=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    df = pd.read_csv(CSV_FILE)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    if "job_title" not in df.columns:
        raise ValueError("CSV must contain a 'job_title' column")

    prompt = build_prompt(MY_PROFILE, df)
    print(prompt)
    ordered_ids, model_used = get_ordered_row_ids(prompt)

    sorted_df = sort_dataframe_by_llm_order(df, ordered_ids)
    sorted_df["sorted_by_model"] = model_used

    sorted_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved sorted jobs to: {OUTPUT_CSV}")
    print(f"Model used: {model_used}")


if __name__ == "__main__":
    main()