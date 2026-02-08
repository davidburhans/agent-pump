"""Ollama configuration model."""

from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """Configuration for Ollama backend."""

    endpoint: str = Field(
        default="http://localhost:11434",
        description="Ollama API endpoint URL",
    )
    model: str = Field(
        default="llama3",
        description="Model name to use (e.g., llama3, mistral)",
    )
