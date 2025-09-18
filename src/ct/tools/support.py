import re
import ollama 
from string import Template
from pydantic import BaseModel, Field
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from ct.settings.config import SUPPORT_INFO_VECTOR_PATH

embeddings = OllamaEmbeddings(model="snowflake-arctic-embed2:568m")
vector_store = FAISS.load_local(
    SUPPORT_INFO_VECTOR_PATH,
    embeddings=embeddings,
    allow_dangerous_deserialization=True
)

retriever1 = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={'k': 1, 'lambda_mult': 0.7,
                    'filter': {'collection': 'Procedimientos Garantía'}}
)

retriever2 = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={'k': 3, 'lambda_mult': 0.7,
                    'filter': {'collection': ['Compra en línea', 'ESD', 'Políticas', 'Términos y Condiciones']}}
)

class SupportInput(BaseModel):
    query: str = Field(description="Duda del usuario")
    
def system_prompt(context: str):
    prompt = Template("""
Eres un agente experto en consultas de políticas, garantías, términos y condiciones.
Utiliza el siguiente contexto para responder a la pregunta del usuario.
Si no sabes la respuesta, di que no la sabes, no intentes inventar una.
Contexto: 
${context}

No ofrezcas más ayuda, solo responde la duda actual.

SIEMPRE contestas en español.
""")
    return prompt.substitute(
        context=context
        )

def get_support_info(query: str):

    results1 = retriever1.invoke(query)
    results2 = retriever2.invoke(query)

    context_text = " ".join([doc.page_content for doc in results1 + results2])
    #system = system_prompt(context_text)

    # response = ollama.generate(
    #     model="qwen3:8b",
    #     system=system,
    #     prompt=query,
    #     options={'temperature':0}
    # )

    # response = re.sub(r"<think>.*?</think>", "", response.response, flags=re.DOTALL)

    return context_text