import pytest
from pydantic import ValidationError
from pathlib import Path
from agent_pump.models.validation import ProjectPathInput, IdeaInput, PromptCustomizationInput

def test_project_path_input_valid(tmp_path):
    """Test valid project path."""
    # tmp_path is a directory that exists
    model = ProjectPathInput(path=str(tmp_path))
    assert model.path == str(tmp_path.resolve())

def test_project_path_input_non_existent():
    """Test path that does not exist."""
    with pytest.raises(ValidationError) as excinfo:
        # Use a path unlikely to exist on any system
        path = Path("/path/that/does/not/exist/at/all/hopefully/12345")
        ProjectPathInput(path=str(path))
    assert "Path does not exist" in str(excinfo.value)

def test_project_path_input_not_a_dir(tmp_path):
    """Test path that is a file, not a directory."""
    file_path = tmp_path / "test_file.txt"
    file_path.touch()
    with pytest.raises(ValidationError) as excinfo:
        ProjectPathInput(path=str(file_path))
    assert "Path is not a directory" in str(excinfo.value)

def test_project_path_input_empty():
    """Test empty path."""
    with pytest.raises(ValidationError) as excinfo:
        ProjectPathInput(path="")
    assert "Path cannot be empty" in str(excinfo.value)

def test_idea_input_valid():
    """Test valid idea."""
    model = IdeaInput(idea="Build a rocket ship")
    assert model.idea == "Build a rocket ship"

def test_idea_input_too_short():
    """Test idea too short."""
    with pytest.raises(ValidationError) as excinfo:
        IdeaInput(idea="tiny")
    assert "String should have at least 5 characters" in str(excinfo.value)

def test_idea_input_too_long():
    """Test idea too long."""
    long_idea = "a" * 501
    with pytest.raises(ValidationError) as excinfo:
        IdeaInput(idea=long_idea)
    assert "String should have at most 500 characters" in str(excinfo.value)

def test_prompt_template_valid():
    """Test valid prompt template."""
    model = PromptCustomizationInput(template="Hello {name}")
    assert model.template == "Hello {name}"

def test_prompt_template_invalid_format():
    """Test invalid brace matching."""
    with pytest.raises(ValidationError) as excinfo:
        PromptCustomizationInput(template="Hello {name")
    assert "Invalid template format" in str(excinfo.value)

def test_prompt_template_empty():
    """Test empty prompt template."""
    with pytest.raises(ValidationError) as excinfo:
        PromptCustomizationInput(template="   ")
    assert "Template cannot be empty" in str(excinfo.value)
