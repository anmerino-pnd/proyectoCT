from pymongo import MongoClient, UpdateOne
from langchain.schema import Document
from ct.ETL.transform import Transform
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from ct.settings.config import PRODUCTS_VECTOR_PATH, SALES_PRODUCTS_VECTOR_PATH
from ct.settings.clients import openai_api_key as api_key, mongo_db, mongo_collection_specifications


class Load:
    def __init__(self):
        # La instancia de Transform ahora se crea aquí, no en el pipeline
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)

        self.client = MongoClient("mongodb://localhost:27017")
        self.db = self.client[mongo_db]
        # Eliminamos las colecciones de productos y ventas, ya que no se usarán
        self.specifications_collection = self.db[mongo_collection_specifications]

    def build_content(self, product : dict, product_features : list):
        """
        Construye el contenido del documento para el embedding.
        """
        return ". ".join(
            f"{product_feature}: {product.get(product_feature, 'No disponible')}" 
            for product_feature in product_features 
            if product.get(product_feature))

    # Eliminamos las funciones mongo_products y mongo_sales

    def load_products(self):
        """
        Carga los productos directamente desde la función de limpieza y los convierte
        en objetos Document de Langchain.
        """
        products = list(self.clean_data.clean_products())
        if not products:
            print("Advertencia: No hay productos para cargar.")
            return []

        # Usar product_features de un producto de ejemplo
        product_features = [column for column in products[0].keys() if column not in ["_id", "idProducto"]]

        docs = [
            Document(
                page_content=self.build_content(product, product_features),
                metadata = {"collection": 'productos', "clave": product.get("clave")} 
            )
            for product in products 
        ]
        return docs

    def load_sales(self):
        """
        Carga las ventas (ofertas) directamente desde la función de limpieza y las convierte
        en objetos Document de Langchain.
        """
        sales = list(self.clean_data.clean_sales())
        if not sales:
            print("Advertencia: No hay ofertas para cargar.")
            return []
        
        # Usar sales_features de una venta de ejemplo
        sales_features = [column for column in sales[0].keys() if column not in ["_id", "idProducto"]]
        docs = [
            Document(
                page_content=self.build_content(sale, sales_features),
                metadata = {"collection": 'promociones', "clave": sale.get("clave")} 
            )
            for sale in sales
        ]
        return docs
    
    def vector_store(self, docs: list[Document]) -> FAISS:
        """
        Crea un vector store de FAISS a partir de los documentos.
        """
        if not docs:
            print("Advertencia: No hay documentos para crear el vector store.")
            return None
        # La bandera allow_dangerous_deserialization se usa por seguridad
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def products_vs(self, products: list[Document]):
        """
        Crea o actualiza el vector store para productos.
        """
        if not products:
            print("No hay productos para crear el vector store.")
            return

        batch_size = 150
        total_docs = len(products)
        
        # Inicializar el vector store con el primer lote
        vector_store = self.vector_store(products[:batch_size])
        if vector_store:
            for i in range(batch_size, total_docs, batch_size):
                batch = products[i:i + batch_size]
                if batch:
                    vector_store.add_documents(batch)
                    print(f"Procesados {i + len(batch)} de {total_docs} documentos de productos.")
        
            vector_store.save_local(str(PRODUCTS_VECTOR_PATH))
            print("Vector store de productos creado y guardado en disco.")
        else:
            print("No se pudo crear el vector store de productos.")


    def sales_products_vs(self, sales: list[Document]):
        """
        Crea o actualiza el vector store para ventas/ofertas.
        """
        if not sales:
            print("No hay ventas para crear el vector store.")
            return

        batch_size = 150
        total_docs = len(sales)
        
        # Cargar el vector store de productos existente para añadir las ventas
        try:
            vector_store = FAISS.load_local(folder_path=str(PRODUCTS_VECTOR_PATH), 
                                            embeddings=self.embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"Error al cargar el vector store de productos, se creará uno nuevo si es necesario: {e}")
            vector_store = self.vector_store(sales[:batch_size])
            if not vector_store:
                print("No se pudo crear el vector store de ventas.")
                return

        vector_store.add_documents(sales[:min(batch_size, total_docs)])
        for i in range(batch_size, total_docs, batch_size):
            batch = sales[i:i + batch_size]
            if batch:
                vector_store.add_documents(batch)
                print(f"Procesados {i + len(batch)} de {total_docs} documentos de ventas.")
        
        vector_store.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        print("Vector store de ventas creado y guardado en disco.")

