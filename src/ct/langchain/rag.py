from ct.langchain.vectorstore import LangchainVectorStore
from ct.langchain.embedder import LangchainEmbedder
from ct.langchain.assistant import LangchainAssistant
from ct.langgraph.assistant import LangGraphAssistant
from typing import Tuple, AsyncGenerator

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = LangchainEmbedder()  # Asegúrate que retorna un objeto Embeddings
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        
        # Verifica que el retriever se haya creado
        if not hasattr(self.vectorstore, 'retriever'):
            raise ValueError("VectorStore no se inicializó correctamente. ¿El índice existe?")
            
        self.assistant = LangchainAssistant(self.vectorstore.retriever)

    async def run(self, query: str, session_id: str = None, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Ejecuta una consulta RAG y muestra los chunks de respuesta en tiempo real."""
        if session_id is None:
            session_id = "default_session"

        async for chunk in self.assistant.answer(session_id, query, listaPrecio):
            yield chunk