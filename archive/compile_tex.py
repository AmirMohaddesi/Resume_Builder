#!/usr/bin/env python
"""
Simple script to compile a LaTeX .tex file to PDF.

Usage:
    python compile_tex.py [path/to/file.tex] [--engine pdflatex|xelatex|auto]

Examples:
    python compile_tex.py output/generated/rendered_resume.tex
    python compile_tex.py output/generated/rendered_resume.tex --engine xelatex
    python compile_tex.py output/generated/rendered_resume.tex --engine auto
"""

import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path


def find_project_root(start_path: Path) -> Path:
    """Find project root by looking for markers."""
    current = start_path.resolve()
    for _ in range(5):
        if (current / "pyproject.toml").exists() or (current / "src").exists():
            return current
        if (current / "output").exists() and current.name != "output":
            return current
        if current.parent == current:
            break
        current = current.parent
    if "output" in start_path.parts:
        output_idx = list(start_path.parts).index("output")
        if output_idx > 0:
            return Path(*start_path.parts[:output_idx])
    return Path.cwd()


def check_engine(engine_name: str) -> bool:
    """Check if LaTeX engine is available."""
    try:
        result = subprocess.run(
            [engine_name, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_engine(tex_content: str) -> str:
    """Auto-detect which engine to use based on content."""
    import re
    unicode_emoji_pattern = r'[📞📧🌐🔗💻🎓🏠📍]'
    if re.search(unicode_emoji_pattern, tex_content):
        if check_engine("xelatex"):
            return "xelatex"
    return "pdflatex"


def main():
    parser = argparse.ArgumentParser(
        description="Compile a LaTeX .tex file to PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compile_tex.py output/generated/rendered_resume.tex
  python compile_tex.py output/generated/rendered_resume.tex --engine xelatex
  python compile_tex.py output/generated/rendered_resume.tex --engine auto
        """
    )
    
    parser.add_argument(
        "tex_file",
        type=str,
        help="Path to the .tex file to compile"
    )
    
    parser.add_argument(
        "--engine",
        type=str,
        default="auto",
        choices=["pdflatex", "xelatex", "auto"],
        help="LaTeX engine to use: 'pdflatex' (default), 'xelatex' (for Unicode/emojis), or 'auto' (auto-detect)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output PDF filename (default: same as .tex file but with .pdf extension)"
    )
    
    args = parser.parse_args()
    
    # Resolve the tex file path
    tex_path = Path(args.tex_file).resolve()
    if not tex_path.exists():
        print(f"❌ Error: File not found: {tex_path}")
        sys.exit(1)
    
    if not tex_path.suffix == ".tex":
        print(f"⚠️  Warning: File doesn't have .tex extension: {tex_path}")
    
    # Determine output filename
    if args.output:
        output_name = args.output
    else:
        output_name = tex_path.stem + ".pdf"
    
    # Find project root and output directory
    project_root = find_project_root(tex_path.parent)
    output_dir = project_root / "output" / "generated"
    output_dir.mkdir(exist_ok=True, parents=True)
    final_pdf = output_dir / output_name
    
    print(f"📄 Compiling: {tex_path}")
    print(f"📦 Output: {final_pdf}")
    
    # Read LaTeX content to detect engine
    tex_content = tex_path.read_text(encoding="utf-8")
    
    # Determine engine
    if args.engine == "auto":
        engine_name = detect_engine(tex_content)
        print(f"🔧 Auto-detected engine: {engine_name}")
    else:
        engine_name = args.engine
        print(f"🔧 Using engine: {engine_name}")
    
    # Check if engine is available
    if not check_engine(engine_name):
        if engine_name == "xelatex":
            print(f"⚠️  {engine_name} not found, falling back to pdflatex")
            engine_name = "pdflatex"
        if not check_engine(engine_name):
            print(f"❌ Error: {engine_name} not found. Please install a LaTeX distribution.")
            print(f"   Windows: Install MiKTeX from https://miktex.org/download")
            print(f"   Linux: sudo apt-get install texlive-full")
            print(f"   macOS: Install MacTeX from https://www.tug.org/mactex/")
            sys.exit(1)
    
    # Copy resumecv.cls if it exists
    templates_dir = project_root / "src" / "resume_builder" / "templates"
    class_file = templates_dir / "resumecv.cls"
    
    # Use a temporary directory for compilation
    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir)
        
        # Copy the LaTeX file to temp dir
        work_tex = work / tex_path.name
        work_tex.write_text(tex_content, encoding="utf-8")
        
        # Copy resumecv.cls if it exists
        if class_file.exists():
            shutil.copy(class_file, work / "resumecv.cls")
            print(f"📋 Copied resumecv.cls to temp directory")
        
        # Copy any other files from the tex directory
        for f in tex_path.parent.iterdir():
            if f.is_file() and f.suffix in [".cls", ".sty", ".tex"] and f != tex_path:
                shutil.copy(f, work / f.name)
        
        # Compile (run twice to resolve references)
        command = [
            engine_name,
            "-interaction=nonstopmode",
            "-no-shell-escape",
            "-output-directory", str(work),
            tex_path.name,
        ]
        
        print(f"\n🔄 Running {engine_name} (first pass)...")
        try:
            result1 = subprocess.run(
                command,
                cwd=str(work),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            
            if result1.returncode != 0:
                print(f"⚠️  First pass had warnings/errors (this is often normal)")
            
            print(f"🔄 Running {engine_name} (second pass for references)...")
            result2 = subprocess.run(
                command,
                cwd=str(work),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            
            # Check if PDF was created
            work_pdf = work / tex_path.stem / (tex_path.stem + ".pdf")
            if not work_pdf.exists():
                # Try alternative location
                work_pdf = work / (tex_path.stem + ".pdf")
            
            if work_pdf.exists():
                # Copy PDF to output directory
                shutil.copy(work_pdf, final_pdf)
                pdf_size = final_pdf.stat().st_size
                print(f"\n✅ Success! PDF generated:")
                print(f"   📄 {final_pdf}")
                print(f"   📊 Size: {pdf_size:,} bytes")
                
                # Save compilation log
                log_path = output_dir / "compile.log"
                log_content = f"=== First Pass ===\n{result1.stdout.decode('utf-8', errors='replace')}\n\n=== Second Pass ===\n{result2.stdout.decode('utf-8', errors='replace')}"
                log_path.write_text(log_content, encoding="utf-8")
                print(f"   📝 Log: {log_path}")
            else:
                print(f"\n❌ Compilation failed: PDF not found")
                print(f"\n=== First Pass Output ===")
                print(result1.stdout.decode('utf-8', errors='replace')[-500:])
                print(f"\n=== Second Pass Output ===")
                print(result2.stdout.decode('utf-8', errors='replace')[-500:])
                sys.exit(1)
                
        except subprocess.TimeoutExpired:
            print(f"❌ Error: Compilation timed out (exceeded 60 seconds)")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error during compilation: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
