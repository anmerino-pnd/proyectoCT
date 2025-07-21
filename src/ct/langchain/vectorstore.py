import os
from langchain_community.vectorstores import FAISS

class LangchainVectorStore():
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

    
    def create_index(self, texts):
        """Crea un nuevo índice"""
        self.vectorstore = FAISS.from_documents(
            documents=texts,
            embedding=self.embedder  
        )
        if self.index_path:
            self.vectorstore.save_local(self.index_path)
        