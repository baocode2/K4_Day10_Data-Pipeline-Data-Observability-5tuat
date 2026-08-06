from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings


class GeminiEmbeddings(Embeddings):
    """LangChain adapter for Gemini embeddings used by Chroma and Ragas."""

    def __init__(self, model_name: str, google_api_key: str | None):
        if not google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is required to use Gemini embeddings.")
        self.model = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=google_api_key,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.model.embed_query(text)
