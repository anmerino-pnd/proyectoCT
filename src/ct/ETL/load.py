from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ct.ETL.transform import Transform
from ct.settings.clients import openai_api_key as api_key
from ct.settings.config import (
    PRODUCTS_VECTOR_PATH, 
    SALES_VECTOR_PATH, 
    SALES_PRODUCTS_VECTOR_PATH
    )


class Load:
    def __init__(self):
        self.clean_data = Transform()
        self.embeddings = OpenAIEmbeddings(api_key=api_key)
        
        # Inicializamos el divisor de texto con los parámetros que necesitas
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=220,
            chunk_overlap=10,  # Este es el 'padding' o solapamiento
            length_function=len,
            add_start_index=True, # Ayuda a identificar la posición del chunk
            strip_whitespace = True
        )

    def _create_documents_with_context(self, data: dict, collection_name: str) -> list[Document]:
        """
        Función genérica para crear documentos, dividirlos en chunks y 
        añadir contexto a cada uno.
        """
        all_docs = []
        if not data:
            return all_docs

        for clave, content in data.items():
            contexto = content.get("contexto", "")
            texto_principal = content.get("informacion", "")

            # Dividimos el contenido principal en chunks
            chunks = self.text_splitter.split_text(texto_principal)

            for chunk in chunks:
                # A cada chunk le anteponemos la información de contexto
                page_content_with_context = f"{clave} {contexto} {chunk}"
                
                doc = Document(
                    page_content=page_content_with_context,
                    metadata={"collection": collection_name, "clave": clave}
                )
                all_docs.append(doc)
        
        return all_docs

    def load_products(self) -> list[Document]:
        """
        Carga los productos, los divide en chunks y les añade contexto.
        """
        ids_validos = self.clean_data.data.get_valid_ids()
        products_data = self.clean_data.clean_products(ids_validos)
        if not products_data:
            print("Advertencia: No hay productos para cargar.")
            return []

        docs = self._create_documents_with_context(products_data, 'productos')
        print(f"Se generaron {len(docs)} documentos (chunks) para productos.")
        return docs

    def load_sales(self) -> list[Document]:
        """
        Carga las ventas (ofertas), las divide en chunks y les añade contexto.
        """
        sales_raw = self.clean_data.data.get_current_sales()
        sales_data = self.clean_data.clean_sales(sales_raw)
        if not sales_data:
            print("Advertencia: No hay ofertas para cargar.")
            return []

        docs = self._create_documents_with_context(sales_data, 'promociones')
        print(f"Se generaron {len(docs)} documentos (chunks) para ofertas.")
        return docs
    
    def vector_store(self, docs: list[Document]) -> FAISS:
        """
        Crea un vector store de FAISS a partir de los documentos.
        """
        if not docs:
            print("Advertencia: No hay documentos para crear el vector store.")
            return None
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store
    
    def products_vs(self, products: list[Document]):
        """
        Crea o actualiza el vector store para productos.
        """
        if not products:
            print("No hay productos para crear el vector store.")
            return

        batch_size = 500
        total_docs = len(products)
        
        if total_docs == 0:
            print("No hay documentos de productos para procesar.")
            return
            
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


    def sales_vs(self, sales: list[Document]):
        """
        Crea o actualiza el vector store para ventas/ofertas.
        """
        if not sales:
            print("No hay ventas para crear el vector store.")
            return
            
        batch_size = 500
        total_docs = len(sales)
        if total_docs == 0:
            print("No hay documentos de ventas para procesar.")
            return

        vector_store = self.vector_store(sales[:batch_size])
        if vector_store:
            for i in range(batch_size, total_docs, batch_size):
                batch = sales[i:i + batch_size]
                if batch:
                    vector_store.add_documents(batch)
                    print(f"Procesados {i + len(batch)} de {total_docs} documentos de productos.")
        
            vector_store.save_local(str(SALES_VECTOR_PATH))
            print("Vector store de productos creado y guardado en disco.")
        else:
            print("No se pudo crear el vector store de productos.")

    def sales_products_vs(self):
        products_vs = FAISS.load_local(
            folder_path=str(PRODUCTS_VECTOR_PATH),
            embeddings=OpenAIEmbeddings(openai_api_key=api_key),
            allow_dangerous_deserialization=True
        )
        sales_vs = FAISS.load_local(
            folder_path=str(SALES_VECTOR_PATH),
            embeddings=OpenAIEmbeddings(openai_api_key=api_key),
            allow_dangerous_deserialization=True
        )

        products_vs.merge_from(sales_vs)
        products_vs.save_local(str(SALES_PRODUCTS_VECTOR_PATH))
        return print("Vector store de productos y ofertas creado y guardado en disco.")

    def add_products(self):
        productos_vectorstore = FAISS.load_local(
            folder_path=str(PRODUCTS_VECTOR_PATH),
            embeddings=OpenAIEmbeddings(openai_api_key=api_key),
            allow_dangerous_deserialization=True
        )

        unique_products = list(set([doc.metadata["clave"] for doc in productos_vectorstore.docstore._dict.values()]))
        ids_nuevos = self.clean_data.data.update_products(unique_products)
        if ids_nuevos == []:
            print("Advertencia: No hay productos nuevos para cargar.")
            return False
        new_products = self.clean_data.clean_products(ids_nuevos)
        
        docs = self._create_documents_with_context(new_products, 'productos')

        productos_vectorstore.add_documents(docs)

        productos_vectorstore.save_local(str(PRODUCTS_VECTOR_PATH))
        print(f"Cantidad de documentos nuevos agregados: {len(docs)}")
        return True
    