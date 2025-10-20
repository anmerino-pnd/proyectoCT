from langchain.tools import tool
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS

from typing import List
from collections import defaultdict
from pydantic import BaseModel, Field
from ct.settings.clients import openai_api_key
from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH

index_por_clave = None
ensemble_retriever = None

def vector_store():
    vectorstore = FAISS.load_local(
        folder_path=str(SALES_PRODUCTS_VECTOR_PATH),
        embeddings=OpenAIEmbeddings(openai_api_key=openai_api_key),
        allow_dangerous_deserialization=True  # Necesario para FAISS
    )
    index_por_clave = {
        doc.metadata["clave"]: doc for doc in vectorstore.docstore._dict.values()
        }

    retriever_productos = vectorstore.as_retriever(
        search_type='mmr',
        search_kwargs={
            "k": 8,
            "filter": {"collection": "productos"},
            "lambda_mult": 0.85
        }
    )

    retriever_promociones = vectorstore.as_retriever(
        search_type='mmr',
        search_kwargs={
            "k": 10,
            "filter": {"collection": "promociones"},
            "lambda_mult": 0.85
        }
    )
    return index_por_clave, EnsembleRetriever(
    retrievers=[retriever_productos, retriever_promociones]
)

def reload_vector_store():
    global index_por_clave, ensemble_retriever
    index_por_clave, ensemble_retriever = vector_store()
    print("✅ Vector store recargado exitosamente en memoria.")
    return True


# --- CARGA INICIAL ---
reload_vector_store()

def _merge_grouped_docs(grouped_dict):
    return {k: " ".join(v) for k, v in grouped_dict.items()}

def _group_docs_by_key(docs: List[Document]) -> dict:
    """
    Función auxiliar para agrupar documentos de Langchain por la 'clave'
    en sus metadatos y unir su contenido.
    """
    productos_grouped_by_key = defaultdict(list)
    sales_grouped_by_key = defaultdict(list)

    for doc in docs:
        match doc.metadata.get('collection'):
            case 'productos':
                clave = doc.metadata.get("clave")
                productos_grouped_by_key[clave].append(doc.page_content)
            case 'promociones':
                clave = doc.metadata.get("clave")
                sales_grouped_by_key[clave].append(doc.page_content)
        
    return {
    "productos": _merge_grouped_docs(productos_grouped_by_key),
    "promociones": _merge_grouped_docs(sales_grouped_by_key)
}


@tool(description="Busca información detallada de productos y promociones. Agrupa la información por la clave del producto para dar un contexto completo.")
def search_information_tool(query: str) -> dict[str, dict[str, str]]:
    docs = ensemble_retriever.invoke(query)
    return _group_docs_by_key(docs)

class ClaveInput(BaseModel):
    clave: str = Field(description="Clave del producto en MAYUSCULAS")

def search_by_key_tool(clave: str) -> dict:
    """
    Busca documentos por clave en el índice ya generado.
    """
    doc = index_por_clave.get(clave)
    if not doc:
        return {
            "status": "error",
            "message": "Producto no encontrado actualmente"
        }

    # Si hay más de un documento por clave, puedes adaptar esto:
    return {
        "status": "ok",
        "data": _group_docs_by_key([doc])
    }

