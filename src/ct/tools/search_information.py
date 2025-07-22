import re
from langchain.tools import tool
from ct.settings.clients import openai_api_key
from langchain_openai import OpenAIEmbeddings
from ct.langchain.vectorstore import LangchainVectorStore
from ct.settings.config import SALES_PRODUCTS_VECTOR_PATH

vectorstore = LangchainVectorStore(
    OpenAIEmbeddings(openai_api_key= openai_api_key),
    SALES_PRODUCTS_VECTOR_PATH
    )


retriever_productos = vectorstore.vectorstore.as_retriever(
    search_type='similarity',  
    search_kwargs={
        "k": 2, 
        "score_threshold": 0.95,  # alto para filtrar ruido
        "filter": {"collection": "productos"}
    }
)

retriever_promociones = vectorstore.vectorstore.as_retriever(
    search_type='similarity',
    search_kwargs={
        "k": 2, 
        "score_threshold": 0.95,
        "filter": {"collection": "promociones"}
    }
)

@tool(description="Busca productos y promociones usando búsqueda semántica.")
def search_information_tool(query):
    promociones = retriever_promociones.invoke(query)
    productos = retriever_productos.invoke(query)

    def parse_page_content(content):
        # Separa por '. ' pero ignora los puntos dentro de objetos o listas
        parts = re.split(r'\.\s+', content.strip())
        data = {}
        for part in parts:
            if ':' in part:
                key, val = part.split(':', 1)
                data[key.strip()] = val.strip().strip('.')
        return data

    return {
        "Promociones": [parse_page_content(doc.page_content) for doc in promociones],
        "Productos": [parse_page_content(doc.page_content) for doc in productos]
    }

