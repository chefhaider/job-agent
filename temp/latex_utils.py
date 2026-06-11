import os
import subprocess
import sys
import shutil
from pathlib import Path

def compile_latex_to_pdf(tex_file_path: str, output_dir: str = None, keep_aux: bool = False):
    """
    Compile a .tex file to PDF using latexmk (same as Overleaf).
    
    Parameters:
        tex_file_path: Path to your main .tex file (e.g., "main.tex")
        output_dir: Directory to store output files (default: same as .tex file)
        keep_aux: If False, cleans up auxiliary files after compilation
    """
    tex_path = Path(tex_file_path).resolve()
    
    if not tex_path.exists():
        print(f"Error: File {tex_path} not found!")
        return False
    
    if output_dir:
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = tex_path.parent
    
    # Change working directory to where the .tex file is (important for includes)
    original_cwd = os.getcwd()
    os.chdir(tex_path.parent)
    
    try:
        print(f"Compiling {tex_path.name} ...")
        
        # This is exactly what Overleaf runs:
        result = subprocess.run([
            "latexmk",
            "-pdf",                   # Generate PDF using pdflatex
            "-interaction=nonstopmode",  # Don't stop on errors
            "-halt-on-error",         # Stop on serious errors
            "-outdir=" + str(out_dir), # Output directory
            tex_path.name
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("LaTeX compilation failed!")
            print(result.stdout)
            print(result.stderr)
            return False
        
        pdf_path = out_dir / (tex_path.stem + ".pdf")
        if pdf_path.exists():
            print(f"Success! PDF created: {pdf_path}")
            return str(pdf_path)
        else:
            print("Compilation seemed successful but PDF was not found.")
            return False
            
    except FileNotFoundError:
        print("Error: 'latexmk' not found. Please install TeX Live or MiKTeX.")
        print("\nOn Windows (MiKTeX): Install from https://miktex.org/")
        print("On macOS: sudo tlmgr update --self && sudo tlmgr install latexmk")
        print("On Linux (Ubuntu/Debian): sudo apt install texlive-latex-extra latexmk")
        return False
    finally:
        os.chdir(original_cwd)
        
        # Clean up auxiliary files (like Overleaf's "Recompile from scratch")
        if not keep_aux:
            subprocess.run(["latexmk", "-c", "-outdir=" + str(out_dir)], cwd=tex_path.parent)

# ============================
# Example Usage
# ============================
# Change this to your .tex file!
tex_file = "main.tex"        # or "report.tex", "thesis.tex", etc.

# Optional: specify output directory
pdf_path = compile_latex_to_pdf(tex_file, output_dir="output", keep_aux=False)

if pdf_path:
    print(f"\nYour PDF is ready: {pdf_path}")
    
    # Optional: Open PDF automatically
    if shutil.which("open" if sys.platform == "darwin" else "xdg-open" if sys.platform == "linux" else "start"):
        os.startfile(pdf_path) if sys.platform == "win32" else \
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", pdf_path])