from abc import ABC, abstractmethod
from ct.types import Text, Chunks
from typing import Dict, List, Optional, Any
from langchain.schema import Document

class DocCollection(ABC):
    @abstractmethod
    def get_chunks(self, t : Text) -> Chunks:
        pass
    
    @abstractmethod
    def load_pdf(self, pdf_path: str) -> Text:
        pass

    @abstractmethod
    def load_docs(self, docs: List[dict]) -> list:
        pass

