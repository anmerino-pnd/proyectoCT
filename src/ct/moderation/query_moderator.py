from datetime import datetime, timedelta, timezone
from typing import Optional
from ct.langchain.tool_agent import ToolAgent
import ollama


class QueryModerator:
    def __init__(self, model: str = "gemma3:4b", assistant : ToolAgent = None):
        self.model = model
        self.assistant = assistant

    def classify_query(self, query: str) -> str:
        result = ollama.generate(
            model=self.model,
            system=self._classification_prompt(),
            prompt=query,
            options={
                "temperature": 0,       # Valor de 0 lo hace determinista
                "top_p": 0.8,           # Distribución de probabilidad
                "num_predict": 20,      # Cantidad de palabras que devuelve al contestar
                "num_ctx": 36000,       # Cantidad de tokens de entrada, modelo gemma3 tiene 128k de entrada máximo
                "top_k": 3              # Prioridad de la cantidad de palabras 
            }
        )
        return result.response.strip().lower()

    def _classification_prompt(self) -> str:
        return """
Clasifica el siguiente mensaje del usuario respondiendo solo con una de estas palabras exactas:

- 'relevante'

- 'irrelevante'

- 'inapropiado'

Criterios:

- Relevante: mensajes relacionados con productos o servicios tecnológicos. Incluye búsqueda, recomendación, precios, cotizaciones, disponibilidad, promociones, detalles técnicos, políticas, términos y condiciones, estatus de pedidos o referencias a mensajes previos sobre estos temas. También saludos iniciales para conversar sobre productos tecnológicos.

- Irrelevante: mensajes no relacionados con tecnología (alimentos, ropa, perfumes, muebles, mascotas, deportes, celebridades, política, religión, salud, chistes, temas personales o electrodomésticos no tecnológicos).

- Inapropiado: mensajes con lenguaje ofensivo, vulgar, sexual, violento o amenazante, o solicitudes de productos de carácter sexual.

Responde únicamente con la palabra indicada, sin explicaciones ni repetir el mensaje.
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
