from agent_pump.integrations.failure_parser import FailureParser

def test_parse_python_error():
    logs = """
    some log content
    E       AssertionError: assert 1 == 2
    some other content
    """
    parser = FailureParser()
    info = parser.parse(logs)

    assert len(info.errors) == 1
    assert info.errors[0]["type"] == "python_error"
    # Note: Regex captures "AssertionError" and "assert 1 == 2", then joins with ": "
    assert info.errors[0]["details"] == "AssertionError: assert 1 == 2"

def test_parse_pytest_failure():
    logs = """
    FAILED tests/test_foo.py::test_bar
    """
    parser = FailureParser()
    info = parser.parse(logs)

    assert len(info.errors) == 1
    assert info.errors[0]["type"] == "pytest_failure"
    assert info.errors[0]["details"] == "tests/test_foo.py: test_bar"

def test_suggest_fix():
    parser = FailureParser()
    fix = parser._suggest_fix([{"type": "python_error", "details": "ModuleNotFound: No module named 'foo'"}])
    assert fix == "Install missing dependency"

def test_no_errors():
    logs = "Build succeeded"
    parser = FailureParser()
    info = parser.parse(logs)
    assert len(info.errors) == 0
    assert info.suggested_fix == "Investigate CI logs (no specific error pattern matched)"
