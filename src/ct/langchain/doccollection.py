import pandas as pd
from ct.tools.doccollection import DocCollection
from langchain.schema import Document
from typing import List

class DisjointCollection(DocCollection):
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def get_chunks(self, t: str) -> List[str]:
        return [t[i:i + self.chunk_size] for i in range(0, len(t), self.chunk_size)]

    def load_pdf(self, pdf_path: str) -> str:
        # Implement PDF loading logic here
        pass
    
    def build_content(self, product : dict, product_features : list):
        return ". ".join(f"{product_feature.capitalize()}: {product.get(product_feature, 'No disponible')}" for product_feature in product_features if product.get(product_feature))
 

    def load_docs(self, data: pd.DataFrame) -> List[Document]:
        if data.empty:
            return []

        features = data.columns.tolist()
        str_data = data.astype(str)
        
        documents = [
            Document(
                page_content=self.build_content(row.to_dict(), features),
                metadata={
                    "row_index": idx 
                }
            )
            for idx, row in str_data.iterrows()  
        ]
        
        return documents