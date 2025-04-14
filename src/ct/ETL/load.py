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
    
    def products_vs(self):
        # Load products 
        products = self.load_products()
        # Create the vector store
        vector_store = self.vector_store(products)
        # Save the vector store to disk
        vector_store.save_local(str(PRODUCTS_VECTOR_PATH))
        print("Vector store created and saved to disk.")

    def sales_products_vs(self):
        # Load sales 
        sales = self.load_sales()
        # Create the vector store
        vector_store = self.vector_store(sales)
        # Read productos vector store
        vector_store2 = FAISS.load_local(str(PRODUCTS_VECTOR_PATH), self.embeddings, allow_dangerous_deserialization=True)
        # Merge the two vector stores
        vector_store.merge_from(vector_store2)
        # Save the merged vector store to disk
        vector_store.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        print("Merged vector store created and saved to disk.")
        
    
    