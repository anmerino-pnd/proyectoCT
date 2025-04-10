from abc import ABC, abstractmethod
from ct.types import Vector
from typing import Dict, List

class Embedder(ABC):
    @abstractmethod
    def embed_documents(self, s : list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        pass
