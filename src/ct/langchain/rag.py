from ct.langchain.vectorstore import LangchainVectorStore
from ct.langchain.embedder import LangchainEmbedder
from ct.langchain.assistant import LangchainAssistant
from typing import Tuple, AsyncGenerator
import ollama

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = LangchainEmbedder()  # Asegúrate que retorna un objeto Embeddings
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        self.model= "phi4:latest"
        
        # Verifica que el retriever se haya creado
        if not hasattr(self.vectorstore, 'retriever'):
            raise ValueError("VectorStore no se inicializó correctamente. ¿El índice existe?")
            
        self.assistant = LangchainAssistant(self.vectorstore.retriever)

    def classify_query(self, query: str) -> str:
        return ollama.generate(
        model= self.model,
        system= """
            Clasifica la entrada del usuario como uno de los siguientes valores:
            - 'relevante' si el mensaje trata sobre precios, cotizaciones, productos tecnológicos, computadoras o cualquier solicitud de compra o asistencia comercial.
            - 'irrelevante' si es un saludo, una conversación casual o no relacionada con productos.
            - 'inapropiado' si contiene lenguaje ofensivo, contenido sexual, violencia, amenazas, groserías, o cualquier tema o producto sexual.

            Solo responde con una palabra: 'relevante', 'irrelevante' o 'inapropiado'. No agregues explicaciones.
            """
            ,
        prompt=query,
        options={'temperature' : 0, 'top_p': 0.1, 'num_predict': 10}
    ).response

    def polite_answer(self, query: str) -> str:
        return ollama.generate(
        model= self.model,
        system="""
            Eres un asistente cordial. Tu tarea es informarle al usuario que su mensaje no parece estar relacionado con productos o compras.
            Pídele de forma amable y clara que reformule su solicitud para que puedas ayudarlo mejor.
            No uses lenguaje sarcástico ni autoritario.
            """
            ,
        prompt=f"El usuario preguntó: {query}",
        options={'temperature' : 0},
        stream=True
    )
    
    def ban_answer(self, query: str) -> str:
        return ollama.generate(
        model= self.model,
        system="""
            El mensaje del usuario ha sido clasificado como inapropiado. 
            Infórmale con seriedad, pero sin insultos, que este tipo de lenguaje no es aceptado. 
            Adviértele que, si continúa, su acceso será restringido.
            """
            ,
        prompt=f"El usuario preguntó: {query}",
        options={'temperature' : 0},
        stream=True
    )

    async def run(self, query: str, session_id: str = None, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Ejecuta una consulta RAG y muestra los chunks de respuesta en tiempo real."""
        if session_id is None:
            session_id = "default_session"

        label = self.classify_query(query)

        if 'relevante' in label.lower():
            async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                yield chunk
        elif 'irrelevante' in label.lower():
            for chunk in self.polite_answer(query):
                yield chunk.response
        elif 'inapropiado' in label.lower():
            for chunk in self.ban_answer(query):
                yield chunk.response

        