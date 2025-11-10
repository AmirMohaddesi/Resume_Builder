from pathlib import Path

import pytest

from resume_builder.tools.latex_edit import LatexEditTool


def test_full_content_overwrite(make_tex) -> None:
    original = r"""
\documentclass{article}
\begin{document}
Old content
\end{document}
""".lstrip()
    path = make_tex("test.tex", original)
    tool = LatexEditTool()

    new_content = r"""
\documentclass{article}
\begin{document}
New content!
\end{document}
""".lstrip()

    result = tool._run(tex_path=str(path), full_content=new_content)
    assert result["success"] is True
    written = Path(result["tex_path"]).read_text(encoding="utf-8")
    assert "New content!" in written
    assert "Old content" not in written


def test_markers_replace_and_append(make_tex) -> None:
    content = r"""
\documentclass{article}
\begin{document}
% BEGIN:SUMMARY
Old summary
% END:SUMMARY
\end{document}
""".lstrip()
    path = make_tex("marker.tex", content)
    tool = LatexEditTool()

    result = tool._run(
        tex_path=str(path),
        markers={
            "SUMMARY": "This is the new summary.",
            # Use double backslashes to avoid invalid escape sequences in regex replacement
            "SKILLS": r"\\begin{itemize}\\item Python\\item LaTeX\\end{itemize}",
        },
        append_missing_blocks=True,
    )
    assert result["success"] is True
    written = Path(result["tex_path"]).read_text(encoding="utf-8")
    assert "This is the new summary." in written
    assert "Old summary" not in written
    # Appended block exists before \end{document}
    assert "% BEGIN:SKILLS" in written
    assert r"\item Python" in written


def test_sections_replace_and_append(make_tex) -> None:
    content = r"""
\documentclass{article}
\begin{document}
\section*{Experience}
Old experience text.
% some comment
\section*{Education}
BS in Something
\end{document}
""".lstrip()
    path = make_tex("sections.tex", content)
    tool = LatexEditTool()

    result = tool._run(
        tex_path=str(path),
        sections={
            "Experience": "5 years of Python and ML.",
            "Skills": "Python, Pandas, SQL",
        },
        append_missing_blocks=True,
    )
    assert result["success"] is True
    written = Path(result["tex_path"]).read_text(encoding="utf-8")
    # Replaced Experience body
    assert "5 years of Python and ML." in written
    assert "Old experience text." not in written
    # Appended missing section
    assert r"\section*{Skills}" in written
    assert "Python, Pandas, SQL" in written


def test_substitutions(make_tex) -> None:
    content = r"""
\documentclass{article}
\begin{document}
Hello NAME
\end{document}
""".lstrip()
    path = make_tex("subs.tex", content)
    tool = LatexEditTool()

    result = tool._run(
        tex_path=str(path),
        substitutions={"NAME": "World"},
    )
    assert result["success"] is True
    written = Path(result["tex_path"]).read_text(encoding="utf-8")
    assert "Hello World" in written
    assert "Hello NAME" not in written


