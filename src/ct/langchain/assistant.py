import os
import json
import time
from typing import AsyncGenerator, Dict
from datetime import datetime, timezone

from ct.llm import LLM
from ct.config import HISTORY_FILE, BACKUP_HISTORY_FILE
from ct.tools.assistant import Assistant
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler

from langchain_core.runnables import ConfigurableFieldSpec
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.schema import AIMessage, HumanMessage, BaseMessage 
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import ChatMessageHistory

from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class LangchainAssistant(Assistant):
    def __init__(self, retriever):
        llm_instance = LLM()
        self.llm, self.model = llm_instance.OpenAI()  # O .Ollama()
        self.retriever = retriever

        self.history_file = HISTORY_FILE
        self.backup_history_file = BACKUP_HISTORY_FILE
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
        
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Obtiene el historial de una sesión específica y lo convierte en BaseChatMessageHistory."""
        if session_id not in self.histories:
            self.histories[session_id] = []

        messages = [
            HumanMessage(content=m["content"]) if m["type"] == "human" else AIMessage(content=m["content"])
            for m in self.histories[session_id]
        ]
        return ChatMessageHistory(messages=messages)
        
    def save_full_history(self):
        """Guarda el diccionario COMPLETO de historiales en el archivo JSON."""
        # Esta función podría llamarse periódicamente o al cerrar la app
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.histories, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial completo en {self.history_file}: {e}")
    
    def backup_full_history(self):
        """Copia de seguridad del historial completo en un archivo JSON separado."""
        try:
            with open(self.backup_history_file, "w", encoding="utf-8") as f:
                json.dump(self.histories, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar la copia de seguridad del historial: {e}")

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


        self.save_full_history()
        self.backup_full_history()
    
    def clear_session_history(self, session_id: str) -> bool:
        """
        Elimina el historial de una sesión específica tanto de la memoria
        en ejecución como del archivo JSON.

        Retorna True si la sesión existía y fue eliminada, False si no existía.
        """

        history_existed = session_id in self.histories

        if history_existed:
            self.histories[session_id] = []  
               
            self.save_full_history()
            return True
        else:
            return False 
    
    def get_windowed_memory_for_session(self, session_id: str) -> BaseChatMessageHistory:
        """Obtiene el backend de memoria windowed (limitada) para una sesión específica."""
        if session_id not in self.session_memory:
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
        system_template = self.answer_template()

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        return prompt

    def answer_template(self) -> str:
        """
        Define y devuelve el string del prompt de sistema para la generación de respuestas.
        Este template espera que las variables {listaPrecio}, {context}, y {input}
        sean proporcionadas por el flujo de la cadena Langchain.
        """
        
        tpl = (
        """
        Eres un asistente especializado exclusivamente en responder preguntas relacionadas con productos y promociones.
        
        Basate solo en los siguientes fragmentos de contexto para responder la consulta del usuario.  

        El usuario pertenece a la listaPrecio {listaPrecio}, así que usa exclusivamente los precios de esta lista. 
        No menciones la lista de precios en la respuesta, solo proporciona el precio final en formato de precio (por ejemplo, $1,000.00).  
        Para el valor de la moneda, si moneda es 1, usa "MXN", si es 0, usa "USD".

        Si hay productos en oferta, menciónalos primero. 
        Si no hay promociones, ofrece los productos normales con su precio correcto.  
        Si el usuario pregunta por un producto específico, verifica si está en promoción y notifícalo.  

        Para que un producto se considere en promoción debe tener las variables de precio_oferta, descuento, EnCompraDE y Unidades.
        Luego, estas deben cumplir las siguientes condiciones:

        1. Si el producto tiene un precio_oferta mayor a 0.0:  
            - Usa este valor como el precio final y ofrécelo al usuario. 

        2. Si el precio_oferta es 0, pero el descuento es mayor a 0.0%:  
            - Aplica el descuento al precio que se encuentra en lista_precios y toma el precio correspondiente a la listaPrecio {listaPrecio}.  
            - Muestra ese precio tachado y el nuevo precio con el descuento aplicado.  

        3. Si el precio_oferta y el descuento son 0.0, pero la variable EnCompraDE es mayor a 0 y Unidades es mayor a 0:  
            - Menciona que hay una promoción especial al comprar cierta cantidad.  
            - Usa un tono sutil, por ejemplo: "En compra de 'X' productos, recibirás 'Y' unidades gratis."  

        Revisa también:  
            - La variable limitadoA para indicar si la disponibilidad es limitada.  
            - La variable fecha_fin para aclarar la vigencia de la promoción.  

        Formato de respuesta, SIEMPRE:  
        - Para cada producto que ofrezcas:
            * Toma el valor de la variable 'clave' 
            * Resalta el nombre poniendo su hipervinculo https://ctdev.ctonline.mx/buscar/productos?b=clave
        - Presenta la información de manera clara
        - Los detalles y precios puntualizados y estructurados 
        - Espacios entre productos.         
        - Evita explicaciones largas o innecesarias.  

        Siempre aclara al final que la disponibilidad y los precios pueden cambiar.  

        Contexto: {context}  
        """
            )
        return tpl


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

            chain_input = {"input": question, "listaPrecio": listaPrecio or ""} 

            async for chunk in conversational_chain.astream(chain_input, config=config):
                chunk_answer = chunk.get("answer", "")
                if isinstance(chunk_answer, BaseMessage): 
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

            try:
                self.add_message_to_full_history(session_id, "human", question) 
                
                if full_answer:
                    self.add_message_to_full_history(
                        session_id,
                        "assistant",
                        full_answer,
                        metadata
                    )
            except Exception as e:
                pass

        except Exception as e:
            pass
            

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
