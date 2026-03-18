from pathlib import Path

from agent_pump.models.workspace import KnowledgeBaseConfig, ProjectConfig


def test_knowledge_base_defaults():
    kb = KnowledgeBaseConfig()
    assert kb.enabled is True
    assert kb.docs_dirs == ["docs"]
    assert kb.external_resources == []
    assert ".md" in kb.file_extensions


def test_project_config_with_kb():
    config = ProjectConfig(path=Path("/tmp/test"), name="test")
    assert config.knowledge_base.enabled is True

    config = ProjectConfig(
        path=Path("/tmp/test"), name="test", knowledge_base=KnowledgeBaseConfig(enabled=False)
    )
    assert config.knowledge_base.enabled is False
