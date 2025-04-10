import os
from langchain_community.vectorstores import FAISS


class VectorStore:
    def __init__(self, VECTOR_DB_PATH, embedding_model):
        """Carga la base de datos vectorial con el modelo de embeddings correcto."""
        self.VECTOR_DB_PATH = VECTOR_DB_PATH
        self.embedding_model = embedding_model

    def load_retriever(self):
        """Carga FAISS si existe, sino lanza error."""
        if os.path.exists(self.VECTOR_DB_PATH):
            return FAISS.load_local(self.VECTOR_DB_PATH, self.embedding_model, allow_dangerous_deserialization=True)
        else:
            raise FileNotFoundError(f"No se encontró la base de datos en {self.VECTOR_DB_PATH}")

    def asRetriever(self, search_kwargs=None):
        """Carga la base de datos vectorial con parámetros seguros por defecto."""
        vdb = self.load_retriever()
        safe_kwargs = {
            "k": 8,  # Solo 8 documentos máximo
            "score_threshold": 0.65,  # Filtro por relevancia
            **(search_kwargs or {})  # Permite sobreescribir desde el llamador
        }
        return vdb.as_retriever(search_kwargs=safe_kwargs)
