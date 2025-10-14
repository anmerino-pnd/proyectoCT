import redis
from typing import Optional
from langchain_openai import ChatOpenAI
from ct.settings.clients import openai_api_key
from datetime import datetime, timedelta, timezone

class QueryModerator:
    def __init__(self, assistant=None):
        self.assistant = assistant
        self.llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model="gpt-4.1",
            temperature=0,
            cache=True  
        )
        
    def classify_query(self, query: str, session_id: str) -> str:
        history = self._get_formatted_history(session_id)

        full_prompt = (
            "HISTORIAL DE LA CONVERSACIÓN:\n"
            f"{history}\n"
            "MENSAJE ACTUAL:\n"
            f"{query}"
        )

        response = self.llm.invoke([
            {"role": "system", "content": self._classification_prompt()},
            {"role": "user", "content": full_prompt},
        ])

        return response.content.strip().lower()

    def _classification_prompt(self) -> str:
        return """
Eres un asistente experto en clasificar el MENSAJE ACTUAL de un usuario para un chatbot de CT Internacional.
Tu única función es leer el MENSAJE ACTUAL y el HISTORIAL DE LA CONVERSACIÓN para responder con una de tres categorías.
Debes responder única y exclusivamente con UNA de las siguientes palabras exactas:
- 'relevante' 
- 'irrelevante'
- 'inapropiado'

Principio Fundamental: El Contexto es Rey
Si un mensaje por sí solo parece irrelevante o ambiguo (como '?', 'y ese?', 'para gaming'), pero el historial de la conversación trata sobre un tema relevante,
DEBES clasificar el mensaje actual como 'relevante'. El historial tiene prioridad sobre el contenido del mensaje aislado.

Criterios de Clasificación

1. 'relevante': Cualquier mensaje relacionado directamente con productos, servicios o temas de tecnología, O que sea una continuación directa de una conversación relevante.

    * Consultas Comerciales y de Producto:
        * Búsqueda, recomendación, precios, cotizaciones, disponibilidad, promociones.
        * Búsqueda por códigos, SKUs o números de parte (ej: 'ACCITL5520', 'c008').
        * Detalles sobre políticas, garantías, devoluciones, términos y condiciones.
        * Estatus de pedidos, envíos o devoluciones.
        * Saludos iniciales y mensajes con errores de tipeo pero con intención clara (ej: 'hols', 'cpuevo').

    * Soporte Técnico y Guías de Uso:
        * Preguntas sobre cómo instalar, configurar, usar o solucionar problemas de un producto.
        * Solicitudes de guías, manuales o tutoriales.

    * Aclaraciones y Conversación de Seguimiento (CRÍTICO):
        * Preguntas cortas que dependen del contexto anterior (ej: 'y en color rojo?', 'cuál es mejor?', 'por qué?').
        * Respuestas directas a una pregunta hecha por el chatbot (ej: si el bot pregunta '¿para qué uso?', la respuesta 'para arquitectura' es relevante).
        * Solicitudes de más opciones o variaciones (ej: 'dame otras 3', 'muéstrame más baratos').
        * Signos de interrogación o frases muy cortas si el contexto es relevante.

    * Dudas sobre la empresa CT Internacional:
        * 'quién es CT?'
        * 'qué es CT?'
        * 'Cuáles son los valores de la empresa?'

2. 'irrelevante': Cualquier mensaje que no guarde relación con el ámbito tecnológico de la empresa y que no sea una continuación de una conversación relevante.

    * Temas generales: alimentos, ropa, deportes, celebridades, política, religión, uso personal, etc.
    * Preguntas de "cómo hacer" sobre temas no tecnológicos (ej: ¿cómo cambiar una llanta?).
    * Conversación personal o chistes si inician una nueva conversación (ej: ¿cómo estás?, ¿qué haces?, ¿cómo funcionas?, etc.)

3. 'inapropiado': Mensajes ofensivos o solicitudes no éticas.

    * Lenguaje vulgar, sexual, violento, discriminatorio o amenazante.
    * Solicitudes de productos o servicios ilegales.

Ejemplos Clave:

* "¿cómo configurar mi impresora?" -> **Respuesta**: `relevante`
* "venden tarjetas madre con socket AM5?" -> **Respuesta**: `relevante`
* "¿cómo se cambia una llanta?" -> **Respuesta**: `irrelevante`
* "¿qué me recomiendas para cenar?" -> **Respuesta**: `irrelevante`
* "eres un tonto" -> **Respuesta**: `inapropiado`

Recuerda: No añadas explicaciones, saludos ni repitas el mensaje. Tu respuesta debe ser solo la palabra de la categoría.
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

        sancion : timedelta = escalado.get(tries, timedelta(days=7))  # Máximo castigo es 7 días
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
        banned_until : datetime = session.get("banned_until")
        
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
    
    def _get_formatted_history(self, session_id: str, last_n: int = 5) -> str:
        session = self.assistant.sessions.find_one(
            {"session_id": session_id},
            # Proyectamos solo el campo last_messages para eficiencia
            {"last_messages": {"$slice": -last_n}}
        )

        if not session or "last_messages" not in session:
            return ""

        # Formatear el historial
        formatted_messages = []
        for msg in session["last_messages"]:
            if msg["type"] == "human":
                formatted_messages.append(msg["content"])
            else:
                continue
        
        return "\n".join(formatted_messages)