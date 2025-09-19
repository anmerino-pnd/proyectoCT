import re
import ollama 
from typing import List, Literal
from string import Template
from pydantic import BaseModel, Field
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from ct.settings.clients import openai_api_key
from langchain_community.vectorstores import FAISS
from ct.settings.config import SUPPORT_INFO_VECTOR_PATH

# Define los filtros disponibles usando Literal para que el agente los conozca.
# Esto es más robusto que solo mencionarlos en el prompt, ya que forma parte del "schema" de la herramienta.
SupportFilter = Literal['Compra en línea', 'ESD', 'Políticas', 'Términos y Condiciones', 'Procedimientos Garantía']

class SupportInput(BaseModel):
    """Define la entrada para la herramienta de información de soporte."""
    query: str = Field(description="La pregunta o duda específica del usuario.")
    filters: List[SupportFilter] = Field(
        description="Una lista de filtros a aplicar para la búsqueda. Elige los más relevantes de las opciones disponibles según la consulta del usuario."
    )

#embeddings = OllamaEmbeddings(model="snowflake-arctic-embed2:568m")
embeddings = OpenAIEmbeddings(api_key=openai_api_key)

vector_store = FAISS.load_local(
    SUPPORT_INFO_VECTOR_PATH,
    embeddings=embeddings,
    allow_dangerous_deserialization=True
)
def get_faiss_retriever(collection_filter: str):
    """
    Crea y devuelve un retriever de FAISS configurado para un filtro de colección específico.
    """    
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            'k': 12,
            'filter': {'collection': collection_filter},
        }
    )

def get_support_info(query: str, filters: List[SupportFilter]) -> str:
    """
    Recupera información de la base de datos vectorial basada en una consulta y una lista de filtros.
    El agente debe inferir los filtros correctos a partir de la consulta del usuario.
    """
    context_parts = []

    for collection_filter in filters:
        try:
            retriever = get_faiss_retriever(collection_filter=collection_filter)
            docs = retriever.invoke(query)
            if docs:
                # Agrega un título para separar el contexto de cada filtro
                context_parts.append(f"--- Información sobre: {collection_filter} ---\n")
                all_info = "\n".join([doc.page_content for doc in docs])
                context_parts.append(all_info)
        except Exception as e:
            # Es buena idea registrar errores si un filtro falla.
            print(f"Error retrieving info for filter '{collection_filter}': {e}")
            
    if not context_parts:
        return "No se encontró información relevante para los filtros seleccionados."
        
    return "\n".join(context_parts)

# def get_support_info(query: str, filters: List[str]):

#     results1 = retriever1.invoke(query)
#     results2 = retriever2.invoke(query)
#     print(results2)
#     context_text = " ".join([doc.page_content for doc in results1 + results2])
    #system = system_prompt(context_text)

    # response = ollama.generate(
    #     model="qwen3:8b",
    #     system=system,
    #     prompt=query,
    #     options={'temperature':0}
    # )

    # response = re.sub(r"<think>.*?</think>", "", response.response, flags=re.DOTALL)

    #return context_text

# def system_prompt(context: str):
#     prompt = Template("""
# Eres un agente experto en consultas de políticas, garantías, términos y condiciones.
# Utiliza el siguiente contexto para responder a la pregunta del usuario.
# Si no sabes la respuesta, di que no la sabes, no intentes inventar una.
# Contexto: 
# ${context}

# No ofrezcas más ayuda, solo responde la duda actual.

# SIEMPRE contestas en español.
# """)
#     return prompt.substitute(
#         context=context
#         )