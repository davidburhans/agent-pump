from unittest.mock import MagicMock, patch

import pytest

from agent_pump.services.embeddings_service import EmbeddingsService


@pytest.fixture
def mock_sentence_transformer():
    with patch("agent_pump.services.embeddings_service.SentenceTransformer") as mock:
        yield mock


def test_lazy_loading(mock_sentence_transformer):
    service = EmbeddingsService(model_name="test-model")
    assert service._model is None

    # Accessing model should trigger load
    _ = service.model
    mock_sentence_transformer.assert_called_once_with("test-model")


def test_generate_embeddings(mock_sentence_transformer):
    service = EmbeddingsService()
    mock_model_instance = mock_sentence_transformer.return_value
    mock_model_instance.encode.return_value = [0.1, 0.2, 0.3]

    embedding = service.generate_embeddings("test text")

    mock_model_instance.encode.assert_called_once_with("test text", convert_to_numpy=True)
    assert embedding == [0.1, 0.2, 0.3]
