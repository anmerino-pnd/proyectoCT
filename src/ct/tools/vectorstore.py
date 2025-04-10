from abc import ABC, abstractmethod
from ct.types import Text, Vector
from typing import List, Tuple

class VectorStore(ABC):
    @abstractmethod
    def create_index(self, texts: List[str]) -> None:
        """
        Create an index from the given texts.
        
        Args:
            texts (List[Text]): List of texts to index.
        """
        pass

