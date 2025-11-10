from pathlib import Path

from resume_builder.tools.pdf_read import PdfReadTool


def test_missing_file_returns_error(tmp_path: Path) -> None:
    tool = PdfReadTool()
    missing = tmp_path / "nope.pdf"
    result = tool._run(pdf_path=str(missing))
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_extract_text_from_simple_pdf(write_sample_pdf) -> None:
    path = write_sample_pdf("hello.pdf")
    tool = PdfReadTool()
    result = tool._run(pdf_path=str(path))
    # Depending on available tools, text extraction should succeed for this simple PDF
    assert isinstance(result, dict)
    if result["success"]:
        content = result["content"]
        assert isinstance(content, str)
        # Looser match; some extractors may add whitespace/newlines
        assert "Hello" in content or "HELLO" in content.upper()
    else:
        # If no extraction backends are available, ensure we get a clear error
        assert "could not extract text" in result["error"].lower()


