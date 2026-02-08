import tempfile
from pathlib import Path

import numpy as np
import pytest

from agent_pump.services.vector_store import VectorStore


@pytest.fixture
def temp_store_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "store.npz"


def test_add_and_search():
    store = VectorStore()

    # Simple 2D vectors
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]

    store.add("chunk1", v1, {"file": "file1.py"})
    store.add("chunk2", v2, {"file": "file2.py"})

    # Search for v1 (closest to v1)
    results = store.search([1.0, 0.0], k=1)
    assert len(results) == 1
    assert results[0].content == "chunk1"
    assert results[0].score > 0.99  # Should be ~1.0

    # Search for v2
    results = store.search([0.0, 1.0], k=1)
    assert len(results) == 1
    assert results[0].content == "chunk2"


def test_save_and_load(temp_store_path):
    store = VectorStore()
    store.add("test", [0.5, 0.5], {"meta": "data"})

    store.save(temp_store_path)

    new_store = VectorStore()
    new_store.load(temp_store_path)

    assert len(new_store.embeddings) == 1
    assert new_store.chunks[0] == "test"
    assert new_store.metadata[0] == {"meta": "data"}
    # Using np.allclose for float comparison
    assert np.allclose(new_store.embeddings[0], [0.5, 0.5])


def test_search_empty():
    store = VectorStore()
    results = store.search([1.0, 1.0])
    assert results == []
