import os
import time
import re
import subprocess
import json
import random
from pathlib import Path
from openai import OpenAI, RateLimitError

# ── Config ────────────────────────────────────────────────────────────────────

# Fetch the security-compliant environment variable
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Models order from high-tier to low-tier fallback
GITHUB_MODELS = [
    "gpt-4o",                    # High Tier: 10 RPM / 50 RPD
    "phi-4-reasoning",           # High Tier: 10 RPM / 50 RPD
    "gpt-4o-mini",               # Low Tier: 15 RPM / 150 RPD
    "phi-4-mini-instruct"        # Low Tier: 15 RPM / 150 RPD
]

PROMPT_FILE = "templates/resume_prompt.txt"
JOBS_JSON = "output/job_descriptions.json"
TEX_FILE = "templates/main.tex"
OUTPUT_DIR = "output"

# Adaptive timing helper based on Student Tier pools
BASE_WAIT_HIGH_TIER = 60 * 1.5  # ~90 seconds safety buffer between High-Tier calls
BASE_WAIT_LOW_TIER = 10         # ~10 seconds safety buffer for low-tier variants


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


# ── LLM (GitHub Models Implementation) ────────────────────────────────────────

def call_llm(prompt: str) -> tuple[str | None, str | None]:
    """
    Queries GitHub Models API sequentially. 
    Handles Rate Limit (429) via dynamic exponential sleeping strategies.
    Returns a tuple of (response_text, model_used).
    """
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN environment variable is missing.")
        return None, None

    # Point to GitHub's Azure hosted OpenAI-compatible marketplace endpoint
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=GITHUB_TOKEN
    )

    for model_name in GITHUB_MODELS:
        retries = 3
        backoff = 65  # Default wait window if rate limited per minute
        
        while retries > 0:
            try:
                print(f"  Trying GitHub Model: {model_name}...", end=" ", flush=True)
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                print("✓")
                return resp.choices[0].message.content, model_name

            except RateLimitError as e:
                print(f"\n⚠️  Rate Limit (429) hit on {model_name}.")
                retries -= 1
                if retries > 0:
                    print(f"     Sleeping for {backoff} seconds before retrying this model...")
                    time.sleep(backoff)
                    backoff *= 1.5  # Scale up sleep window if it hits again
                else:
                    print("     Max retries reached for this model. Cascading to next fallback...")
            except Exception as e:
                print(f"✗ Unexpected Error: ({e})")
                break  # Break retry loop to jump to the next model immediately
                
    print("❌ All GitHub models failed or exhausted rate limit pools for this job.")
    return None, None


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

def build_resumes(
    prompt_file=PROMPT_FILE,
    jobs_json=JOBS_JSON,
    tex_file=TEX_FILE,
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

    print(f"🚀 Processing {len(jobs)} jobs via GitHub Models...\n")
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

        prompt = base_prompt + job_info + "Now return the complete tailored LaTeX resume. Start with \documentclass. No markdown. No explanation."
        
        random_num = random.randint(100000, 999999)
        input_txt_name = f"muhammad_haider_{random_num}_input.txt"
        input_txt_path = os.path.join(output_dir, input_txt_name)
        with open(input_txt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Call adjusted LLM handler
        raw, model_used = call_llm(prompt)
        
        if raw is None:
            print("  ⚠️  LLM completely failed. Skipping this job entry.")
            job["resume_file_path"] = None
            continue

        latex = extract_latex(raw)
        if not latex.strip():
            print("  ⚠️  LLM returned empty/invalid LaTeX. Skipping this job entry.")
            job["resume_file_path"] = None
            continue

        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(latex)
        
        pdf_name = f"muhammad_haider_{random_num}.pdf"
        pdf_path = os.path.join(output_dir, pdf_name)

        compiled = compile_latex_to_pdf(tex_file, pdf_path, keep_aux=False)

        if compiled:
            job["resume_file_path"] = f"/home/chefhaider/Repositories/job_automation/output/{pdf_name}"
            print(f"  ✅ {job['resume_file_path']}")
        else:
            job["resume_file_path"] = f"/home/chefhaider/Repositories/job_automation/output/{input_txt_name}"
            print(f"  ⚠️  LaTeX compilation failed. Saved alternative raw text here: {job['resume_file_path']}")

        # ── Rate Limit Preservation Sleep Mechanism ──
        if i < len(jobs) - 1:
            # Determine sleep depth based on which pool limits were consumed
            is_high_tier = "mini" not in model_used and "8b" not in model_used.lower()
            sleep_duration = BASE_WAIT_HIGH_TIER if is_high_tier else BASE_WAIT_LOW_TIER
            
            print(f"  ⏳ Waiting {sleep_duration}s to respect the {model_used} token pool budget...")
            time.sleep(sleep_duration)

    with open(jobs_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Pipeline Complete! Output tracked inside: {jobs_json}")


if __name__ == "__main__":
    build_resumes()