import os
import json
import time
from typing import AsyncGenerator
from datetime import datetime, timezone

from ct.llm import LLM
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler
from ct.clients import mongo_uri, mongo_collection_sessions, mongo_collection_message_backup

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from langchain_core.messages import trim_messages
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class LangchainAssistant:
    def __init__(self, retriever):
        llm_instance = LLM()
        self.llm, self.model = llm_instance.OpenAI()
        self.retriever = retriever

        try:
            self.client = MongoClient(mongo_uri).get_default_database()
            self.sessions = self.client[mongo_collection_sessions]
            self.message_backup = self.client[mongo_collection_message_backup]

            self.memory_window_size = 3000
            self.rag_chain = self.build_chain()

        except PyMongoError as e:
            raise
        except Exception as e:
            raise


    def get_session_history(self, session_id: str) -> list[BaseMessage]:
        messages_data = []
        try:
            session = self.sessions.find_one(
                {"session_id": session_id},
                {"last_messages": 1}
            )
            if session and "last_messages" in session:
                for m in session["last_messages"]:
                    if m["type"] == "human":
                        messages_data.append(HumanMessage(content=m["content"]))
                    elif m["type"] == "assistant":
                        messages_data.append(AIMessage(content=m["content"]))
        except PyMongoError as e:
            pass
        return messages_data
    
    def clear_session_history(self, session_id: str):
        try:
            self.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"last_messages": []}}
            )
            return True
        except PyMongoError as e:
            return False
        except Exception as e:
            return False

    def ensure_session(self, session_id: str):
        try:
            self.sessions.update_one(
                {"session_id": session_id},
                {"$setOnInsert": {"created_at": datetime.now(timezone.utc)},
                 "$set": {"last_activity": datetime.now(timezone.utc)}},
                upsert=True
            )
        except PyMongoError as e:
            pass
        except Exception as e:
            pass

    def build_chain(self):
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
        return (
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
            - La variable fecha_fin para aclarar la vigencia de la promoción, siempre aclara la vigencia.  

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

    async def answer(self, session_id: str, question: str, listaPrecio: str = None) -> AsyncGenerator[str, None]:
        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(
            self.model,
            token_cost_process=token_cost_process
        )

        full_answer = ""
        start_time = time.perf_counter()
        metadata = {}

        try:
            self.ensure_session(session_id)
            
            full_history = self.get_session_history(session_id)
            
            trimmed_history = trim_messages(
                full_history,
                token_counter=lambda messages: sum(len(m.content.split()) for m in messages),
                max_tokens=self.memory_window_size,
                strategy="last",
                start_on="human",
                include_system=True,
                allow_partial=False,
            )

            chain_input = {
                "input": question,
                "listaPrecio": listaPrecio,
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

            if full_answer:
                try:
                    self.add_message(session_id, "human", question)
                    self.add_message(session_id, "assistant", full_answer, metadata)

                    self.add_message_backup(session_id, question, full_answer, metadata)
                except Exception as e:
                    pass

        except PyMongoError as e:
            pass
        except Exception as e:
            pass
    
    def add_message(self, session_id: str, message_type: str, content: str, metadata: dict = None):
        timestamp = datetime.now(timezone.utc)

        try:
            short_msg = {
                "type": message_type,
                "content": str(content),
                "timestamp": timestamp
            }

            self.sessions.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "last_messages": {
                            "$each": [short_msg],
                            "$sort": {"timestamp": 1},
                            "$slice": -50  # Cambia este número según lo que quieras conservar
                        }
                    }
                }
            )

        except PyMongoError as e:
            pass
        except Exception as e:
            pass

    def add_message_backup(self, session_id: str, question: str, full_answer: str, metadata: dict):
        timestamp = datetime.now(timezone.utc)

        message_doc = {
            "session_id": session_id,
            "question": question,
            "answer": full_answer,
            "timestamp": timestamp,
            "input_tokens": metadata["tokens"]["input"],
            "output_tokens": metadata["tokens"]["output"],
            "total_tokens": metadata["tokens"]["total"],
            "estimated_cost": metadata["tokens"]["estimated_cost"],
            "duration_seconds": metadata["duration"]["seconds"],
            "tokens_per_second": metadata["duration"]["tokens_per_second"],
            "model_used": metadata["cost_model"]
        }

        try:
            self.message_backup.insert_one(message_doc)
        except PyMongoError as e:
            pass
        except Exception as e:
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
                "tokens_per_second": token_cost_process.total_tokens / duration if duration and duration > 0 else 0
            }
        }
        return metadata