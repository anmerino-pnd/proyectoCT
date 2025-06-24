from ct.langchain.vectorstore import LangchainVectorStore
from ct.langchain.embedder import LangchainEmbedder
from ct.langchain.assistant import LangchainAssistant
from typing import AsyncGenerator
import ollama

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = LangchainEmbedder()  # Asegúrate que retorna un objeto Embeddings
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        self.model= "gemma3:12b"
        
        # Verifica que el retriever se haya creado
        if not hasattr(self.vectorstore, 'retriever'):
            raise ValueError("VectorStore no se inicializó correctamente. ¿El índice existe?")
            
        self.assistant = LangchainAssistant(self.vectorstore.retriever)

    def classify_query(self, query: str) -> str:
        return ollama.generate(
        model= self.model,
        system="""
        Clasifica la entrada del usuario como uno de los siguientes valores:

        - 'relevante' si el mensaje trata exclusivamente sobre productos de tecnología o cómputo, como laptops, computadoras, servidores, impresoras, monitores, teléfonos, cámaras, accesorios tecnológicos (teclados, mouse, mochilas para laptop, audífonos), redes, software, licencias, dispositivos inteligentes, componentes electrónicos (RAM, SSD, tarjetas madre), o si pregunta por precios, cotizaciones, soporte técnico o compra de productos tecnológicos.

        - 'irrelevante' si la consulta NO está relacionada con productos tecnológicos. Esto incluye mensajes sobre alimentos, ropa, perfumes, artículos de cuidado personal, muebles, mascotas, deportes, celebridades, electrodomésticos del hogar (lavadoras, refrigeradores, estufas), preguntas filosóficas, política, religión, chistes, salud o cualquier otra conversación casual o fuera del giro comercial de tecnología.

        - 'inapropiado' si el mensaje contiene lenguaje ofensivo, sexual, violento, amenazante o vulgar, o si solicita productos de carácter sexual.

        Ejemplos irrelevantes: "Quiero una hamburguesa", "Tienen pañales para bebé?", "Qué opinas de Messi?", "Me siento triste", "Dónde queda Cancún", "Quiero comprar una blusa".

        Solo responde con una palabra exacta: 'relevante', 'irrelevante' o 'inapropiado'. No des explicaciones ni repitas el mensaje del usuario.
        """
        ,
        prompt=query,
        options={'temperature' : 0, 'top_p': 0.1, 'num_predict': 10}
    ).response

    def polite_answer(self, query: str) -> str:
        return ollama.generate(
        model= self.model,
        system="""
        Eres un asistente cordial de una empresa especializada exclusivamente en productos de tecnología y cómputo, como laptops, impresoras, teléfonos, accesorios, redes, software, partes electrónicas, etc.

        Tu tarea es responder amablemente al usuario cuando su consulta no está relacionada con ese tipo de productos.

        Indícale con cortesía que no manejamos ese tipo de artículos, y que puede volver a intentarlo preguntando por productos tecnológicos.

        No uses lenguaje sarcástico ni autoritario. Sé breve, claro y profesional.
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
        Has detectado un mensaje clasificado como 'inapropiado' por su contenido ofensivo, sexual, violento o irrespetuoso. 
        Tu deber es responder de forma clara y firme, sin sarcasmo ni tono amistoso. No intentes suavizar el mensaje ni educar con sugerencias.
        Tu único objetivo es establecer límites.

        Dile al usuario directamente que ese tipo de lenguaje no está permitido en esta plataforma. Adviértele que, si insiste en ese comportamiento, se le bloqueará el acceso.

        No sugieras reformulaciones ni alternativas. No des explicaciones.
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

        label = self.classify_query(query).strip().lower()
        yield label

        if label == "relevante":
            print('OpenAI')
            async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                yield chunk
        elif label == "irrelevante":
            print('Ollama')
            for chunk in self.polite_answer(query):
                yield chunk.response
        elif label == "inapropiado":
            print('Ollama')
            for chunk in self.ban_answer(query):
                yield chunk.response


        