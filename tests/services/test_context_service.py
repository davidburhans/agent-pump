from unittest.mock import MagicMock, patch

import pytest

from agent_pump.services.context_service import ContextService


@pytest.fixture
def mock_embeddings_service():
    with patch("agent_pump.services.context_service.EmbeddingsService") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vector_store_cls():
    # Patch the CLASS, return the Mock Class
    with patch("agent_pump.services.context_service.VectorStore") as mock:
        yield mock


@pytest.fixture
def mock_code_chunker():
    with patch("agent_pump.services.context_service.CodeChunker") as mock:
        yield mock


@pytest.fixture
def context_service(mock_embeddings_service, mock_vector_store_cls, mock_code_chunker, tmp_path):
    # The patch is active.
    # Constructor calls VectorStore() -> mock_vector_store_cls() -> instance
    service = ContextService(tmp_path)

    # We can inject mocks if needed, but VectorStore is already mocked via class patch
    service.embeddings_service = mock_embeddings_service
    # service.vector_store is already the mock instance
    service.code_chunker = mock_code_chunker

    return service


@pytest.mark.asyncio
async def test_index_project_walks_files(
    context_service, tmp_path, mock_code_chunker, mock_embeddings_service, mock_vector_store_cls
):
    # Setup dummy project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Readme")

    mock_code_chunker.chunk_content.side_effect = lambda content, name: [content]
    mock_embeddings_service.generate_embeddings.return_value = [0.1, 0.2]

    await context_service.index_project()

    # Check that chunking happened
    assert mock_code_chunker.chunk_content.call_count >= 2

    # Check that VectorStore instance was used
    # index_project creates a NEW instance: new_store = VectorStore()
    # Since we mocked the class, this returns a new return_value (or same if side_effect not set)
    # By default calling a mock returns the SAME child mock (return_value)

    instance = mock_vector_store_cls.return_value
    assert instance.add.call_count >= 2
    instance.save.assert_called_once()


@pytest.mark.asyncio
async def test_get_relevant_context(
    context_service, mock_embeddings_service, mock_vector_store_cls
):
    mock_embeddings_service.generate_embeddings.return_value = [0.5, 0.5]

    instance = mock_vector_store_cls.return_value

    # Mock search result
    mock_result = MagicMock()
    mock_result.content = "relevant code"
    mock_result.metadata = {"file": "file.py"}
    mock_result.score = 0.9

    instance.search.return_value = [mock_result]

    context = await context_service.get_relevant_context("query")

    instance.search.assert_called_once_with([0.5, 0.5], k=5)
    assert len(context) == 1
    assert "relevant code" in context[0]
    assert "file.py" in context[0]
