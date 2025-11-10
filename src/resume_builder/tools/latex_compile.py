from __future__ import annotations

"""
Tool for compiling LaTeX files into PDF documents.

This module defines a tool that wraps a safe invocation of `pdflatex` to
compile a LaTeX source file into a PDF. The compilation is performed in a
temporary directory to avoid polluting the working directory with auxiliary
files. The resulting PDF is copied into an `output` directory relative to
the project root. Similar to the original engineering_team implementation,
no shell escape is allowed and a timeout is enforced on the compilation
process. See LatexCompileTool for usage details.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

# Try to import logger, fallback to None if not available
try:
    from resume_builder.logger import get_logger
    logger = get_logger("latex_compile")
except ImportError:
    import logging
    logger = logging.getLogger("latex_compile")


class LatexCompileInput(BaseModel):
    """Input schema for the LatexCompileTool."""
    tex_path: str = Field(..., description="Absolute or relative path to the LaTeX file to compile.")
    out_name: str = Field(default="resume.pdf", description="Filename of the generated PDF.")
    # Accept optional extras from tasks.yaml to avoid validation/type errors
    workdir: str | None = Field(default=None, description="Optional working directory (ignored).")
    engine: str | None = Field(default=None, description="LaTeX engine hint (ignored; uses pdflatex).")
    log_path: str | None = Field(default=None, description="Optional compile log path (ignored by tool).")
    model_config = ConfigDict(extra="ignore")


class LatexCompileTool(BaseTool):
    """
    Compile a LaTeX file into a PDF using pdflatex.

    The tool copies the LaTeX file and any accompanying files into a temporary
    directory, runs `pdflatex` twice to resolve references, and then
    copies the resulting PDF into an `output` directory. If compilation
    fails or the PDF is not produced, it returns an error message.
    """

    name: str = "latex_compile_pdf"
    description: str = "Compile a LaTeX file into a PDF using pdflatex with safe defaults."
    # Declare args_schema as a ClassVar so Pydantic treats it as a static attribute.
    # Without the ClassVar annotation Pydantic v2 will interpret it as a field,
    # leading to errors when overriding args_schema on BaseTool subclasses.
    args_schema: Type[BaseModel] = LatexCompileInput

    @staticmethod
    def _extract_latex_errors(log_text: str) -> str:
        """Extract and format common LaTeX errors from compilation log."""
        errors = []
        lines = log_text.split('\n')
        
        # Look for error patterns
        error_patterns = [
            (r'! (.*)', 'LaTeX Error'),
            (r'Error: (.*)', 'Error'),
            (r'Fatal error: (.*)', 'Fatal Error'),
            (r'Undefined control sequence', 'Undefined control sequence'),
            (r'Missing .* inserted', 'Missing character'),
            (r'Overfull .*', 'Overfull hbox'),
            (r'Underfull .*', 'Underfull hbox'),
            (r'Package .* Error', 'Package Error'),
        ]
        
        for i, line in enumerate(lines):
            for pattern, label in error_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Include context (next few lines)
                    context = '\n'.join(lines[i:min(i+5, len(lines))])
                    errors.append(f"[{label}] {context}")
                    break
        
        if errors:
            return "\n\n--- EXTRACTED ERRORS ---\n\n" + "\n\n".join(errors[:5])  # Limit to 5 errors
        return ""

    def _run(self, tex_path: str, out_name: str = "resume.pdf", log_path: str | None = None, **_: Any) -> Dict[str, Any]:  # type: ignore[override]
        logger.info(f"Starting LaTeX compilation: {tex_path} -> {out_name}")
        tex = Path(tex_path).resolve()
        logger.debug(f"Resolved LaTeX path: {tex}")
        
        # Strip "output/" prefix from out_name to prevent nested output/ directories
        out_name_clean = out_name.replace("\\", "/")
        if out_name_clean.startswith("output/"):
            out_name = out_name_clean[7:]  # Remove "output/" prefix
            logger.debug(f"Stripped 'output/' prefix from out_name: {out_name}")
        
        # Find project root reliably
        # Strategy: Look for common project markers (pyproject.toml, src/, output/)
        def find_project_root(start_path: Path) -> Path:
            """Find project root by looking for markers."""
            current = start_path.resolve()
            # Check up to 5 levels up
            for _ in range(5):
                # Check for project markers - prioritize pyproject.toml and src/ over output/
                # This prevents stopping at output/ when we're already inside it
                if (current / "pyproject.toml").exists() or (current / "src").exists():
                    return current
                # Only check for output/ if we're not already inside an output/ directory
                # and if it's not the start_path itself
                if (current / "output").exists() and current.name != "output":
                    return current
                if current.parent == current:  # Reached filesystem root
                    break
                current = current.parent
            # Fallback: If tex is in output/, go up one level to get project root
            if "output" in tex.parts:
                # Find where "output" appears in the path and go up one level
                output_idx = list(tex.parts).index("output")
                if output_idx > 0:
                    return Path(*tex.parts[:output_idx])
            # Last resort: use current working directory
            return Path.cwd()
        
        # Find project root starting from the tex file location
        project_root = find_project_root(tex.parent)
        output_dir = project_root / "output"
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Ensure output_dir is absolute and doesn't create nested paths
        output_dir = output_dir.resolve()
        
        # If log_path is provided and is relative, resolve it relative to output_dir
        if log_path:
            compile_log_path = Path(log_path)
            if not compile_log_path.is_absolute():
                # If it starts with "output/", remove that prefix
                log_str = str(compile_log_path).replace("\\", "/")
                if log_str.startswith("output/"):
                    log_str = log_str[7:]  # Remove "output/" prefix
                compile_log_path = output_dir / log_str
            else:
                compile_log_path = Path(log_path).resolve()
        else:
            compile_log_path = output_dir / "compile.log"
        
        logger.debug(f"Project root: {project_root}")
        logger.debug(f"Output directory: {output_dir}, Log path: {compile_log_path}")
        
        # Check if pdflatex is available
        logger.debug("Checking for pdflatex...")
        try:
            result = subprocess.run(
                ["pdflatex", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True,
            )
            logger.debug(f"pdflatex found: {result.stdout.decode()[:50]}...")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            error_msg = "pdflatex not found. Please install a LaTeX distribution (e.g., MiKTeX or TeX Live). See INSTALL_LATEX.md for instructions."
            logger.error(f"pdflatex check failed: {e}")
            # Remove any existing corrupted PDF
            final_path = output_dir / out_name
            if final_path.exists():
                final_path.unlink()
                logger.debug(f"Removed existing PDF: {final_path}")
            try:
                compile_log_path.write_text(error_msg, encoding="utf-8")
            except Exception:
                pass
            # Raise exception so agent sees the error
            raise RuntimeError(error_msg)
        
        # Clean the LaTeX file - remove markdown code fences if present
        logger.debug("Reading and cleaning LaTeX content...")
        tex_content = tex.read_text(encoding="utf-8")
        original_size = len(tex_content)
        
        # Fix escaped newlines (common LLM mistake: generates \n instead of real newlines)
        if "\\n" in tex_content and tex_content.count("\\n") > 5:
            logger.warning(f"Found {tex_content.count('\\n')} escaped newlines, fixing...")
            # Replace escaped newlines with real newlines
            tex_content = tex_content.replace("\\n", "\n")
            # Also handle escaped backslashes that might have been intended as newlines
            tex_content = tex_content.replace("\\\\n", "\n")
            logger.info("Fixed escaped newlines in LaTeX content")
        
        # Remove markdown code fences (```latex and ```)
        if tex_content.startswith("```"):
            logger.warning("Found markdown code fences, removing...")
            lines = tex_content.split("\n")
            # Remove first line if it's a code fence
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove last line if it's a code fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            tex_content = "\n".join(lines)
            logger.info("Removed markdown code fences")
        
        if len(tex_content) != original_size:
            logger.debug(f"LaTeX content size changed: {original_size} -> {len(tex_content)} bytes")
        
        # Write cleaned content back
        tex.write_text(tex_content, encoding="utf-8")
        logger.debug(f"Cleaned LaTeX written to: {tex}")
        
        # Use a temporary directory for compilation
        with tempfile.TemporaryDirectory() as tmpdir:
            work = Path(tmpdir)
            # Copy the LaTeX file to temp dir
            work_tex = work / tex.name
            work_tex.write_text(tex_content, encoding="utf-8")
            # Copy any other files from the tex directory
            for f in tex.parent.iterdir():
                if f.is_file() and f != tex:
                    shutil.copy(f, work / f.name)
            
            command = [
                "pdflatex",
                "-interaction=nonstopmode",
                "-no-shell-escape",
                "-output-directory", str(work),
                tex.name,
            ]
            
            compilation_log = []
            try:
                logger.info("Running pdflatex (first pass)...")
                # Run pdflatex twice to ensure references are resolved
                result1 = subprocess.run(
                    command,
                    cwd=work,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                    check=False,
                    text=True,
                )
                compilation_log.append(result1.stdout)
                logger.debug(f"First pass exit code: {result1.returncode}")
                
                logger.info("Running pdflatex (second pass for references)...")
                result2 = subprocess.run(
                    command,
                    cwd=work,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                    check=False,
                    text=True,
                )
                compilation_log.append(result2.stdout)
                logger.debug(f"Second pass exit code: {result2.returncode}")
                
                # Extract errors from log
                full_log = "\n\n".join(compilation_log)
                extracted_errors = self._extract_latex_errors(full_log)
                if extracted_errors:
                    logger.warning("LaTeX compilation errors detected:")
                    logger.warning(extracted_errors)
                else:
                    logger.info("No LaTeX errors detected in compilation log")
                
                # Persist log after runs
                try:
                    compile_log_path.write_text(full_log, encoding="utf-8")
                    logger.debug(f"Compilation log saved to: {compile_log_path}")
                except Exception as e:
                    logger.warning(f"Failed to save compilation log: {e}")
            except subprocess.TimeoutExpired:
                logger.error("LaTeX compilation timed out after 60 seconds")
                try:
                    compile_log_path.write_text("LaTeX compilation timed out", encoding="utf-8")
                except Exception:
                    pass
                return {"success": False, "error": "LaTeX compilation timed out"}
            except Exception as e:
                logger.exception(f"Exception during LaTeX compilation: {e}")
                # Write whatever we captured
                try:
                    compile_log_path.write_text("\n\n".join(compilation_log + [f"Exception: {e}"]), encoding="utf-8")
                except Exception:
                    pass
                return {"success": False, "error": f"Compilation error: {str(e)}"}
            
            pdf_file = work / f"{tex.stem}.pdf"
            logger.debug(f"Checking for generated PDF: {pdf_file}")
            if not pdf_file.exists():
                logger.error("PDF file was not generated by pdflatex")
                # Return error log for debugging
                error_log = "\n".join(compilation_log)
                extracted_errors = self._extract_latex_errors(error_log)
                # Don't create a corrupted PDF file - remove it if it exists
                final_path = output_dir / out_name
                if final_path.exists():
                    final_path.unlink()  # Delete corrupted PDF
                    logger.debug(f"Removed existing PDF: {final_path}")
                error_msg = f"PDF not generated. pdflatex compilation failed.\n\n{extracted_errors}\n\nFull compilation log (last 1000 chars):\n{error_log[-1000:] if error_log else 'No compilation log available. Is pdflatex installed?'}\n\nTIP: Copy the LaTeX content from output/rendered_resume.tex to Overleaf to see detailed errors."
                try:
                    compile_log_path.write_text(f"{extracted_errors}\n\n--- FULL LOG ---\n\n{error_log}", encoding="utf-8")
                except Exception:
                    pass
                raise RuntimeError(error_msg)
            
            pdf_size = pdf_file.stat().st_size
            logger.info(f"PDF generated successfully: {pdf_size:,} bytes")
            
            # Verify PDF is valid (not empty or corrupted)
            if pdf_size < 1000:  # PDFs should be at least 1KB
                logger.warning(f"PDF file is suspiciously small: {pdf_size} bytes")
                error_log = "\n".join(compilation_log)
                extracted_errors = self._extract_latex_errors(error_log)
                final_path = output_dir / out_name
                if final_path.exists():
                    final_path.unlink()  # Delete corrupted PDF
                error_msg = f"Generated PDF is too small (corrupted). Compilation likely failed.\n\n{extracted_errors}\n\nFull compilation log (last 1000 chars):\n{error_log[-1000:] if error_log else 'No compilation log available.'}\n\nTIP: Copy the LaTeX content from output/rendered_resume.tex to Overleaf to see detailed errors."
                try:
                    compile_log_path.write_text(f"{extracted_errors}\n\n--- FULL LOG ---\n\n{error_log}", encoding="utf-8")
                except Exception:
                    pass
                raise RuntimeError(error_msg)
            
            # Copy the PDF to the output directory
            # IMPORTANT: Do this BEFORE the temp directory context exits
            # Ensure output directory exists (create parent directories if needed)
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / out_name
            
            # Read PDF bytes while still in temp directory context
            pdf_bytes = pdf_file.read_bytes()
            pdf_size = len(pdf_bytes)
            
            # Verify we actually read something
            if pdf_size < 1000:
                error_log = "\n".join(compilation_log)
                extracted_errors = self._extract_latex_errors(error_log)
                error_msg = f"PDF file is too small after read ({pdf_size} bytes). Copy may have failed.\n\n{extracted_errors}\n\nFull compilation log (last 1000 chars):\n{error_log[-1000:] if error_log else 'No compilation log available.'}"
                try:
                    compile_log_path.write_text(f"{extracted_errors}\n\n--- FULL LOG ---\n\n{error_log}", encoding="utf-8")
                except Exception:
                    pass
                raise RuntimeError(error_msg)
            
        # Remove old PDF if it exists
        final_path = Path(final_path)
        if final_path.exists():
            logger.debug(f"Removing existing PDF: {final_path}")
            final_path.unlink()
        
        # Ensure directory exists before writing
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the PDF bytes to final location
        logger.debug(f"Writing PDF to: {final_path}")
        try:
            final_path.write_bytes(pdf_bytes)
            # Verify the write succeeded
            written_size = final_path.stat().st_size if final_path.exists() else 0
            if written_size != pdf_size:
                logger.error(f"PDF write verification failed. Expected {pdf_size} bytes, got {written_size}")
                raise IOError(f"PDF write verification failed. Expected {pdf_size} bytes, got {written_size}")
            logger.info(f"✓ PDF successfully copied to: {final_path} ({pdf_size:,} bytes)")
        except Exception as e:
            logger.exception(f"Failed to write PDF to {final_path}: {e}")
            error_msg = f"Failed to copy PDF to {final_path}: {e}\n\nPDF was successfully compiled ({pdf_size} bytes) but copy failed.\nYou can manually copy it or run: python fix_pdf.py"
            try:
                compile_log_path.write_text(f"{error_msg}\n\n--- COMPILATION LOG ---\n\n{chr(10).join(compilation_log)}", encoding="utf-8")
            except Exception:
                pass
            raise RuntimeError(error_msg)
        
        logger.info(f"LaTeX compilation completed successfully: {final_path}")
        return {"success": True, "pdf_path": str(final_path.resolve()), "log_path": str(compile_log_path.resolve()), "pdf_size": pdf_size}