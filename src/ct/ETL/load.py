import time
from pymongo import MongoClient
from langchain.schema import Document
from ct.ETL.transform import Transform  
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from ct.config import PRODUCTS_VECTOR_PATH, SALES_PRODUCTS_VECTOR_PATH
from ct.clients import openai_api_key as api_key, mongo_uri, mongo_db, mongo_collection_products, mongo_collection_sales


class Load:
    def __init__(self):
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)

        self.client = MongoClient("mongodb://localhost:27017")
        self.db = self.client[mongo_db]
        self.products_collection = self.db[mongo_collection_products]
        self.sales_collection = self.db[mongo_collection_sales]

    def build_content(self, product : dict, product_features : list):
        return ". ".join(
            f"{product_feature.capitalize()}: {product.get(product_feature, 'No disponible')}" 
            for product_feature in product_features 
            if product.get(product_feature))
 
    def mongo_products(self):
        products = self.clean_data.clean_products()
        for product in products:
            clave = product.get("clave")
            if clave:
                self.products_collection.update_one(
                    {"clave": clave},           # filtro: busca por clave
                    {"$set": product},          # operación: actualiza todo el documento con los nuevos valores
                    upsert=True                 # si no existe, lo inserta
                )


    def mongo_sales(self):
        sales = self.clean_data.clean_sales()
        for sale in sales:
            clave = sale.get("clave")
            if clave:
                self.sales_collection.update_one(
                    {"clave": clave},
                    {"$set": sale},
                    upsert=True
                )

    def load_products(self):
        products = self.products_collection.find()
        
        product = products[0]  
        product_features = [column for column in product.keys() if column != "_id"]

        docs = [
            Document(
                page_content=self.build_content(product, product_features),
                metadata = {"_id": str(product["_id"])}
            )
            for product in products 
        ]
        return docs

    def load_sales(self):
        sales = self.sales_collection.find()
        
        sale = sales[0]
        sales_features = [column for column in sale.keys() if column != "_id"]
        docs = [
            Document(
                page_content=self.build_content(sale, sales_features),
                metadata = {"_id": str(sale["_id"])}
            )
            for sale in sales
        ]
        return docs
    
    def vector_store(self, docs: Document) -> FAISS:
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def products_vs(self):
        products = self.load_products()

        # --- Batch size ---
        batch_size = 250
        # Create the vector store
        total_docs = len(products)
        
        vector_store = self.vector_store(products[:batch_size])  
        for i in range(1, total_docs, batch_size):
            batch = products[i:i + batch_size]
            vector_store.add_documents(batch)
            print(f"Processed {i + batch_size} of {total_docs} documents.")
    
        vector_store.save_local(str(PRODUCTS_VECTOR_PATH))
        print("Vector store created and saved to disk.")

    def sales_products_vs(self):
        sales = self.load_sales()

        # --- Batch size ---
        batch_size = 200
        # Create the vector store
        total_docs = len(sales)
        vector_store = FAISS.load_local(folder_path=str(PRODUCTS_VECTOR_PATH), 
                                          embeddings=self.embeddings, allow_dangerous_deserialization=True)
        vector_store.add_documents(sales[:batch_size])
        for i in range(1, total_docs, batch_size):
            batch = sales[i:i + batch_size]
            vector_store.add_documents(batch)
            print(f"Processed {i + batch_size} of {total_docs} documents.")
        
        vector_store.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        print("Sales vector store created and saved to disk.")
        
    
    