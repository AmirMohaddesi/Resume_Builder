from pathlib import Path

from resume_builder.tools.pdf_verify import PdfVerifyTool


def test_missing_file_returns_not_exists(tmp_path: Path) -> None:
    tool = PdfVerifyTool()
    missing = tmp_path / "nope.pdf"
    result = tool._run(pdf_path=str(missing))
    assert result["success"] is False
    assert result["exists"] is False
    assert "not found" in result["error"].lower()


def test_too_small_pdf_flagged_corrupted(tmp_path: Path) -> None:
    # Write a tiny PDF-like file
    path = tmp_path / "small.pdf"
    path.write_bytes(b"%PDF-1.4\n% tiny\n")

    tool = PdfVerifyTool()
    result = tool._run(pdf_path=str(path))
    assert result["success"] is False
    assert result["exists"] is True
    assert result["corrupted"] is True
    assert "too small" in result["error"].lower()


def test_invalid_header_flagged_corrupted(tmp_path: Path) -> None:
    # Valid size, invalid header
    path = tmp_path / "bad_header.pdf"
    data = b"NOTPDF" + b"x" * 2000  # > 1KB
    path.write_bytes(data)

    tool = PdfVerifyTool()
    result = tool._run(pdf_path=str(path))
    assert result["success"] is False
    assert result["exists"] is True
    assert result["corrupted"] is True
    assert "valid pdf header" in result["error"].lower()


def test_valid_pdf_with_count_and_size(tmp_path: Path) -> None:
    # Minimal valid-looking PDF with header and /Count marker
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<<>>endobj\n"
        b"2 0 obj<<>>endobj\n"
        b"3 0 obj<<>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n"
        b"0000000020 00000 n \n0000000030 00000 n \n"
        b"trailer<< /Size 4 >>\nstartxref\n123\n%%EOF\n"
    )
    # Add a /Count 2 marker somewhere in the body to be detected heuristically
    pdf_bytes += b"\n/Count 2\n" + b"x" * 3000
    path = tmp_path / "ok.pdf"
    path.write_bytes(pdf_bytes)

    tool = PdfVerifyTool()
    result = tool._run(pdf_path=str(path))
    assert result["success"] is True
    assert result["exists"] is True
    assert result["corrupted"] is False
    assert result["file_size"] == path.stat().st_size
    assert result["page_count"] in (None, 2)  # heuristics or external tools might set 2


