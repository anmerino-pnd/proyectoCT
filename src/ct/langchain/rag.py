from ct.clients import openai_api_key
from langchain_openai import OpenAIEmbeddings
from ct.langchain.assistant import LangchainAssistant
from ct.langchain.vectorstore import LangchainVectorStore
from typing import AsyncGenerator
import ollama

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        self.model= "gemma3:4b"
        
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
        """
        Devuelve una respuesta prediseñada cuando la consulta es irrelevante.
        No utiliza un modelo de lenguaje, lo cual es más rápido y confiable.
        """
        return (
            "Gracias por tu mensaje. Nuestra empresa se especializa exclusivamente en productos de tecnología y cómputo, "
            "como laptops, impresoras, accesorios, redes, software y partes electrónicas.\n\n"
            "Tu consulta no parece estar relacionada con este tipo de productos. "
            "Por favor, intenta con una nueva pregunta enfocada en productos tecnológicos. "
            "Estaremos encantados de ayudarte. 😊"
        )

    def ban_answer(self, query: str) -> str:
        """
        Devuelve una respuesta prediseñada cuando la consulta es clasificada como inapropiada.
        No utiliza un modelo de lenguaje para garantizar rapidez y control de tono.
        """
        return (
            "Hemos detectado que tu mensaje contiene lenguaje o contenido inapropiado. "
            "Te pedimos mantener un lenguaje respetuoso y adecuado.\n\n"
            "Si continúas con este tipo de mensajes, podríamos restringir tu acceso al servicio. "
            "Por favor, formula tus preguntas de manera cordial para que podamos ayudarte con gusto."
        )

    async def run(self, query: str, session_id: str = None, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Ejecuta una consulta RAG y muestra los chunks de respuesta en tiempo real."""
        if session_id is None:
            session_id = "default_session"

        label = self.classify_query(query).strip().lower()
        yield f"Etiqueta de la consulta: {label}\n"

        if label == "relevante":
            async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                yield chunk
        elif label == "irrelevante":
            yield self.polite_answer(query)
        elif label == "inapropiado":
            yield self.ban_answer(query)


        