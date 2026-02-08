"""Tests for coverage parser."""

from agent_pump.utils.coverage_parser import CoverageParser


def test_parse_pytest_cov():
    output = """
    Name                      Stmts   Miss  Cover
    ---------------------------------------------
    src/agent_pump/__init__.py      0      0   100%
    src/agent_pump/app.py          50     10    80%
    ---------------------------------------------
    TOTAL                        50     10    80%
    """
    report = CoverageParser.parse_text(output)
    assert report is not None
    assert report.total_coverage == 80.0


def test_parse_generic_coverage_colon():
    output = "Coverage: 85.50%"
    report = CoverageParser.parse_text(output)
    assert report is not None
    assert report.total_coverage == 85.5


def test_parse_go_test():
    output = "coverage: 42.5% of statements"
    report = CoverageParser.parse_text(output)
    assert report is not None
    assert report.total_coverage == 42.5


def test_parse_jest_table():
    output = """
    -------------------|---------|----------|---------|---------|-------------------
    File               | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
    -------------------|---------|----------|---------|---------|-------------------
    All files          |   85.5  |    100   |    100  |   85.5  |
    -------------------|---------|----------|---------|---------|-------------------
    """
    report = CoverageParser.parse_text(output)
    assert report is not None
    assert report.total_coverage == 85.5


def test_parse_no_match():
    output = "Some random output"
    report = CoverageParser.parse_text(output)
    assert report is None
