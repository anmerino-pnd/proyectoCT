from langchain.tools import tool
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
#from langchain_core.vectorstores import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore


from typing import List, cast
from collections import defaultdict
from ct.settings.clients import openai_api_key
from pydantic import BaseModel, Field, SecretStr
from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH

index_por_clave = None
retriever_productos = None
retriever_promociones = None

def vector_store():
    vectorstore = FAISS.load_local(
        folder_path=str(SALES_PRODUCTS_VECTOR_PATH),
        embeddings=OpenAIEmbeddings(api_key=SecretStr(openai_api_key)),
        allow_dangerous_deserialization=True
    )

    docstore = cast(InMemoryDocstore, vectorstore.docstore)
    index_por_clave = {
        doc.metadata["clave"]: doc for doc in docstore._dict.values()
    }

    retriever_productos = vectorstore.as_retriever(
        search_type='mmr',
        search_kwargs={
            "k": 10,
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

    return index_por_clave, retriever_productos, retriever_promociones


def reload_vector_store():
    global index_por_clave, retriever_productos, retriever_promociones
    index_por_clave, retriever_productos, retriever_promociones = vector_store()
    print("✅ Vector store recargado exitosamente.")
    return True

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

@tool(description="Busca información de productos y promociones de Honeywell y otras marcas.")
def search_information_tool(query: str) -> dict:
    assert retriever_productos is not None, "retriever_productos no inicializado"
    assert retriever_promociones is not None, "retriever_promociones no inicializado"

    docs_prod = retriever_productos.invoke(query)   # ✅
    docs_prom = retriever_promociones.invoke(query) # ✅
    
    all_docs = docs_prod + docs_prom
    return _group_docs_by_key(all_docs)

class ClaveInput(BaseModel):
    clave: str = Field(description="Clave del producto en MAYUSCULAS")

def search_by_key_tool(clave: str) -> dict:
    """
    Busca documentos por clave en el índice ya generado.
    """
    assert index_por_clave is not None, "index_por_clave no inicializado"

    doc = index_por_clave.get(clave)  # ✅
    if not doc:
        return {
            "status": "error",
            "message": "Producto no encontrado actualmente"
        }

    return {
        "status": "ok",
        "data": _group_docs_by_key([doc])
    }

