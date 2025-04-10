import os
import json
import time
from typing import AsyncGenerator, Dict
from datetime import datetime, timezone

from ct.openai.llm import LLM
from ct.types import LLMAPIResponseError
from ct.tools.assistant import Assistant
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler


from langchain_core.runnables import ConfigurableFieldSpec
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.schema import AIMessage, HumanMessage, BaseMessage 
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class LangchainAssistant(Assistant):
    """
    Langchain Assistant class that integrates with Langchain components."
    """
    def __init__(self, retriever):
        self.model = LLM().model
        self.llm = LLM().llm
        self.retriever = retriever

        self.history_file = "./datos/history.json"
        self._ensure_history_file()
        self.histories: Dict[str, list] = self.load_history()

        self.session_memory: Dict[str, ConversationBufferWindowMemory] = {}
        self.memory_window_size = 3 # O el valor que elijas (k=5 turnos)

        self.rag_chain = self.build_chain()

    def _ensure_history_file(self):
        """Verifica si el archivo de historial existe, si no, lo crea vacío."""
        if not os.path.exists(self.history_file):
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True) # Asegura que el directorio exista
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

    def load_history(self) -> dict:
        """Carga el historial de conversaciones COMPLETO desde un archivo JSON."""
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Advertencia: No se pudo cargar el historial desde {self.history_file}. Iniciando con historial vacío.")
            return {}
        
    def save_full_history(self):
        """Guarda el diccionario COMPLETO de historiales en el archivo JSON."""
        # Esta función podría llamarse periódicamente o al cerrar la app
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.histories, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial completo en {self.history_file}: {e}")

    def add_message_to_full_history(self, session_id: str, message_type: str, content: str, metadata: dict = None):
        """Añade un mensaje al historial COMPLETO (self.histories) y lo guarda en JSON."""
        if session_id not in self.histories:
            self.histories[session_id] = []

        # Tu lógica de validación y formato de mensaje
        if not isinstance(content, str):
             content = str(content) # Simplificado

        message = {
            "type": message_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if metadata:
            message["metadata"] = metadata

        self.histories[session_id].append(message)

        # *** Guardado inmediato (como lo tenías antes) ***
        # Desventaja: Lento por I/O en cada mensaje.
        # Ventaja: Simple, datos siempre actualizados en disco.
        self.save_full_history()
        # Considera mover self.save_full_history() fuera si quieres optimizar I/O
        # y llamarlo, por ejemplo, solo al final de la función answer()
    
    def get_windowed_memory_for_session(self, session_id: str) -> BaseChatMessageHistory:
        """Obtiene el backend de memoria windowed (limitada) para una sesión específica."""
        if session_id not in self.session_memory:
            # Creamos la memoria windowed si no existe para esta sesión
            print(f"Creando memoria windowed (k={self.memory_window_size}) para sesión: {session_id}")
            # Cargamos los últimos 'k * 2' mensajes del historial COMPLETO si existen
            # para inicializar la memoria windowed con algo de contexto.
            initial_messages = []
            if session_id in self.histories:
                full_session_history = self.histories[session_id]
                # Tomamos los últimos N mensajes (N = window_size * 2)
                last_n_messages = full_session_history[-(self.memory_window_size * 2):]
                for msg_data in last_n_messages:
                    content = msg_data.get("content", "")
                    if msg_data.get("type") == "human":
                        initial_messages.append(HumanMessage(content=content))
                    elif msg_data.get("type") == "assistant":
                        initial_messages.append(AIMessage(content=content))

            self.session_memory[session_id] = ConversationBufferWindowMemory(
                k=self.memory_window_size,
                memory_key="history",
                input_key="input",
                output_key="answer", # Clave donde buscará la respuesta del AI
                chat_memory=ChatMessageHistory(messages=initial_messages), # Inicializa con mensajes recientes
                return_messages=True
            )
        # Devolvemos el backend (ChatMessageHistory) que usa RunnableWithMessageHistory
        return self.session_memory[session_id].chat_memory

    def build_chain(self):
        history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever, self.QPromptTemplate())
        question_answer_chain = create_stuff_documents_chain(self.llm, self.APromptTemplate())
        return create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    def build_conversational_chain(self) -> RunnableWithMessageHistory:
         # self.rag_chain ya está construido en __init__
         return RunnableWithMessageHistory(
             self.rag_chain,
             self.get_windowed_memory_for_session, # Usa la memoria windowed
             input_messages_key="input",
             history_messages_key="history",
             output_messages_key="answer",
             history_factory_config=[
                 ConfigurableFieldSpec(
                     id="session_id",      # El nombre del argumento en tu función get_windowed_memory_for_session
                     annotation=str,       # El tipo de dato esperado (opcional pero bueno ponerlo)
                     name="session_id",      # Cómo se llamará esta configuración (usualmente igual a id)
                 )
             ]
         )
    
    def QPromptTemplate(self):
        return ChatPromptTemplate.from_messages([
            ("system", self.history_system()),
            MessagesPlaceholder("history"),
            ("human", "{input}"),	
        ])

    def history_system(self) -> str:
        return (
             "Dada una historia de chat y la última pregunta del usuario "
             "que podría hacer referencia al contexto en la historia de chat, "
             "formula una pregunta independiente que pueda ser entendida "
             "sin la historia de chat. NO respondas la pregunta, "
             "solo reformúlala si es necesario y, en caso contrario, devuélvela tal como está."
         )

    def APromptTemplate(self):
        """
        Construye el ChatPromptTemplate para la generación de respuestas,
        asegurando la correcta inyección de variables dinámicas como listaPrecio y context.
        """
        # Llama al método que devuelve el string del template del sistema
        system_template = self.answer_template()

        # Crea el ChatPromptTemplate usando from_messages
        prompt = ChatPromptTemplate.from_messages([
            # 1. Mensaje de Sistema: Usa from_template para permitir inyección de variables
            #    Langchain buscará 'listaPrecio' y 'context' en los datos de la cadena.
            SystemMessagePromptTemplate.from_template(system_template),

            # 2. Historial: Placeholder gestionado por RunnableWithMessageHistory
            MessagesPlaceholder(variable_name="history"),

            # 3. Entrada del Usuario: Usa from_template para la variable 'input'.
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        return prompt

    def answer_template(self) -> str:
        """
        Define y devuelve el string del prompt de sistema para la generación de respuestas.
        Este template espera que las variables {listaPrecio}, {context}, y {input}
        sean proporcionadas por el flujo de la cadena Langchain.
        """
        system_template_string = """
            Eres un asistente de ventas experto de CT. Tu objetivo es responder la consulta del usuario basándote EXCLUSIVAMENTE en los fragmentos de CONTEXTO proporcionados y la lista de precios asignada al usuario.

            **Información Clave:**
            - El usuario pertenece a la lista de precios identificada como: **{listaPrecio}**. Debes usar únicamente los precios correspondientes a esta lista que encuentres en el CONTEXTO.
            - Contexto recuperado con información de productos:
            --- CONTEXTO ---
            {context}
            --- FIN CONTEXTO ---

            **Instrucciones Detalladas:**

            1.  **Análisis de Producto y Precio (Basado en CONTEXTO y {listaPrecio}):**
                * Identifica el/los producto(s) relevantes del CONTEXTO para la consulta del usuario.
                * Para cada producto, busca su información de precio **correspondiente a la lista {listaPrecio}** y sus datos de promoción (`precio_oferta`, `descuento`, `EnCompraDE`, `Unidades`, `limitadoA`, `fecha_fin`) dentro del CONTEXTO.
                * **Prioridad:** Ofrece primero los productos que estén en promoción.

            2.  **Cálculo de Precio y Promoción:**
                * **Regla 1 (Precio Oferta):** Si el producto tiene `precio_oferta` > 0.0 en el CONTEXTO, ESE es el precio final. Menciónalo claramente.
                * **Regla 2 (Descuento):** Si `precio_oferta` es 0.0 Y `descuento` > 0.0, calcula el precio final aplicando el `descuento` al precio normal de la lista `{listaPrecio}` encontrado en el CONTEXTO. Muestra el precio original tachado y el precio con descuento (ej: ~~$1,200.00~~ **$1,080.00 (10% dto.)**).
                * **Regla 3 (Cantidad):** Si `precio_oferta` es 0.0 Y `descuento` es 0.0 Y `EnCompraDE` > 0 Y `Unidades` > 0, menciona la promoción por volumen de forma sutil (ej: "Promoción especial: En la compra de {{EnCompraDE}} unidades, recibe {{Unidades}} adicional(es) sin costo."). El precio a mostrar es el normal de la lista `{listaPrecio}`. 
                * **Precio Normal:** Si ninguna regla de promoción aplica, muestra el precio normal correspondiente a la lista `{listaPrecio}` encontrado en el CONTEXTO.

            3.  **Formato Obligatorio de Respuesta:**
                * Para CADA producto mencionado:
                    * Usa la `clave` del producto (del CONTEXTO) para generar un hipervínculo: `https://ctonline.mx/buscar/productos?b=[CLAVE]` (Reemplaza [CLAVE] con la clave real).
                    * **Nombre del Producto (con enlace):** `[Nombre del Producto](https://ctonline.mx/buscar/productos?b=[CLAVE])`
                    * **Precio Final:** (Calculado según reglas, formato $X,XXX.XX)
                    # --- CORRECCIÓN AQUÍ TAMBIÉN (Ejemplo de Promo) ---
                    * **Promoción (si aplica):** (ej: "Oferta especial!", "15% de descuento", "Promo Compra {{EnCompraDE}} Lleva {{Unidades}}", etc.) 
                    * **Detalles Adicionales (si aplica y están en CONTEXTO):** Menciona si la disponibilidad es `limitadoA` y la `fecha_fin` de la promoción.
                * Presenta la información de manera clara, estructurada (usa viñetas o párrafos separados por producto).
                * Sé conciso, evita explicaciones innecesarias. NO menciones explícitamente el nombre "{listaPrecio}" en la respuesta al usuario, solo úsala internamente para tus cálculos basados en el CONTEXTO.

            4.  **Notas Finales:**
                * Si el CONTEXTO no contiene información suficiente sobre un producto o su precio para la lista `{listaPrecio}`, indica que no puedes proporcionar esos detalles específicos. NO inventes información.
                * Siempre finaliza tu respuesta con la frase: "Recuerda que la disponibilidad y los precios pueden cambiar sin previo aviso."

            **Respuesta del Asistente:**
            """      
        return system_template_string


    async def answer(self, session_id: str, question: str, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Genera una respuesta usando memoria windowed y guarda historial completo."""
        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(
            self.model,
            token_cost_process=token_cost_process
        )

        full_answer = ""
        start_time = time.perf_counter()
        metadata = {}

        try:
            conversational_chain = self.build_conversational_chain()
            config = {"configurable": {"session_id": session_id}, "callbacks": [cost_handler]}

            # Guarda la pregunta del usuario en el historial COMPLETO
            self.add_message_to_full_history(session_id, "human", question) # <-- Guardado para análisis

            # Preparamos el input para Langchain. ¡Incluye listaPrecio aquí!
            chain_input = {"input": question, "listaPrecio": listaPrecio or ""} # Asegura que no sea None

            async for chunk in conversational_chain.astream(chain_input, config=config):
                chunk_answer = chunk.get("answer", "")
                if isinstance(chunk_answer, BaseMessage): # Puede ser AIMessage
                     chunk_content = chunk_answer.content
                elif isinstance(chunk_answer, str):
                     chunk_content = chunk_answer
                else:
                     chunk_content = str(chunk_answer) # Failsafe

                if chunk_content:
                    full_answer += chunk_content
                    yield chunk_content

            duration = time.perf_counter() - start_time
            metadata = self.make_metadata(token_cost_process, duration)

            # Guarda la respuesta COMPLETA del AI en el historial COMPLETO con metadata
            if full_answer:
                self.add_message_to_full_history(
                    session_id,
                    "assistant",
                    full_answer,
                    metadata # Añade la metadata al historial completo
                )
            else:
                 print(f"Advertencia: No se generó respuesta para sesión {session_id}, pregunta: {question}")
                 # Podrías guardar un mensaje indicando que no hubo respuesta si lo deseas
                 # self.add_message_to_full_history(session_id, "system", "[No Answer Generated]", metadata)


        except Exception as e:
            import traceback
            print(f"Error en answer para sesión {session_id}:")
            traceback.print_exc()
            # Guarda el error en el historial completo si quieres
            error_message = f"Error al procesar respuesta: {str(e)}"
            self.add_message_to_full_history(session_id, "system", f"ERROR: {error_message}\n{traceback.format_exc()}", {})
            yield error_message # Envía error al usuario

    def make_metadata(self, token_cost_process: TokenCostProcess, duration: float = None) -> dict:
        """Versión simplificada de metadata"""
        cost = token_cost_process.get_total_cost_for_model(self.model)
        
        metadata = {
            "cost_model": self.model, 
            "tokens": {
                "input": token_cost_process.input_tokens,
                "output": token_cost_process.output_tokens,
                "total": token_cost_process.total_tokens,
                "estimated_cost": cost
            },
            "duration": {
                "seconds": duration,
                "tokens_per_second": token_cost_process.total_tokens / duration if duration > 0 else 0
            }
        }
        return metadata   
