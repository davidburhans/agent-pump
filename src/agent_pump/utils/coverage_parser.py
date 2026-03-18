"""Coverage output parser."""

import re
from datetime import datetime

from agent_pump.models.coverage import CoverageReportModel


class CoverageParser:
    """Parser for various coverage report formats."""

    @staticmethod
    def parse_text(output: str) -> CoverageReportModel | None:
        """
        Parse text output (stdout) to extract total coverage percentage.
        Supports common formats like:
        - pytest-cov: "TOTAL ... 85%"
        - cargo-tarpaulin: "Coverage: 85.00%" or "85.00% coverage"
        - go test: "coverage: 85.0% of statements"
        - Jest: "All files ... 85" (in table)
        """
        if not output:
            return None

        # Try to find TOTAL line first (common in Python/Jest tables)
        # Regex for "TOTAL" followed by anything then percentage at end of line
        # e.g. "TOTAL 100 20 80%"
        # Allow leading whitespace for indentation robustness
        total_match = re.search(r"^\s*TOTAL\s+.*\s+(\d+(?:\.\d+)?)\%\s*$", output, re.MULTILINE)
        if total_match:
            try:
                return CoverageReportModel(
                    total_coverage=float(total_match.group(1)),
                    raw_output=output,
                    timestamp=datetime.now(),
                )
            except ValueError:
                pass

        # Regex for "Coverage: XX%" (Tarpaulin/Generic)
        coverage_match = re.search(r"Coverage:\s*(\d+(?:\.\d+)?)\%", output, re.IGNORECASE)
        if coverage_match:
            try:
                return CoverageReportModel(
                    total_coverage=float(coverage_match.group(1)),
                    raw_output=output,
                    timestamp=datetime.now(),
                )
            except ValueError:
                pass

        # Regex for Go "coverage: XX.X% of statements"
        go_match = re.search(r"coverage:\s*(\d+(?:\.\d+)?)\%\s+of\s+statements", output)
        if go_match:
            try:
                return CoverageReportModel(
                    total_coverage=float(go_match.group(1)),
                    raw_output=output,
                    timestamp=datetime.now(),
                )
            except ValueError:
                pass

        # Regex for Jest/Istanbul table "All files ... | 85 | ..."
        # Usually: "All files | 85 | ..."
        # Allow leading whitespace
        jest_match = re.search(r"^\s*All files\s*\|\s*(\d+(?:\.\d+)?)\s*\|", output, re.MULTILINE)
        if jest_match:
            try:
                return CoverageReportModel(
                    total_coverage=float(jest_match.group(1)),
                    raw_output=output,
                    timestamp=datetime.now(),
                )
            except ValueError:
                pass

        return None
