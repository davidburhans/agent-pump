from agent_pump.integrations.auto_fix import AutoFixService
from agent_pump.integrations.failure_parser import FailureInfo
from agent_pump.models.project import Project


def test_create_fix_task(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / "ROADMAP.md").write_text("", encoding="utf-8")

    project = Project(path=project_path, name="Test")
    service = AutoFixService()

    failure_info = FailureInfo(
        errors=[{"type": "python_error", "details": "Error: foo"}],
        raw_log="some log",
        suggested_fix="Fix foo",
        run_id=123,
    )

    service.create_fix_task(project, failure_info, 123, 0)

    # Check Roadmap
    roadmap_path = project_path / "ROADMAP.md"
    content = roadmap_path.read_text(encoding="utf-8")

    assert "Fix CI Failure: Fix foo" in content
    assert "**Errors Found:**" in content
    assert "- **python_error**: `Error: foo`" in content
