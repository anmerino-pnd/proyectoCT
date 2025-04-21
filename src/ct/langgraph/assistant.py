from typing import TypedDict, List, Dict, AsyncGenerator
import os
import json
import time
from datetime import datetime, timezone

from ct.llm import LLM
from ct.config import HISTORY_FILE
from ct.tools.assistant import Assistant
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler

from langchain.agents import Tool
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferWindowMemory, ChatMessageHistory


from langgraph.prebuilt import create_react_agent

class LangGraphAssistant(Assistant):
    def __init__(
        self,
        retriever,
        history_file: str = HISTORY_FILE,
        memory_window_size: int = 3
    ):
        llm_instance = LLM()
        self.llm, self.model = llm_instance.OpenAI()  # O .Ollama()
        self.retriever = retriever

        self.memory_window_size = memory_window_size
        self.history_file = history_file
        self.session_memory: Dict[str, ConversationBufferWindowMemory] = {}
        self.histories: Dict[str, list] = self.load_histories()

    def _ensure_history_file(self):
        """Verifica si el archivo de historial existe, si no, lo crea vacío."""
        if not os.path.exists(self.history_file):
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True) # Asegura que el directorio exista
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

    def load_histories(self) -> Dict[str, List[Dict[str, str]]]:
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
    

    def add_message_to_full_history(self, session_id: str, type_: str, content: str):
        if session_id not in self.histories:
            self.histories[session_id] = []
        self.histories[session_id].append({"type": type_, "content": content})
        self.save_full_history()


    def build_react_agent(self, session_id: str,  listaPrecio: str):
        tools = [
            Tool()
        ]

        agent = create_react_agent(
            model=self.llm,
            tools=tools,
        )

        return RunnableWithMessageHistory(
            agent,
            get_session_history=lambda config: self.get_session_history(config["configurable"]["session_id"]),
            history_messages_key="messages",
            input_messages_key="input"
        )


    async def answer(self, session_id: str, question: str, listaPrecio: str = None) -> AsyncGenerator[str, None]:
        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(self.model, token_cost_process=token_cost_process)

        full_answer = ""
        start_time = time.perf_counter()
        metadata = {}

        try:
            agent_node = self.build_react_agent(session_id, listaPrecio)

            config = RunnableConfig(configurable={"session_id": session_id})

            result = await agent_node.ainvoke({"input": question}, config=config)
            answer_text = result.get("output", "")

            self.add_message_to_full_history(session_id, "human", question)
            self.add_message_to_full_history(session_id, "assistant", answer_text)

            full_answer += answer_text
            yield full_answer

        except Exception as e:
            yield f"Error al generar respuesta: {str(e)}"

        finally:
            elapsed = time.perf_counter() - start_time
            metadata.update({
                "model": self.model,
                "duration_seconds": elapsed,
            })