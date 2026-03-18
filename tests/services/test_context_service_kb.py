from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.models.workspace import KnowledgeBaseConfig, ProjectConfig
from agent_pump.services.context_service import ContextService


@pytest.fixture
def mock_project_path(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "index.md").write_text("# Doc\nContent", encoding="utf-8")

    s = tmp_path / "src"
    s.mkdir()
    (s / "main.py").write_text("print('hello')", encoding="utf-8")
    return tmp_path


@pytest.fixture
def project_config(mock_project_path):
    return ProjectConfig(
        path=mock_project_path,
        name="test_proj",
        knowledge_base=KnowledgeBaseConfig(
            enabled=True, docs_dirs=["docs"], external_resources=["http://example.com"]
        ),
    )


@pytest.mark.asyncio
async def test_index_project_with_kb(mock_project_path, project_config):
    with (
        patch("agent_pump.services.context_service.VectorStore") as MockVectorStore,
        patch("agent_pump.services.context_service.EmbeddingsService") as MockEmbeddings,
        patch("httpx.AsyncClient") as MockClient,
    ):
        # Mock embeddings
        mock_embeddings_instance = MockEmbeddings.return_value
        mock_embeddings_instance.generate_embeddings.return_value = [0.1, 0.2]

        # Mock vector store
        # Since VectorStore is instantiated twice (in __init__ and index_project),
        # return_value returns the SAME mock instance by default unless side_effect is used.
        # But we verify calls on that instance, so it's fine as long as we clear it or distinguish.
        # Here we just check if methods were called.

        mock_store_instance = MockVectorStore.return_value
        mock_store_instance.chunks = []
        mock_store_instance.metadata = []
        mock_store_instance.embeddings = []
        mock_store_instance.save = MagicMock()
        mock_store_instance.add = MagicMock()
        mock_store_instance.search = MagicMock()

        # Mock httpx
        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><h1>External</h1><p>Content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client_instance.get.return_value = mock_response

        service = ContextService(mock_project_path, config=project_config)
        # Patch load_store to avoid file I/O
        service._load_store = MagicMock()

        await service.index_project()

        # Check adds
        adds = mock_store_instance.add.call_args_list
        assert len(adds) >= 3  # main.py, index.md, external

        files_indexed = []
        types_indexed = []

        for call in adds:
            meta = call.kwargs.get("metadata", {})
            f = str(meta.get("file")).replace("\\", "/")  # normalize
            files_indexed.append(f)
            types_indexed.append(meta.get("type"))

        assert "src/main.py" in files_indexed
        assert "docs/index.md" in files_indexed
        assert "http://example.com" in files_indexed

        # Check types
        main_idx = files_indexed.index("src/main.py")
        assert types_indexed[main_idx] == "code"

        doc_idx = files_indexed.index("docs/index.md")
        assert types_indexed[doc_idx] == "docs"

        ext_idx = files_indexed.index("http://example.com")
        assert types_indexed[ext_idx] == "external_doc"


@pytest.mark.asyncio
async def test_get_relevant_context_formatting(mock_project_path, project_config):
    with (
        patch("agent_pump.services.context_service.VectorStore") as MockVectorStore,
        patch("agent_pump.services.context_service.EmbeddingsService") as MockEmbeddings,
    ):
        mock_embeddings_instance = MockEmbeddings.return_value
        mock_embeddings_instance.generate_embeddings.return_value = [0.1, 0.2]

        mock_store_instance = MockVectorStore.return_value

        # Setup search results
        mock_result1 = MagicMock()
        mock_result1.metadata = {"file": "docs/index.md", "type": "docs"}
        mock_result1.score = 0.9
        mock_result1.content = "Doc content"

        mock_result2 = MagicMock()
        mock_result2.metadata = {"file": "http://example.com", "type": "external_doc"}
        mock_result2.score = 0.8
        mock_result2.content = "External content"

        mock_store_instance.search.return_value = [mock_result1, mock_result2]

        service = ContextService(mock_project_path, config=project_config)
        service._load_store = MagicMock()

        context = await service.get_relevant_context("query")

        assert len(context) == 2
        assert "Documentation: docs/index.md" in context[0]
        assert "External Resource: http://example.com" in context[1]
