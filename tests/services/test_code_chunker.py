from agent_pump.utils.code_chunker import CodeChunker


def test_chunk_python_content():
    content = """
import os

class MyClass:
    def method_one(self):
        print("one")

    def method_two(self):
        print("two")

def global_function():
    return True
"""
    chunks = CodeChunker.chunk_content(content, "test.py")

    # Expecting: imports/global, MyClass (or its methods), global_function
    # The chunker logic will determine exact output, but let's assume
    # we chunk by top-level definitions for now.

    assert len(chunks) >= 3
    assert any("class MyClass" in c for c in chunks)
    assert any("def global_function" in c for c in chunks)


def test_chunk_markdown_content():
    content = """# Title

## Section 1
Content 1.

## Section 2
Content 2.
"""
    chunks = CodeChunker.chunk_content(content, "readme.md")

    assert len(chunks) >= 2
    assert any("## Section 1" in c for c in chunks)
    assert any("## Section 2" in c for c in chunks)


def test_chunk_small_file():
    content = "print('hello')"
    chunks = CodeChunker.chunk_content(content, "script.py")
    assert len(chunks) == 1
    assert chunks[0] == content
