import base64
import sys
from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture(scope="session", autouse=True)
def add_src_to_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


@pytest.fixture
def make_tex(tmp_path: Path) -> Callable[[str, str], Path]:
    def _make_tex(filename: str, content: str) -> Path:
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        return path

    return _make_tex


# Minimal valid PDF with visible text "Hello, PDF!" (Base64-encoded)
_SIMPLE_TEXT_PDF_B64 = (
    "JVBERi0xLjQKJeLjz9MKNyAwIG9iago8PC9UeXBlIC9QYWdlCi9QYXJlbnQgNSAwIFIKL1Jl"
    "c291cmNlcyA8PC9Gb250IDw8L0YxIDQgMCBSPj4+PgovTWVkaWFCb3ggWzAgMCAyMDAgMjAw"
    "XQovQ29udGVudHMgNiAwIFI+PgplbmRvYmoKNCAwIG9iago8PC9UeXBlIC9Gb250Ci9TdWJ0"
    "eXBlIC9UeXBlMQovQmFzZUZvbnQgL0hlbHZldGljYT4+CmVuZG9iago2IDAgb2JqCjw8L0xl"
    "bmd0aCA1Mz4+CnN0cmVhbQpCVC9GMSAyNCBUZiA3MiAxMjAgVGQgKEhlbGxvLCBQRkQhKSBU"
    "agpFVAplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwvVHlwZSAvUGFnZXMKL0tpZHMgWzMg"
    "MCBSXQovQ291bnQgMT4+CmVuZG9iagozIDAgb2JqCjw8L1R5cGUgL1BhZ2UKL1BhcmVudCA1"
    "IDAgUgovTWVkaWFCb3ggWzAgMCAyMDAgMjAwXQovUmVzb3VyY2VzIDw8L0ZvbnQgPDwvRjEg"
    "NCAwIFI+Pj4+Ci9Db250ZW50cyA2IDAgUj4+CmVuZG9iagoyIDAgb2JqCjw8L1R5cGUgL1Bh"
    "Z2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDE+PgplbmRvYmoKMSAwIG9iago8PC9UeXBlIC9D"
    "YXRhbG9nCi9QYWdlcyAyIDAgUj4+CmVuZG9iagp4cmVmCjAgNwowMDAwMDAwMDAwIDY1NTM1"
    "IGYgCjAwMDAwMDAxMTQgMDAwMDAgbiAKMDAwMDAwMDA3MCAwMDAwMCBuIAowMDAwMDAwMzQ2"
    "IDAwMDAwIG4gCjAwMDAwMDAxODYgMDAwMDAgbiAKMDAwMDAwMDQ2MyAwMDAwMCBuIAowMDAw"
    "MDAwMjc5IDAwMDAwIG4gCnRyYWlsZXIKPDwvUm9vdCAxIDAgUgovU2l6ZSA3Pj4Kc3RhcnR4"
    "cmVmCjUwNQolJUVPRgo="
)


@pytest.fixture
def write_sample_pdf(tmp_path: Path) -> Callable[[str], Path]:
    def _write(filename: str = "sample.pdf") -> Path:
        pdf_bytes = base64.b64decode(_SIMPLE_TEXT_PDF_B64)
        path = tmp_path / filename
        path.write_bytes(pdf_bytes)
        return path

    return _write


