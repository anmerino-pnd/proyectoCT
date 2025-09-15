import re
from langchain.tools import tool
from langchain.schema import Document
from ct.settings.clients import openai_api_key
from langchain_openai import OpenAIEmbeddings
from ct.langchain.vectorstore import LangchainVectorStore
from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH
from collections import defaultdict
from typing import List

vectorstore = LangchainVectorStore(
    OpenAIEmbeddings(openai_api_key=openai_api_key),
    SALES_PRODUCTS_VECTOR_PATH
)

retriever_productos = vectorstore.vectorstore.as_retriever(
    search_type='similarity',
    search_kwargs={
        "k": 5,
        "score_threshold": 0.80,
        "filter": {"collection": "productos"}
    }
)

retriever_promociones = vectorstore.vectorstore.as_retriever(
    search_type='similarity',
    search_kwargs={
        "k": 5,
        "score_threshold": 0.80,
        "filter": {"collection": "promociones"}
    }
)

def _group_docs_by_key(docs: List[Document]) -> dict:
    """
    Función auxiliar para agrupar documentos de Langchain por la 'clave'
    en sus metadatos y unir su contenido.
    """
    if not docs:
        return {}

    grouped_by_key = defaultdict(list)
    for doc in docs:
        clave = doc.metadata.get("clave")
        grouped_by_key[clave].append(doc.page_content)

    final_results = {
        clave: " ... ".join(contents)
        for clave, contents in grouped_by_key.items()
    }
    return final_results


@tool(description="Busca información detallada de productos y promociones. Agrupa la información por la clave del producto para dar un contexto completo.")
def search_information_tool(query: str) -> dict:
    """
    Realiza una búsqueda semántica y agrupa los resultados por producto.
    """
    promociones_docs = retriever_promociones.invoke(query)
    productos_docs = retriever_productos.invoke(query)

    grouped_promociones = _group_docs_by_key(promociones_docs)
    grouped_productos = _group_docs_by_key(productos_docs)

    return {
        "Promociones": grouped_promociones,
        "Productos": grouped_productos
    }

