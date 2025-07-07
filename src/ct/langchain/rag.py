from ct.clients import openai_api_key
from langchain_openai import OpenAIEmbeddings
from ct.langchain.assistant import LangchainAssistant
from ct.langchain.vectorstore import LangchainVectorStore
from typing import AsyncGenerator, Optional
from datetime import timedelta, timezone, datetime
import ollama

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        self.model= "gemma3:1b"
        
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

        session = self.assistant.ensure_session(session_id)
        ban_message = self.check_if_banned(session)
        if ban_message:
            yield ban_message
            return

        label = self.classify_query(query).strip().lower()

        if label == "relevante":
            async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                yield chunk
        elif label == "irrelevante":
            yield self.polite_answer(query)
        elif label == "inapropiado":
            session = self.assistant.sessions.find_one({"session_id": session_id}) or {}
            msg, tries, banned_until = self.evaluate_inappropriate_behavior(session, query)

            self.update_inappropriate_session(session_id, tries, banned_until)
            yield msg
        else:
            yield "Lo siento, no entendí tu mensaje. ¿Podrías reformularlo?"

    def check_if_banned(self, session: dict) -> Optional[str]:
        """Verifica si el usuario está actualmente baneado."""
        now = datetime.now(timezone.utc)
        banned_until = session.get("banned_until")
        
        if banned_until:
            # Asegurar que banned_until tenga zona horaria UTC si no la tiene
            if banned_until.tzinfo is None:
                banned_until = banned_until.replace(tzinfo=timezone.utc)
            
            if banned_until > now:
                tiempo_restante = banned_until - now
                horas = int(tiempo_restante.total_seconds() // 3600)
                minutos = int((tiempo_restante.total_seconds() % 3600) // 60)
                return (
                    f"Tu acceso sigue restringido por conducta inapropiada.\n\n"
                    f"Podrás volver a usar el asistente en aproximadamente {horas} horas y {minutos} minutos."
                )
            else:
                # El ban ya expiró, limpiar la base de datos
                self.assistant.sessions.update_one(
                    {"session_id": session.get("session_id")},
                    {"$unset": {"banned_until": ""}}
                )
        
        return None

    def evaluate_inappropriate_behavior(self, session: dict, query: str) -> tuple[str, int, Optional[datetime]]:
        now = datetime.now(timezone.utc)
        last = session.get("last_inappropriate")
        tries = session.get("inappropriate_tries", 0) + 1

        # Si ha pasado más de 1 hora y el baneo anterior era menor a 1 hora, perdonamos
        banned_until = session.get("banned_until")
        if last:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)

            if (now - last).total_seconds() > 3600:
                # Si hubo baneo previo y fue menor a 1 hora
                if banned_until:
                    if banned_until.tzinfo is None:
                        banned_until = banned_until.replace(tzinfo=timezone.utc)
                    duration = (banned_until - last).total_seconds()
                    if duration < 3600:
                        tries = 1  # perdona
                else:
                    # No hubo baneo (solo advertencia), también perdona
                    tries = 1


        # Escalamiento progresivo
        escalado = {
            1: None,
            2: timedelta(minutes=1),
            3: timedelta(minutes=3),
            4: timedelta(minutes=10),
            5: timedelta(hours=1),
            6: timedelta(days=1),
            7: timedelta(days=7)
        }

        sancion = escalado.get(tries, timedelta(days=7))  # Máximo castigo es 7 días
        banned_until = now + sancion if sancion else None

        # Mensajes personalizados
        if sancion is None:
            msg = self.ban_answer(query)
        elif sancion.total_seconds() < 3600:
            minutos = int(sancion.total_seconds() // 60)
            msg = f"Se ha restringido temporalmente tu acceso por {minutos} minutos debido a lenguaje inapropiado."
        elif sancion.total_seconds() < 86400:
            horas = int(sancion.total_seconds() // 3600)
            msg = f"Tu acceso ha sido bloqueado por {horas} hora debido a múltiples incidentes."
        elif sancion.total_seconds() < 604800:
            msg = "Tu acceso ha sido bloqueado por 1 día debido a repetidas conductas inapropiadas."
        else:
            msg = "Tu acceso ha sido bloqueado por 7 días debido a reiteradas violaciones."

        return msg, tries, banned_until


        
    def update_inappropriate_session(self, session_id: str, tries: int, banned_until: Optional[datetime]):
        update_fields = {
            "inappropriate_tries": tries,
            "last_inappropriate": datetime.now(timezone.utc),
        }
        if banned_until:
            update_fields["banned_until"] = banned_until

        self.assistant.sessions.update_one(
            {"session_id": session_id},
            {"$set": update_fields},
            upsert=True
        )
