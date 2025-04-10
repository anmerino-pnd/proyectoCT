from langchain.schema import Document
from ct.ETL.transform import Transform  
from langchain_openai import OpenAIEmbeddings
from ct.clients import openai_api_key as api_key
from langchain_community.vectorstores import FAISS

class Load:
    def __init__(self):
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)

    def build_content(self, product : dict, product_features : list):
        return ". ".join(f"{product_feature.capitalize()}: {product.get(product_feature, 'No disponible')}" for product_feature in product_features if product.get(product_feature))
 
    def load_products(self):
        products = self.clean_data.clean_products()  # Ahora sabemos que es una lista
        excluded_columns = ['idProductos']
        
        product = products[0]  # Tomamos el primer elemento directamente
        product_features = [column for column in product.keys() if column not in excluded_columns]

        docs = [
            Document(
                page_content=self.build_content(product, product_features),
                metadata={'idProductos': product['idProductos']}
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
                page_content=self.build_content(sale, sales_features),
                metadata={"Producto": sale["producto"]}
            )
            for sale in sales
        ]
        return docs
    
    def vector_store(self, docs: Document) -> FAISS:
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def load(self):
        # Load products and sales data into the vector store
        product_docs = self.load_products()
        sales_docs = self.load_sales()
        
        # Combine 
        all_docs = product_docs + sales_docs

        # Create the vector store
        vector_store = self.vector_store(all_docs)
        # Save the vector store to disk
        vector_store.save_local("faiss_vector_store")
        return print("Vector store created and saved to disk.")
    
    