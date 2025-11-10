from pathlib import Path
from typing import Any, Optional

import pytest

from resume_builder.tools.latex_compile import LatexCompileTool


def _fake_completed(stdout: str = "", returncode: int = 0) -> Any:
    class _CP:
        def __init__(self, stdout: str, returncode: int) -> None:
            self.stdout = stdout
            self.returncode = returncode

    return _CP(stdout=stdout, returncode=returncode)


def test_raises_when_pdflatex_missing(make_tex, monkeypatch) -> None:
    # Force the version check to fail consistently
    def fake_run_version(*args, **kwargs):
        raise FileNotFoundError("pdflatex not installed")

    monkeypatch.setattr("subprocess.run", fake_run_version)
    path = make_tex("doc.tex", r"\documentclass{article}\begin{document}Hi\end{document}")
    tool = LatexCompileTool()

    with pytest.raises(RuntimeError) as exc:
        tool._run(tex_path=str(path), out_name="x.pdf")
    assert "pdflatex not found" in str(exc.value).lower()


def test_successful_compilation_with_fake_subprocess(make_tex, monkeypatch, tmp_path) -> None:
    # Create .tex
    path = make_tex(
        "doc.tex",
        r"\documentclass{article}\begin{document}Hello\end{document}",
    )
    tool = LatexCompileTool()

    def fake_run(args, cwd: Optional[Path] = None, stdout=None, stderr=None, timeout=None, check=None, text=None, capture_output=None):
        # Simulate version check
        if "--version" in args:
            return _fake_completed(stdout="pdfTeX 3.141592", returncode=0)
        # For compilation runs, write a valid-looking PDF into cwd named after tex
        if cwd is not None:
            # Find tex name from args (last arg)
            tex_name = args[-1]
            pdf_path = Path(cwd) / (Path(tex_name).stem + ".pdf")
            # Large enough and with header to pass verification
            pdf_bytes = b"%PDF-1.4\n" + b"x" * 2048
            pdf_path.write_bytes(pdf_bytes)
        return _fake_completed(stdout="OK", returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = tool._run(tex_path=str(path), out_name="result.pdf")
    assert result["success"] is True
    out_path = Path(result["pdf_path"])
    assert out_path.exists()
    assert out_path.name == "result.pdf"
    assert out_path.stat().st_size >= 2000


def test_compilation_generates_too_small_pdf_raises(make_tex, monkeypatch) -> None:
    path = make_tex("small.tex", r"\documentclass{article}\begin{document}Hi\end{document}")
    tool = LatexCompileTool()

    def fake_run(args, cwd: Optional[Path] = None, stdout=None, stderr=None, timeout=None, check=None, text=None, capture_output=None):
        if "--version" in args:
            return _fake_completed(stdout="pdfTeX 3.141592", returncode=0)
        if cwd is not None:
            tex_name = args[-1]
            pdf_path = Path(cwd) / (Path(tex_name).stem + ".pdf")
            # Too small (< 1000 bytes)
            pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
        return _fake_completed(stdout="OK", returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError) as exc:
        tool._run(tex_path=str(path), out_name="small.pdf")
    assert "too small" in str(exc.value).lower()


def test_compilation_no_pdf_generated_raises(make_tex, monkeypatch) -> None:
    path = make_tex("nopdf.tex", r"\documentclass{article}\begin{document}Hi\end{document}")
    tool = LatexCompileTool()

    def fake_run(args, cwd: Optional[Path] = None, stdout=None, stderr=None, timeout=None, check=None, text=None, capture_output=None):
        if "--version" in args:
            return _fake_completed(stdout="pdfTeX 3.141592", returncode=0)
        # Do not write any PDF to cwd -> simulate compilation failure
        return _fake_completed(stdout="Compilation failed", returncode=1)

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError) as exc:
        tool._run(tex_path=str(path), out_name="fail.pdf")
    assert "pdf not generated" in str(exc.value).lower()


