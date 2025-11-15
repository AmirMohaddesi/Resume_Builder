"""Tool for checking PDF quality and visual appearance."""

from __future__ import annotations

from pathlib import Path
from typing import Type, Optional, Dict, Any, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from ..paths import resolve_under_root

try:
    from resume_builder.logger import get_logger
    logger = get_logger("pdf_quality_checker")
except ImportError:
    import logging
    logger = logging.getLogger("pdf_quality_checker")


class PdfQualityCheckInput(BaseModel):
    """Input schema for PdfQualityCheckerTool."""
    pdf_path: str = Field(..., description="Path to the PDF file to check (absolute or relative to project root).")
    check_text: bool = Field(True, description="Whether to extract and verify text content.")
    check_layout: bool = Field(True, description="Whether to check for layout issues.")
    model_config = ConfigDict(extra="ignore")


class PdfQualityCheckerTool(BaseTool):
    """Check PDF quality, validity, and visual appearance."""
    
    name: str = "pdf_quality_check"
    description: str = (
        "Comprehensively check PDF quality including validity, readability, layout issues, "
        "and visual appearance. Use this after PDF compilation to ensure the resume looks good. "
        "Checks include: PDF structure validity, page count, text extraction, layout problems "
        "(orphaned headers, bad page breaks), and content verification."
    )
    args_schema: Type[BaseModel] = PdfQualityCheckInput
    
    def _check_pdf_structure(self, pdf_path: Path) -> Dict[str, Any]:
        """Check basic PDF structure validity."""
        issues = []
        warnings = []
        
        try:
            pdf_bytes = pdf_path.read_bytes()
            file_size = len(pdf_bytes)
            
            # Check file size
            if file_size < 1000:
                issues.append(f"PDF is suspiciously small ({file_size} bytes) - may be corrupted")
            elif file_size < 5000:
                warnings.append(f"PDF is relatively small ({file_size} bytes) - verify content is complete")
            
            # Check PDF header
            if not pdf_bytes.startswith(b'%PDF-'):
                issues.append("Invalid PDF header - file may be corrupted")
            
            # Check for PDF footer
            if b'%%EOF' not in pdf_bytes[-1024:]:  # Check last 1KB
                warnings.append("PDF footer marker (%%EOF) not found in expected location")
            
            # Try to estimate page count from PDF structure
            page_count = None
            try:
                # Look for /Count patterns in the PDF
                pdf_text = pdf_bytes.decode('latin-1', errors='ignore')
                import re
                # Look for /Count followed by a number
                count_matches = re.findall(r'/Count\s+(\d+)', pdf_text)
                if count_matches:
                    # Take the largest count found (usually the page count)
                    page_count = max(int(c) for c in count_matches)
            except Exception:
                pass
            
            return {
                "valid": len(issues) == 0,
                "file_size": file_size,
                "page_count": page_count,
                "issues": issues,
                "warnings": warnings
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to read PDF: {str(e)}",
                "issues": [f"Could not read PDF file: {str(e)}"]
            }
    
    def _extract_text(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract text from PDF to verify readability."""
        result = {
            "success": False,
            "text_length": 0,
            "has_content": False,
            "sections_found": [],
            "issues": []
        }
        
        # Try multiple extraction methods
        text_content = None
        
        # Method 1: Try PyPDF2
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                pages = []
                for page in pdf_reader.pages:
                    pages.append(page.extract_text())
                text_content = '\n'.join(pages)
                result["page_count"] = len(pdf_reader.pages)
        except ImportError:
            result["issues"].append("PyPDF2 not available for text extraction")
        except Exception as e:
            result["issues"].append(f"PyPDF2 extraction failed: {str(e)}")
        
        # Method 2: Try pdfplumber (more accurate)
        if not text_content or len(text_content.strip()) < 100:
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    pages = []
                    for page in pdf.pages:
                        pages.append(page.extract_text() or "")
                    text_content = '\n'.join(pages)
                    result["page_count"] = len(pdf.pages)
            except ImportError:
                if not result["issues"]:
                    result["issues"].append("pdfplumber not available for text extraction")
            except Exception as e:
                result["issues"].append(f"pdfplumber extraction failed: {str(e)}")
        
        # Method 3: Try pymupdf (fitz) - fastest and most reliable
        if not text_content or len(text_content.strip()) < 100:
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(pdf_path)
                pages = []
                for page_num in range(len(doc)):
                    pages.append(doc[page_num].get_text())
                text_content = '\n'.join(pages)
                result["page_count"] = len(doc)
                doc.close()
            except ImportError:
                if not result["issues"]:
                    result["issues"].append("PyMuPDF not available for text extraction")
            except Exception as e:
                result["issues"].append(f"PyMuPDF extraction failed: {str(e)}")
        
        if text_content:
            text_content = text_content.strip()
            result["success"] = True
            result["text_length"] = len(text_content)
            result["has_content"] = len(text_content) > 100
            
            if result["has_content"]:
                # Check for common resume sections
                text_lower = text_content.lower()
                sections = []
                if any(word in text_lower for word in ['summary', 'professional summary', 'objective']):
                    sections.append("Summary")
                if any(word in text_lower for word in ['experience', 'work experience', 'employment']):
                    sections.append("Experience")
                if any(word in text_lower for word in ['education', 'academic']):
                    sections.append("Education")
                if any(word in text_lower for word in ['skills', 'technical skills', 'competencies']):
                    sections.append("Skills")
                if any(word in text_lower for word in ['projects', 'achievements', 'publications']):
                    sections.append("Projects/Achievements")
                
                result["sections_found"] = sections
                
                # Check for common issues
                if len(text_content) < 500:
                    result["issues"].append("Very little text extracted - resume may be mostly empty")
                
                # Check for encoding issues
                if '\ufffd' in text_content:  # Replacement character
                    result["issues"].append("Text contains replacement characters - possible encoding issues")
            else:
                result["issues"].append("Text extraction returned very little content - PDF may be image-based or corrupted")
        else:
            result["issues"].append("Could not extract text using any available method")
        
        return result
    
    def _check_layout_issues(self, pdf_path: Path, text_content: Optional[str] = None) -> Dict[str, Any]:
        """Check for layout and formatting issues."""
        issues = []
        warnings = []
        
        if not text_content:
            # Try to extract text if not provided
            text_result = self._extract_text(pdf_path)
            if text_result.get("success"):
                text_content = None  # We'll extract again with page info
        
        # Check page count
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            
            if page_count == 0:
                issues.append("PDF has no pages")
            elif page_count > 2:
                warnings.append(f"Resume is {page_count} pages - consider condensing to 1-2 pages")
            
            # Check for orphaned headers (headers at bottom of page)
            # This is a heuristic check - we'd need more sophisticated analysis for perfect detection
            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()
                lines = text.split('\n')
                
                # Check last few lines of page for section headers
                if len(lines) > 3:
                    last_lines = [l.strip() for l in lines[-3:]]
                    # Common section header patterns
                    header_keywords = ['experience', 'education', 'skills', 'projects', 'summary']
                    for line in last_lines:
                        if any(keyword in line.lower() for keyword in header_keywords):
                            if len(line) < 50:  # Likely a header, not content
                                warnings.append(f"Possible orphaned header '{line}' at bottom of page {page_num + 1}")
            
            doc.close()
        except ImportError:
            warnings.append("PyMuPDF not available - cannot check detailed layout")
        except Exception as e:
            warnings.append(f"Layout check failed: {str(e)}")
        
        return {
            "issues": issues,
            "warnings": warnings
        }
    
    def _run(self, pdf_path: str, check_text: bool = True, check_layout: bool = True) -> str:
        """Check PDF quality and return comprehensive report."""
        try:
            pdf_file = resolve_under_root(pdf_path)
            
            if not pdf_file.exists():
                return f"[error] PDF file not found: {pdf_path}"
            
            if not pdf_file.suffix.lower() == '.pdf':
                return f"[error] File is not a PDF: {pdf_path}"
            
            # Run checks
            results = {
                "pdf_path": str(pdf_file),
                "structure_check": {},
                "text_check": {},
                "layout_check": {},
                "overall_status": "unknown"
            }
            
            # 1. Structure check (always run)
            logger.info(f"Checking PDF structure: {pdf_file}")
            results["structure_check"] = self._check_pdf_structure(pdf_file)
            
            # 2. Text extraction check
            if check_text:
                logger.info(f"Extracting text from PDF: {pdf_file}")
                results["text_check"] = self._extract_text(pdf_file)
            
            # 3. Layout check
            if check_layout:
                logger.info(f"Checking layout issues: {pdf_file}")
                text_for_layout = None
                if check_text and results["text_check"].get("success"):
                    # Re-extract with page info if needed
                    pass
                results["layout_check"] = self._check_layout_issues(pdf_file, text_for_layout)
            
            # Determine overall status
            all_issues = []
            all_warnings = []
            
            if results["structure_check"].get("issues"):
                all_issues.extend(results["structure_check"]["issues"])
            if results["structure_check"].get("warnings"):
                all_warnings.extend(results["structure_check"]["warnings"])
            
            if check_text and results["text_check"].get("issues"):
                all_issues.extend(results["text_check"]["issues"])
            
            if check_layout and results["layout_check"].get("issues"):
                all_issues.extend(results["layout_check"]["issues"])
            if check_layout and results["layout_check"].get("warnings"):
                all_warnings.extend(results["layout_check"]["warnings"])
            
            # Build report
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("PDF QUALITY CHECK REPORT")
            report_lines.append("=" * 80)
            report_lines.append(f"\n📄 PDF: {pdf_file}")
            
            # Structure
            struct = results["structure_check"]
            report_lines.append(f"\n📊 STRUCTURE CHECK:")
            if struct.get("valid"):
                report_lines.append("  ✅ PDF structure is valid")
            else:
                report_lines.append("  ❌ PDF structure issues detected")
            
            if struct.get("file_size"):
                report_lines.append(f"  📏 File size: {struct['file_size']:,} bytes")
            
            if struct.get("page_count"):
                report_lines.append(f"  📑 Pages: {struct['page_count']}")
            
            if struct.get("issues"):
                for issue in struct["issues"]:
                    report_lines.append(f"  ⚠️  {issue}")
            
            if struct.get("warnings"):
                for warning in struct["warnings"]:
                    report_lines.append(f"  ℹ️  {warning}")
            
            # Text extraction
            if check_text:
                text = results["text_check"]
                report_lines.append(f"\n📝 TEXT EXTRACTION:")
                if text.get("success"):
                    report_lines.append("  ✅ Text extraction successful")
                    report_lines.append(f"  📏 Extracted text length: {text['text_length']:,} characters")
                    
                    if text.get("has_content"):
                        report_lines.append("  ✅ Content appears readable")
                    else:
                        report_lines.append("  ⚠️  Very little content extracted")
                    
                    if text.get("sections_found"):
                        report_lines.append(f"  📋 Sections found: {', '.join(text['sections_found'])}")
                else:
                    report_lines.append("  ❌ Text extraction failed")
                
                if text.get("issues"):
                    for issue in text["issues"]:
                        report_lines.append(f"  ⚠️  {issue}")
            
            # Layout
            if check_layout:
                layout = results["layout_check"]
                report_lines.append(f"\n🎨 LAYOUT CHECK:")
                if layout.get("issues"):
                    for issue in layout["issues"]:
                        report_lines.append(f"  ⚠️  {issue}")
                if layout.get("warnings"):
                    for warning in layout["warnings"]:
                        report_lines.append(f"  ℹ️  {warning}")
                
                if not layout.get("issues") and not layout.get("warnings"):
                    report_lines.append("  ✅ No major layout issues detected")
            
            # Summary
            report_lines.append(f"\n{'=' * 80}")
            report_lines.append("SUMMARY")
            report_lines.append("=" * 80)
            
            if all_issues:
                report_lines.append(f"❌ CRITICAL ISSUES ({len(all_issues)}):")
                for issue in all_issues:
                    report_lines.append(f"  • {issue}")
                overall_status = "❌ FAILED - Critical issues found"
            elif all_warnings:
                report_lines.append(f"⚠️  WARNINGS ({len(all_warnings)}):")
                for warning in all_warnings:
                    report_lines.append(f"  • {warning}")
                overall_status = "⚠️  WARNINGS - Review recommended"
            else:
                overall_status = "✅ PASSED - PDF looks good!"
                report_lines.append("✅ No issues detected - PDF quality is good!")
            
            report_lines.append(f"\n{overall_status}")
            report_lines.append("=" * 80)
            
            logger.info(f"PDF quality check completed: {overall_status}")
            return "\n".join(report_lines)
        
        except Exception as e:
            error_msg = f"[error] Failed to check PDF quality: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

