"""Tests for the ``sensai.embedder`` module."""

import pytest

from sensai.client import OllamaClient
from sensai.embedder import DEFAULT_EMBEDDING_MODEL, Embedder


class MockClient(OllamaClient):
    """Ollama client recording embed requests and answering one fake vector per input."""

    def __init__(self) -> None:
        """Initialize MockClient with no request sent yet."""
        super().__init__(base_url="http://localhost:11434/api/chat", token="token", timeout=1.0)  # noqa: S106
        self.requests: list[tuple[list[str], str]] = []

    async def embed(self, inputs: list[str], model: str) -> list[list[float]]:
        self.requests.append((inputs, model))
        return [[float(i)] for i in range(len(inputs))]


@pytest.mark.asyncio
async def test_embed_query_prefixes_the_query_for_nomic() -> None:
    client = MockClient()

    embedding = await Embedder(client).embed_query("hello")

    assert embedding == [0.0]
    assert client.requests == [(["search_query: hello"], DEFAULT_EMBEDDING_MODEL)]


@pytest.mark.asyncio
async def test_embed_documents_batches_prefixed_texts_in_one_request() -> None:
    client = MockClient()

    embeddings = await Embedder(client, "nomic-embed-text:latest").embed_documents(["a", "b"])

    assert embeddings == [[0.0], [1.0]]
    assert client.requests == [
        (["search_document: a", "search_document: b"], "nomic-embed-text:latest")
    ]


@pytest.mark.asyncio
async def test_embedder_does_not_prefix_for_other_models() -> None:
    client = MockClient()
    embedder = Embedder(client, "bge-m3")

    await embedder.embed_query("hello")
    await embedder.embed_documents(["a"])

    assert client.requests == [(["hello"], "bge-m3"), (["a"], "bge-m3")]


@pytest.mark.asyncio
async def test_embed_documents_without_texts_sends_nothing() -> None:
    client = MockClient()

    assert await Embedder(client).embed_documents([]) == []
    assert client.requests == []
