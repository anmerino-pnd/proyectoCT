from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from ct.settings.config import GUARANTEES_VECTOR_PATH

embeddings = OllamaEmbeddings(model="snowflake-arctic-embed2:568m")
vector_store = FAISS.load_local(
    GUARANTEES_VECTOR_PATH,
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

prompt_template = PromptTemplate(
    template="""
Utiliza el siguiente contexto para responder a la pregunta.
Si no sabes la respuesta, di que no la sabes, no intentes inventar una.
Contexto: {context}
Pregunta: {question}

No ofrezcas más ayuda, solo responde la duda actual.

SIEMPRE contesta en español.
""",
    input_variables=["context", "question"]
)

llm = ChatOllama(model="qwen3:8b", temperature=0.0)

chain = prompt_template | llm

def check_warranty(query: str):
    """
    Consulta en los vectores de procedimientos, términos, políticas, etc.
    y responde a la pregunta usando un modelo LLM.
    """

    results1 = retriever1.invoke(query)
    results2 = retriever2.invoke(query)

    print(results1, flush=True)
    print(results2, flush=True)


    context_text = " ".join([doc.page_content for doc in results1 + results2])

    response = chain.invoke({"context": context_text, "question": query})

    return response  # te devuelve el objeto completo (puede ser un dict o string según llm)

# --- Uso ---
# query = "Compré una ensamble Acer y no funcionó, cómo puedo hacer válida la garantía?"
# respuesta = consultar_garantia(query)
# print(respuesta)
