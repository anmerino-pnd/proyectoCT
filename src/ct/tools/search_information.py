from langchain.tools import tool
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH
from ct.settings.clients import openai_api_key
from pydantic import BaseModel, Field
from collections import defaultdict
from typing import List

from cachetools import TTLCache
from functools import lru_cache

query_cache = TTLCache(maxsize=2000, ttl=600)

vectorstore = FAISS.load_local(
    folder_path=str(SALES_PRODUCTS_VECTOR_PATH),
    embeddings=OpenAIEmbeddings(openai_api_key=openai_api_key),
    allow_dangerous_deserialization=True  # Necesario para FAISS
)

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
    if query in query_cache:
        return query_cache[query]

    promociones_docs = retriever_promociones.invoke(query)
    productos_docs = retriever_productos.invoke(query)

    grouped_promociones = _group_docs_by_key(promociones_docs)
    grouped_productos = _group_docs_by_key(productos_docs)

    result = {"Promociones": grouped_promociones, "Productos": grouped_productos}
    query_cache[query] = result
    return result

class ClaveInput(BaseModel):
    clave: str = Field(description="Clave del producto en MAYUSCULAS")

docstore_dict = vectorstore.docstore._dict

key_cache = TTLCache(maxsize=500, ttl=600)
def search_by_key_tool(clave: str) -> dict:
    if clave in key_cache:
        return key_cache[clave]

    docs_encontrados = []
    for doc_id, doc in docstore_dict.items():
        if doc.metadata.get("clave") == clave:
            docs_encontrados.append(doc)

    if not docs_encontrados:
        result = "producto no encontrado o clave CT incorrecta"
    else:
        result = _group_docs_by_key(docs_encontrados)

    key_cache[clave] = result
    return result
    
