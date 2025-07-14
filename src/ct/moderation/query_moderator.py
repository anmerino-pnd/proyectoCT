from datetime import datetime, timedelta, timezone
from typing import Optional
from ct.langchain.assistant import LangchainAssistant
import ollama


class QueryModerator:
    def __init__(self, model: str = "gemma3:4b", assistant : LangchainAssistant = None):
        self.model = model
        self.assistant = assistant

    def classify_query(self, query: str) -> str:
        result = ollama.generate(
            model=self.model,
            system=self._classification_prompt(),
            prompt=query,
            options={
                "temperature": 0,
                "top_p": 0.8,
                "num_predict": 20,
                "num_ctx": 36000,
                "top_k": 3
            }
        )
        return result.response.strip().lower()

    def _classification_prompt(self) -> str:
        return """
        Clasifica la entrada del usuario como uno de los siguientes valores:

        - 'relevante' si el mensaje trata exclusivamente sobre búsqueda o recomendación de productos de tecnología o cómputo, como laptops, computadoras, servidores, impresoras, monitores, teléfonos, cámaras, accesorios tecnológicos (teclados, mouse, mochilas para laptop, audífonos), redes, software, licencias, dispositivos inteligentes (como asistentes de voz, enchufes inteligentes, cerraduras electrónicas), sistemas de seguridad o vigilancia (como cámaras de seguridad, alarmas, sensores, videovigilancia, kits de monitoreo), automatización del hogar o cualquier otro producto relacionado con tecnología.

        También clasifica como 'relevante' si el usuario pide precios, cotizaciones o información para comprar productos tecnológicos. 
        O si hace referencia a algo ya mencionado previamente (por ejemplo: "¿cuál es el precio de ese?"). 
        Los saludos o mensajes iniciales para comenzar una conversación también deben clasificarse como 'relevante'.

        - 'irrelevante' si el mensaje NO está relacionado con productos tecnológicos. Esto incluye alimentos, ropa, perfumes, artículos de cuidado personal, muebles, mascotas, deportes, celebridades, electrodomésticos del hogar (lavadoras, refrigeradores, estufas), política, religión, salud, chistes, temas personales o cualquier otra conversación casual no relacionada con tecnología.

        - 'inapropiado' si el mensaje contiene lenguaje ofensivo, sexual, violento, amenazante o vulgar, o si solicita productos de carácter sexual.

        Ejemplos irrelevantes: "Quiero una hamburguesa", "Tienen pañales para bebé?", "Qué opinas de Messi?", "Me siento triste", "Dónde queda Cancún", "Quiero comprar una blusa".

        Solo responde con una palabra exacta: 'relevante', 'irrelevante' o 'inapropiado'. No des explicaciones ni repitas el mensaje del usuario.
        """
    
    def classify_relevant_query(self, query: str) -> str:
        result = ollama.generate(
            model=self.model,
            system=self._classification_relevant_query(),
            prompt=query,
            options={
                "temperature": 0,
                "top_p": 0.8,
                "num_predict": 20,
                "num_ctx": 36000,
                "top_k": 2
            }
        )
        return result.response.strip().lower()


    def _classification_relevant_query(self) -> str:
        return """
        Eres un clasificador. Clasifica la intención de la entrada del usuario. 

        Responde solamente con UNA de estas etiquetas (sin comillas):

        - existencias
        - información

        Instrucciones:
        - Usa 'existencias' **solo si** el usuario está preguntando por una cantidad específica de productos, como "¿cuántas tienen?", "¿quedan 10?", "¿hay más de 3?".
        - Usa 'información' para TODO lo demás, incluyendo preguntas como "¿tienen laptops?" o "¿venden ese modelo?", incluso si se habla de productos.

        Ejemplos:
        Usuario: ¿Cuántas impresoras tienen?
        → existencias

        Usuario: ¿Tienen laptops?
        → información

        Usuario: ¿Todavía hay 5 disponibles?
        → existencias

        Usuario: ¿Tienen el modelo X?
        → información

        Tu única respuesta debe ser una sola palabra: 'existencias' o 'información'.
        """

    def polite_answer(self) -> str:
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


    def ban_answer(self) -> str:
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
            msg = self.ban_answer()
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
