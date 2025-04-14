import os
from langchain_community.vectorstores import FAISS
from ct.tools.vectorstore import VectorStore
from ct.langchain.embedder import LangchainEmbedder

class LangchainVectorStore(VectorStore):
    def __init__(self, embedder, index_path: str = None):
        self.embedder = embedder
        self.index_path = index_path
        self.vectorstore = None
        
        if index_path and os.path.exists(index_path):
            self._load_index() 
    
    def _load_index(self):
        """Carga el índice existente"""
        self.vectorstore = FAISS.load_local(
            folder_path=self.index_path,
            embeddings=self.embedder, 
            allow_dangerous_deserialization=True
        )
        safe_kwargs = {
            "k": 8,  
            "score_threshold": 0.8  
        }
        self.retriever = self.vectorstore.as_retriever(search_kwargs=safe_kwargs)
    
    def create_index(self, texts):
        """Crea un nuevo índice"""
        self.vectorstore = FAISS.from_documents(
            documents=texts,
            embedding=self.embedder  
        )
        if self.index_path:
            self.vectorstore.save_local(self.index_path)
        safe_kwargs = {
            "k": 8,  
            "score_threshold": 0.8  
        }
        self.retriever = self.vectorstore.as_retriever(search_kwargs=safe_kwargs)