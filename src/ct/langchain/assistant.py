import os
import json
import time
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone

from ct.llm import LLM
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler
from ct.clients import mongo_uri, mongo_db, mongo_collection_history, mongo_collection_backup

from pymongo import MongoClient
from langchain_core.messages import trim_messages
from langchain_core.runnables import ConfigurableFieldSpec
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class LangchainAssistant:
    def __init__(self, retriever):
        llm_instance = LLM()
        self.llm, self.model = llm_instance.OpenAI()
        self.retriever = retriever

        self.client = MongoClient(mongo_uri)
        self.db = self.client[mongo_db]
        self.collection = self.db[mongo_collection_history]
        self.collection_backup = self.db[mongo_collection_backup]

        self.memory_window_size = 3  # número de mensajes o tokens permitidos

        self.rag_chain = self.build_chain()

    def get_session_history(self, session_id: str) -> list:
        """Devuelve el historial completo de mensajes desde MongoDB."""
        doc = self.collection.find_one({"session_id": session_id})
        messages = []
        if doc and "history" in doc:
            for m in doc["history"]:
                if m["type"] == "human":
                    messages.append(HumanMessage(content=m["content"]))
                elif m["type"] == "assistant":
                    messages.append(AIMessage(content=m["content"]))
        return messages

    def add_message_to_full_history(self, session_id: str, message_type: str, content: str, metadata: dict = None):
        """Agrega un mensaje al historial de MongoDB (por sesión) y hace backup."""
        message = {
            "type": message_type,
            "content": str(content),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if metadata:
            message["metadata"] = metadata

        # Actualiza la colección principal (reemplaza history completo)
        doc = self.collection.find_one({"session_id": session_id})
        history = doc["history"] if doc else []
        history.append(message)
        self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"history": history}},
            upsert=True
        )

        # En la colección de backup, simplemente agrega el mensaje al array (sin borrar lo viejo)
        self.collection_backup.update_one(
            {"session_id": session_id},
            {"$push": {"history": message}},
            upsert=True
        )

    def clear_session_history(self, session_id: str) :
        """Borra el historial de chat de un usuario SIN eliminar el documento ni cambiar el _id."""
        self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"history": []}}
        )
        return True

    def build_chain(self):
        """Construye la cadena de RAG con un retriever que tiene en cuenta el historial de chat."""
        history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever, self.QPromptTemplate())
        question_answer_chain = create_stuff_documents_chain(self.llm, self.APromptTemplate())
        return create_retrieval_chain(history_aware_retriever, question_answer_chain)

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
        system_template = self.answer_template()
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])

    def answer_template(self) -> str:
        tpl = (
            """
            Eres un asistente especializado exclusivamente en responder preguntas relacionadas con productos y promociones.
            Basate solo en los siguientes fragmentos de contexto para responder la consulta del usuario.

            El usuario pertenece a la listaPrecio {listaPrecio}, así que usa exclusivamente los precios de esta lista.
            No menciones la lista de precios en la respuesta, solo proporciona el precio final en formato de precio.

            Siempre aclara al final que la disponibilidad y los precios pueden cambiar.

            Contexto: {context}
            """
        )
        return tpl

    async def answer(self, session_id: str, question: str, listaPrecio: str = None) -> AsyncGenerator[str, None]:
        """Genera una respuesta usando historial recortado y guarda historial completo."""
        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(
            self.model,
            token_cost_process=token_cost_process
        )

        full_answer = ""
        start_time = time.perf_counter()
        metadata = {}

        try:
            # Recuperar historial completo
            full_history = self.get_session_history(session_id)

            # Recortar usando trim_messages
            trimmed_history = trim_messages(
                full_history,
                token_counter=len,  # reemplaza con tu propia función si quieres contar tokens
                max_tokens=self.memory_window_size,
                strategy="last",
                start_on="human",
                include_system=True,
                allow_partial=False,
            )

            chain_input = {
                "input": question,
                "listaPrecio": listaPrecio or "",
                "history": trimmed_history
            }

            config = {"configurable": {"session_id": session_id}, "callbacks": [cost_handler]}

            async for chunk in self.rag_chain.astream(chain_input, config=config):
                chunk_answer = chunk.get("answer", "")
                if isinstance(chunk_answer, BaseMessage):
                    chunk_content = chunk_answer.content
                elif isinstance(chunk_answer, str):
                    chunk_content = chunk_answer
                else:
                    chunk_content = str(chunk_answer)

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
            except Exception:
                pass

        except Exception:
            pass

    def make_metadata(self, token_cost_process: TokenCostProcess, duration: float = None) -> dict:
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
