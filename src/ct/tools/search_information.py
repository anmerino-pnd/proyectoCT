from langchain.tools import tool
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from typing import List
from collections import defaultdict
from pydantic import BaseModel, Field
from ct.settings.clients import openai_api_key
from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH

vectorstore = FAISS.load_local(
    folder_path=str(SALES_PRODUCTS_VECTOR_PATH),
    embeddings=OpenAIEmbeddings(openai_api_key=openai_api_key),
    allow_dangerous_deserialization=True  # Necesario para FAISS
)
index_por_clave = {doc.metadata["clave"]: doc for doc in vectorstore.docstore._dict.values()}

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

def _group_docs_by_key(docs: List[Document]) -> dict:
    """
    Función auxiliar para agrupar documentos de Langchain por la 'clave'
    en sus metadatos y unir su contenido.
    """

    grouped_by_key = defaultdict(list)
    for doc in docs:
        clave = doc.metadata.get("clave")
        grouped_by_key[clave].append(doc.page_content)

    final_results = {
        clave: " ".join(contents)
        for clave, contents in grouped_by_key.items()
    }
    return final_results


@tool(description="Busca información detallada de productos y promociones. Agrupa la información por la clave del producto para dar un contexto completo.")
def search_information_tool(query: str) -> dict:

    promociones_docs = retriever_promociones.invoke(query)
    productos_docs = retriever_productos.invoke(query)

    grouped_promociones = _group_docs_by_key(promociones_docs)
    grouped_productos = _group_docs_by_key(productos_docs)

    result = {"Promociones": grouped_promociones, "Productos": grouped_productos}
    return result

class ClaveInput(BaseModel):
    clave: str = Field(description="Clave del producto en MAYUSCULAS")

docstore_dict = dict(vectorstore.docstore._dict)

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

