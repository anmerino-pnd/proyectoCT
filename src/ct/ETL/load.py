import time
from pymongo import MongoClient
from langchain.schema import Document
from ct.ETL.transform import Transform  # Asegúrate de que la ruta sea correcta
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from ct.config import PRODUCTS_VECTOR_PATH, SALES_PRODUCTS_VECTOR_PATH
# Importa la nueva colección de la configuración si la tienes, de lo contrario, defínela aquí
from ct.clients import openai_api_key as api_key, mongo_uri, mongo_db, mongo_collection_products, mongo_collection_sales, mongo_collection_specifications


class Load:
    def __init__(self):
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)

        self.client = MongoClient("mongodb://localhost:27017")
        self.db = self.client[mongo_db]
        self.products_collection = self.db[mongo_collection_products]
        self.sales_collection = self.db[mongo_collection_sales]
        self.specifications_collection = self.db[mongo_collection_specifications] # Nueva colección para fichas técnicas

    def build_content(self, product : dict, product_features : list):
        """
        Construye el contenido del documento para el embedding.
        """
        return ". ".join(
            f"{product_feature.capitalize()}: {product.get(product_feature, 'No disponible')}" 
            for product_feature in product_features 
            if product.get(product_feature))
 
    def mongo_products(self):
        """
        Carga y limpia los datos de productos y los guarda en MongoDB.
        """
        products = self.clean_data.clean_products()
        for product in products:
            clave = product.get("clave")
            if clave:
                self.products_collection.update_one(
                    {"clave": clave},           # filtro: busca por clave
                    {"$set": product},          # operación: actualiza todo el documento con los nuevos valores
                    upsert=True                 # si no existe, lo inserta
                )
        print("Productos cargados/actualizados en MongoDB.")

    def mongo_sales(self):
        """
        Carga y limpia los datos de ventas (ofertas) y los guarda en MongoDB.
        """
        sales = self.clean_data.clean_sales()
        for sale in sales:
            clave = sale.get("clave")
            if clave:
                self.sales_collection.update_one(
                    {"clave": clave},
                    {"$set": sale},
                    upsert=True
                )
        print("Ofertas cargadas/actualizadas en MongoDB.")

    def load_products(self):
        """
        Carga los productos de MongoDB y los convierte en objetos Document de Langchain.
        """
        products = list(self.products_collection.find()) # Convertir a lista para poder acceder por índice
        if not products:
            return []
        
        product_features = [column for column in products[0].keys() if column != "_id"]

        docs = [
            Document(
                page_content=self.build_content(product, product_features),
                metadata = {"_id": str(product["_id"]), "clave": product.get("clave")} # Añadir clave a metadata
            )
            for product in products 
        ]
        return docs

    def load_sales(self):
        """
        Carga las ventas (ofertas) de MongoDB y las convierte en objetos Document de Langchain.
        """
        sales = list(self.sales_collection.find()) # Convertir a lista para poder acceder por índice
        if not sales:
            return []
        
        sales_features = [column for column in sales[0].keys() if column != "_id"]
        docs = [
            Document(
                page_content=self.build_content(sale, sales_features),
                metadata = {"_id": str(sale["_id"]), "clave": sale.get("clave")} # Añadir clave a metadata
            )
            for sale in sales
        ]
        return docs
    
    def vector_store(self, docs: list[Document]) -> FAISS: # Se cambió el tipo de 'docs' a list[Document]
        """
        Crea un vector store de FAISS a partir de los documentos.
        """
        if not docs:
            print("Advertencia: No hay documentos para crear el vector store.")
            return None
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def products_vs(self):
        """
        Crea o actualiza el vector store para productos.
        """
        products = self.load_products()
        if not products:
            print("No hay productos para crear el vector store.")
            return

        batch_size = 250
        total_docs = len(products)
        
        # Inicializar el vector store con el primer lote
        vector_store = self.vector_store(products[:batch_size])
        if vector_store:
            for i in range(batch_size, total_docs, batch_size): # Empezar desde batch_size
                batch = products[i:i + batch_size]
                if batch: # Asegurarse de que el lote no esté vacío
                    vector_store.add_documents(batch)
                    print(f"Procesados {i + len(batch)} de {total_docs} documentos de productos.")
        
            vector_store.save_local(str(PRODUCTS_VECTOR_PATH))
            print("Vector store de productos creado y guardado en disco.")
        else:
            print("No se pudo crear el vector store de productos.")


    def sales_products_vs(self):
        """
        Crea o actualiza el vector store para ventas/ofertas.
        """
        sales = self.load_sales()
        if not sales:
            print("No hay ventas para crear el vector store.")
            return

        batch_size = 200
        total_docs = len(sales)
        
        # Cargar el vector store de productos existente para añadir las ventas
        try:
            vector_store = FAISS.load_local(folder_path=str(PRODUCTS_VECTOR_PATH), 
                                              embeddings=self.embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"Error al cargar el vector store de productos, se creará uno nuevo si es necesario: {e}")
            vector_store = self.vector_store(sales[:batch_size]) # Crear uno nuevo si falla la carga
            if not vector_store:
                print("No se pudo crear el vector store de ventas.")
                return

        vector_store.add_documents(sales[:min(batch_size, total_docs)]) # Añadir el primer lote de ventas
        for i in range(batch_size, total_docs, batch_size): # Empezar desde batch_size
            batch = sales[i:i + batch_size]
            if batch: # Asegurarse de que el lote no esté vacío
                vector_store.add_documents(batch)
                print(f"Procesados {i + len(batch)} de {total_docs} documentos de ventas.")
        
        vector_store.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        print("Vector store de ventas creado y guardado en disco.")
