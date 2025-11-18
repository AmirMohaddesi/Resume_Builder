"""
Tool to check if LaTeX packages are available in the system.
"""
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, ClassVar
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class LaTeXPackageCheckerInput(BaseModel):
    """Input for LaTeX package checker."""
    tex_file_path: str = Field(..., description="Path to the .tex file to check")


class LaTeXPackageCheckerTool(BaseTool):
    """
    Tool to detect LaTeX packages used in a .tex file and check if they're installed.
    Raises warnings for missing packages that could cause compilation failures.
    """
    name: str = "latex_package_checker"
    description: str = (
        "Checks a LaTeX file for \\usepackage commands and verifies if those packages "
        "are installed in the system. Returns a report of missing packages."
    )
    args_schema: type[BaseModel] = LaTeXPackageCheckerInput

    # Common packages that are typically included in standard LaTeX distributions
    COMMON_PACKAGES: ClassVar[set] = {
        'inputenc', 'fontenc', 'geometry', 'graphicx', 'hyperref', 'color', 'xcolor',
        'amsmath', 'amssymb', 'amsfonts', 'latexsym', 'babel', 'csquotes', 'fancyhdr',
        'setspace', 'multirow', 'multicol', 'array', 'booktabs', 'longtable',
        'caption', 'subcaption', 'float', 'wrapfig', 'enumerate', 'enumitem',
        'textcomp', 'lmodern', 'mathptmx', 'helvet', 'courier', 'times', 'palatino',
        'url', 'titlesec', 'titletoc', 'parskip', 'indentfirst', 'ragged2e'
    }

    # Packages that often cause issues if missing
    SPECIALTY_PACKAGES: ClassVar[dict] = {
        'fontawesome5': 'Font Awesome icons (version 5)',
        'fontawesome': 'Font Awesome icons',
        'moderncv': 'ModernCV resume class',
        'tikz': 'TikZ graphics',
        'pgfplots': 'PGF plots',
        'biblatex': 'Bibliography management',
        'natbib': 'Natural sciences bibliography',
        'algorithm': 'Algorithm typesetting',
        'algorithmic': 'Algorithm typesetting',
        'listings': 'Source code listings',
        'minted': 'Syntax highlighting',
        'beamer': 'Presentation class',
        'memoir': 'Memoir document class',
        'koma-script': 'KOMA-Script classes'
    }

    def _extract_packages(self, tex_content: str) -> tuple[List[str], List[str]]:
        """Extract all packages and document classes from LaTeX content.
        
        Returns:
            Tuple of (packages list, document_classes list)
        """
        packages = []
        
        # Match \usepackage{package} or \usepackage[options]{package}
        # Also match \usepackage{pkg1,pkg2,pkg3} for multiple packages
        pattern = r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}'
        
        matches = re.findall(pattern, tex_content)
        for match in matches:
            # Handle comma-separated packages
            pkgs = [p.strip() for p in match.split(',')]
            packages.extend(pkgs)
        
        # Also check for document class
        class_pattern = r'\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}'
        class_matches = re.findall(class_pattern, tex_content)
        
        return packages, class_matches

    def _check_package_installed(self, package_name: str) -> bool:
        """
        Check if a LaTeX package is installed using kpsewhich.
        Returns True if package is found, False otherwise.
        """
        try:
            # Try to find the package's .sty file
            result = subprocess.run(
                ['kpsewhich', f'{package_name}.sty'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() != ''
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # kpsewhich not available or timeout - assume package exists (fail-safe)
            return True

    def _check_documentclass_installed(self, class_name: str) -> bool:
        """Check if a document class is installed."""
        try:
            result = subprocess.run(
                ['kpsewhich', f'{class_name}.cls'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() != ''
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    def _run(self, tex_file_path: str) -> str:
        """
        Check LaTeX file for missing packages.
        
        Args:
            tex_file_path: Path to the .tex file
            
        Returns:
            JSON string with package check results
        """
        tex_path = Path(tex_file_path)
        
        if not tex_path.exists():
            return f'{{"error": "LaTeX file not found: {tex_file_path}"}}'
        
        try:
            tex_content = tex_path.read_text(encoding='utf-8')
        except Exception as e:
            return f'{{"error": "Failed to read LaTeX file: {str(e)}"}}'
        
        # Extract packages and document class
        packages, doc_classes = self._extract_packages(tex_content)
        
        if not packages and not doc_classes:
            return '{"status": "success", "message": "No packages found to check", "missing_packages": []}'
        
        # Check each package
        missing_packages = []
        specialty_missing = []
        
        for pkg in packages:
            if pkg in self.COMMON_PACKAGES:
                # Skip common packages - assume they exist
                continue
            
            if not self._check_package_installed(pkg):
                pkg_info = {
                    "package": pkg,
                    "description": self.SPECIALTY_PACKAGES.get(pkg, "Unknown package")
                }
                missing_packages.append(pkg_info)
                
                if pkg in self.SPECIALTY_PACKAGES:
                    specialty_missing.append(pkg)
        
        # Check document classes
        missing_classes = []
        for doc_class in doc_classes:
            if not self._check_documentclass_installed(doc_class):
                missing_classes.append(doc_class)
        
        # Build report
        if missing_packages or missing_classes:
            report = {
                "status": "warning",
                "message": f"Found {len(missing_packages)} missing packages and {len(missing_classes)} missing document classes",
                "missing_packages": missing_packages,
                "missing_classes": missing_classes,
                "recommendation": self._generate_recommendation(missing_packages, missing_classes)
            }
        else:
            report = {
                "status": "success",
                "message": "All packages appear to be installed",
                "missing_packages": [],
                "missing_classes": []
            }
        
        import json
        return json.dumps(report, indent=2)

    def _generate_recommendation(self, missing_packages: List[Dict], missing_classes: List[str]) -> str:
        """Generate concise installation recommendations."""
        recommendations = []
        
        if missing_classes:
            recommendations.append(f"Install document classes: {', '.join(missing_classes)}")
        
        if missing_packages:
            pkg_names = [p['package'] for p in missing_packages]
            
            # Common resume packages
            if 'moderncv' in pkg_names:
                recommendations.append("tlmgr install moderncv")
            
            if any('fontawesome' in p for p in pkg_names):
                recommendations.append("tlmgr install fontawesome5")
            
            # General install command for multiple packages
            if len(pkg_names) > 2:
                recommendations.append(f"tlmgr install {' '.join(pkg_names)}")
            elif len(pkg_names) == 1:
                recommendations.append(f"tlmgr install {pkg_names[0]}")
        
        return " | ".join(recommendations) if recommendations else "Use default template if issues persist."

