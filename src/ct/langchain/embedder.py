from ct.clients import openai_api_key
from ct.tools.embedder import Embedder  
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings


class LangchainEmbedder(Embedder, Embeddings):  
    def __init__(self):
        self.embedder = OpenAIEmbeddings(
            openai_api_key=openai_api_key
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de documentos."""
        return self.embedder.embed_documents(texts)
    
    def embed_query(self, text: str) -> list[float]:
        """Genera un embedding para una consulta."""
        return self.embedder.embed_query(text)