import time
from langchain.schema import Document
from ct.ETL.transform import Transform  
from langchain_openai import OpenAIEmbeddings
from ct.clients import openai_api_key as api_key
from langchain_community.vectorstores import FAISS
from ct.config import PRODUCTS_VECTOR_PATH, SALES_PRODUCTS_VECTOR_PATH

class Load:
    def __init__(self):
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)

    def build_content(self, product : dict, product_features : list):
        return ". ".join(f"{product_feature.capitalize()}: {product.get(product_feature, 'No disponible')}" for product_feature in product_features if product.get(product_feature))
 
    def load_products(self):
        products = self.clean_data.clean_products()  # Ahora sabemos que es una lista
        
        product = products[0]  # Tomamos el primer elemento directamente
        product_features = [column for column in product.keys()]

        docs = [
            Document(
                page_content=self.build_content(product, product_features)
            )
            for product in products  # Iteramos sobre la lista directamente
        ]
        return docs

    def load_sales(self):
        sales = self.clean_data.clean_sales()
        
        sale = sales[0]
        sales_features = [column for column in sale.keys()]
        docs = [
            Document(
                page_content=self.build_content(sale, sales_features)
            )
            for sale in sales
        ]
        return docs
    
    def vector_store(self, docs: Document) -> FAISS:
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def products_vs(self):
        # Load products 
        products = self.load_products()
        
        # --- Batch size ---
        batch_size = 250
        # Create the vector store
        total_docs = len(products)
        
        vector_store = self.vector_store(products[:batch_size])  # Initialize with the first batch
        for i in range(1, total_docs, batch_size):
            batch = products[i:i + batch_size]
            vector_store.add_documents(batch)
            time.sleep(5)  # Optional: sleep to avoid hitting API limits
            print(f"Processed {i + batch_size} of {total_docs} documents.")
    
        vector_store.save_local(str(PRODUCTS_VECTOR_PATH))
        print("Vector store created and saved to disk.")

    def sales_products_vs(self):
        sales = self.load_sales()

        # --- Batch size ---
        batch_size = 200
        # Create the vector store
        total_docs = len(sales)
        vector_store = self.vector_store(sales[:batch_size])  # Initialize with the first batch

        for i in range(1, total_docs, batch_size):
            batch = sales[i:i + batch_size]
            vector_store.add_documents(batch)
            time.sleep(5)
            print(f"Processed {i + batch_size} of {total_docs} documents.")

        vector_store.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        print("Merged vector store created and saved to disk.")
        
    
    