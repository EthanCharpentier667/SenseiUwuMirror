"""Embedder turning text into vectors for RAG, on top of the Ollama client."""

from sensai.client import OllamaClient

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

_EMBEDDING_PREFIXES: dict[str, tuple[str, str]] = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
}


class Embedder:
    """Embeds search queries and document pieces with a single Ollama embedding model.

    Queries and the documents they search must be embedded by the same model for their
    vectors to be comparable, so the model is fixed for the embedder's lifetime.
    """

    def __init__(self, client: OllamaClient, model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        """Initialize the embedder.

        Args:
            client (OllamaClient): The client sending the embedding requests.
            model (str, optional): Name of the Ollama embedding model to invoke. Its output
                size must match `chunk.EMBEDDING_DIMENSIONS` (768 for the default
                `nomic-embed-text`).
        """
        self.client = client
        self.model = model
        self._query_prefix, self._document_prefix = _EMBEDDING_PREFIXES.get(
            model.split(":", 1)[0], ("", "")
        )

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query, e.g. the user's question, to look up relevant chunks.

        Args:
            text (str): The query to embed.

        Returns:
            list[float]: The query's embedding vector.
        """
        embeddings = await self.client.embed([f"{self._query_prefix}{text}"], self.model)
        return embeddings[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed pieces of a document, e.g. its chunks, in a single request.

        Args:
            texts (list[str]): The pieces to embed.

        Returns:
            list[list[float]]: One embedding vector per piece, in the same order.
        """
        if not texts:
            return []
        return await self.client.embed(
            [f"{self._document_prefix}{text}" for text in texts], self.model
        )
