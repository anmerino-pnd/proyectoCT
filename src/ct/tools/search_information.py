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
    search_type='similarity',  # o 'similarity'
    search_kwargs={
        "k": 2,  # pocos y muy relevantes
        "score_threshold": 0.85,  # alto para filtrar ruido
        "lambda_mult": 0.7,  
        "filter": {"collection": "productos"}
    }
)

retriever_promociones = vectorstore.vectorstore.as_retriever(
    search_type='similarity',
    search_kwargs={
        "k": 2,  # un poco más para abarcar promociones similares
        "score_threshold": 0.85,
        "lambda_mult": 0.7,  
        "filter": {"collection": "promociones"}
    }
)

@tool(description="Busca productos y promociones usando búsqueda semántica.")
def search_information_tool(query):
    lista = retriever_promociones.invoke(query) + retriever_productos.invoke(query)
    info = [doc.page_content for doc in lista]
    return info


