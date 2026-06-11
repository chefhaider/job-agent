import os
import time
import re
import subprocess
import json
import random
from pathlib import Path
import google.generativeai as genai
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_KEY = os.environ.get("GOOGLE_API_KEY2")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-3.1-flash-lite"]
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
]

COVER_PROMPT_FILE = "templates/cover_letter_prompt.txt"
JOBS_JSON = "output/job_descriptions.json"
COVER_TEX_FILE = "templates/cover_letter.tex"
OUTPUT_DIR = "output"
WAIT_SECONDS = 60 * 8


# ── LaTeX Compiler ───────────────────────────────────────────────────────────

def compile_latex_to_pdf(tex_file_path: str, output_pdf_path: str, keep_aux: bool = False):
    tex_path = Path(tex_file_path).resolve()
    out_path = Path(output_pdf_path).resolve()
    out_dir = out_path.parent

    if not tex_path.exists():
        print(f"❌ Error: LaTeX file not found: {tex_path}")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(tex_path.parent)

    try:
        result = subprocess.run(
            [
                "latexmk", "-pdf", "-interaction=nonstopmode",
                "-halt-on-error", f"-outdir={out_dir}", tex_path.name
            ],
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            print("❌ LaTeX compilation failed.")
            return None

        generated_pdf = out_dir / f"{tex_path.stem}.pdf"
        if not generated_pdf.exists():
            print("❌ PDF not found after compilation.")
            return None

        generated_pdf.rename(out_path)
        return str(out_path)

    except Exception as e:
        print(f"❌ Unexpected compilation error: {e}")
        return None
    finally:
        os.chdir(original_cwd)
        if not keep_aux:
            try:
                subprocess.run(
                    ["latexmk", "-c", f"-outdir={out_dir}"],
                    cwd=tex_path.parent, capture_output=True, text=True,
                )
            except Exception:
                pass


# ── LLM ──────────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str | None:
    for model_name in GEMINI_MODELS:
        try:
            print(f"  Trying Gemini {model_name}...", end=" ", flush=True)
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            print("✓")
            return resp.text
        except Exception as e:
            print(f"✗ ({e})")
            time.sleep(1)

    client = Groq(api_key=GROQ_KEY)
    for model_name in GROQ_MODELS:
        try:
            print(f"  Trying Groq {model_name}...", end=" ", flush=True)
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=8000,
            )
            print("✓")
            return resp.choices[0].message.content
        except Exception as e:
            print(f"✗ ({e})")
            time.sleep(1)

    print("❌ All models failed for this job.")
    return None


# ── Extract clean LaTeX ──────────────────────────────────────────────────────

def extract_latex(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:latex|tex)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    if "\\documentclass" in text:
        start = text.index("\\documentclass")
        end_marker = "\\end{document}"
        end = text.rfind(end_marker)
        if end != -1:
            return text[start: end + len(end_marker)]
        return text[start:]
    return text


# ── Main ─────────────────────────────────────────────────────────────────────

def build_cover_letters(
    prompt_file=COVER_PROMPT_FILE,
    jobs_json=JOBS_JSON,
    tex_file=COVER_TEX_FILE,
    output_dir=OUTPUT_DIR,
):
    if not os.path.exists(prompt_file):
        raise FileNotFoundError(f"❌ Prompt file not found: {prompt_file}")
    with open(prompt_file, "r", encoding="utf-8") as f:
        base_prompt = f.read().strip()

    if not os.path.exists(jobs_json):
        raise FileNotFoundError(f"❌ JSON file not found: {jobs_json}")
    with open(jobs_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    if not jobs:
        print("⚠️  No jobs found in JSON file.")
        return

    print(f"🚀 Generating cover letters for {len(jobs)} jobs...\n")
    os.makedirs(output_dir, exist_ok=True)

    for i, job in enumerate(jobs):
        title = str(job.get("job_title", "")).strip()
        company = str(job.get("company_name", "")).strip()
        description = str(job.get("job_description", ""))

        print(f"[{i + 1}/{len(jobs)}] {company} — {title}")

        job_info = (
            f"Company: {company}\n"
            f"Job Title: {title}\n"
            f"Job Description:\n{description}\n\n"
        )

        prompt = (
            base_prompt
            + job_info
            + "Now return the complete tailored LaTeX cover letter. "
            + "Start with \\documentclass. No markdown. No explanation."
        )

        # ── Generate consistent random ID for all files this job ──
        random_num = random.randint(100000, 999999)

        # ── Save prompt input ──
        input_txt_path = os.path.join(output_dir, f"muhammad_haider_{random_num}_cover_input.txt")
        with open(input_txt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"  📝 Prompt saved: {input_txt_path}")

        # ── LLM call ──
        raw = call_llm(prompt)
        if raw is None:
            print("  ⚠️  LLM failed. Skipping this job.")
            job["cover_letter_file_path"] = None
            if i < len(jobs) - 1:
                print(f"  ⏳ Waiting {WAIT_SECONDS}s before next job...")
                time.sleep(WAIT_SECONDS)
            continue

        latex = extract_latex(raw)
        if not latex.strip():
            print("  ⚠️  LLM returned empty/invalid LaTeX. Skipping this job.")
            job["cover_letter_file_path"] = None
            if i < len(jobs) - 1:
                print(f"  ⏳ Waiting {WAIT_SECONDS}s before next job...")
                time.sleep(WAIT_SECONDS)
            continue

        # ── Write .tex file ──
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(latex)

        # ── File paths ──
        pdf_name = f"muhammad_haider_{random_num}_cover.pdf"
        pdf_path = os.path.join(output_dir, pdf_name)

        # ── Compile ──
        compiled = compile_latex_to_pdf(tex_file, pdf_path, keep_aux=False)

        if compiled:
            job["cover_letter_file_path"] = f"/home/chefhaider/Repositories/job_automation/output/{pdf_name}"
            print(f"  ✅ {job['cover_letter_file_path']}")
        else:
            job["cover_letter_file_path"] = input_txt_path
            print(f"  ⚠️  LaTeX failed. Saved raw output to: {job['cover_letter_file_path']}")

        if i < len(jobs) - 1:
            print(f"  ⏳ Waiting {WAIT_SECONDS}s before next job...")
            time.sleep(WAIT_SECONDS)

    # ── Save updated JSON ──
    with open(jobs_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Updated {jobs_json} with cover_letter_file_path for all jobs.")


if __name__ == "__main__":
    build_cover_letters()