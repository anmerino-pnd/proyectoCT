import re
import yaml
import time
from datetime import datetime, timezone
from ct.settings.prompt import prompt_dict

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from cachetools import TTLCache
from langchain.globals import set_llm_cache
from langchain.tools import Tool, StructuredTool 
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import trim_messages
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.cache import InMemoryCache, SQLiteCache, GPTCache, RedisCache, RedisSemanticCache
from langchain.agents import create_openai_functions_agent, AgentExecutor, create_tool_calling_agent

from ct.tools.ct_info import who_are_we
from ct.tools.status import status_tool, StatusInput
from ct.tools.support import get_support_info, SupportInput
from ct.tools.inventory import inventory_tool, InventoryInput 
from ct.tools.moneda_api import dolar_convertion_tool, DolarInput
from ct.tools.sales_rules_tool import sales_rules_tool, SalesInput
from ct.tools.sucursales import get_sucursales_info, SucursalesInput
from ct.tools.search_information import search_information_tool, search_by_key_tool, ClaveInput

from ct.settings.config import DATA_DIR
from ct.settings.clients import openai_api_key
from ct.settings.tokens import TokenCostProcess, CostCalcAsyncHandler
from ct.settings.clients import mongo_uri, mongo_collection_sessions, mongo_collection_message_backup

system_prompt = yaml.dump(prompt_dict, allow_unicode=True, sort_keys=False)
        
class ToolAgent:
    def __init__(self):
        self.model = "gpt-4.1"
        
        self.rate_limiter = InMemoryRateLimiter(
            requests_per_second=0.1,
            check_every_n_seconds=0.1,
            max_bucket_size=100,
        )

        self.llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model_name=self.model,
            rate_limiter=self.rate_limiter,
            cache=True
            )
        try:
            self.client = MongoClient(mongo_uri).get_default_database()
            self.sessions = self.client[mongo_collection_sessions]
            self.message_backup = self.client[mongo_collection_message_backup]

        except PyMongoError as e:
            raise
        except Exception as e:
            raise

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt
            ),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])

        self.tools = [
            Tool(
                name='search_information_tool',
                func=search_information_tool.invoke,
                description="Busca productos, o información de productos mencionados, una búsqueda más general de lo que se puede encontrar en la empresa"
            ),
            StructuredTool.from_function(
                func=inventory_tool,
                name='inventory_tool',
                description="Esta herramienta sirve como referencia y devuelve precios, moneda y existencias de un producto por su clave y listaPrecio",
                args_schema=InventoryInput 
            ),
            StructuredTool.from_function(
                func=sales_rules_tool,
                name='sales_rules_tool',
                description="Aplica reglas de promoción, devuelve el precio final y mensaje para mostrar al usuario",
                args_schema=SalesInput
        ),
            StructuredTool.from_function(
                func=dolar_convertion_tool,
                name='dolar_convertion_tool',
                description="Solo usa la tool para convertir el precio de un producto de USD a MXN y hacer cuentas",
                args_schema=DolarInput
        ),
            StructuredTool.from_function(
                func=status_tool,
                name='status_tool',
                description="Cuando pregunten por el estatus de algún pedido hecho, pide la factura y busca dicho estatus y no ofrezcas más detalles, solo los regresados por la tool",
                args_schema=StatusInput
        ),
            StructuredTool.from_function(
                func=search_by_key_tool,
                name="search_by_key_tool",
                description="Busca en el docstore un producto o promoción EXACTA usando su clave CT, una sola clave en mayusculas. Búsqueda más específica",
                args_schema=ClaveInput
        ),
            StructuredTool.from_function(
                func=get_support_info,
                name="get_support_info",
                description="Cuando necesites saber sobre cómo hacer compras en líneas, compras y envíos de ESD, políticas, garantías, devoluciones, términos y condiciones",
                args_schema=SupportInput
        ),
            StructuredTool.from_function(
                func=who_are_we,
                name="who_are_we",
                description="SIEMPRE que te pregunten por CT y quién es, qué es, valores, etc., usa esta herramienta.",
        ),
            StructuredTool.from_function(
                func=get_sucursales_info,
                name="get_sucursales_info",
                description="Código Python para analizar el DataFrame 'df' con información de las sucursales. Debe usar print() para mostrar resultados o asignar el resultado a la variable 'result'.",
                args_schema=SucursalesInput
            )
]

        self.executor = None

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

    def ensure_session(self, session_id: str) -> dict:
        now = datetime.now(timezone.utc)
        self.sessions.update_one(
            {"session_id": session_id},
            {
                "$setOnInsert": {"created_at": now},
                "$set": {"last_activity": now}
            },
            upsert=True
        )
        # 👉 retornar directamente la sesión actualizada
        return self.sessions.find_one({"session_id": session_id}) or {}

    def build_executor(self):
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        self.executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=40,
            return_intermediate_steps=False
        )

    async def run(self, query: str, session_id: str, lista_precio: int):
        full_history = self.get_session_history(session_id)
        chat_history = trim_messages(
            full_history,
            token_counter=lambda messages: sum(len(m.content.split()) for m in messages),
            max_tokens=800,
            strategy="last",
            start_on="human",
            include_system=True,
            allow_partial=False,
        )

        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(
            self.model,
            token_cost_process=token_cost_process
        )
        start_time = time.perf_counter()

        if self.executor is None:
            self.build_executor()

        inputs = {
            "input": query,
            "chat_history": chat_history,
            "listaPrecio": lista_precio,
            "session_id" : session_id
        }

        full_answer = ""

        try:
            async for output in self.executor.astream(inputs, config={"callbacks": [cost_handler]}):
                content = output.get("output", "")
                full_answer += content
                yield content
        finally:
            duration = time.perf_counter() - start_time
            metadata = self.make_metadata(token_cost_process, duration)

            if full_answer:
                try:
                    self.add_message(session_id, "human", query)
                    self.add_message(session_id, "assistant", full_answer)
                    self.add_message_backup(session_id, query, full_answer, metadata)
                except Exception:
                    pass

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

    def add_message(self, session_id: str, message_type: str, content: str):
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
                            "$slice": -24  
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
            "model_used": metadata["cost_model"],
            "label": True
        }

        try:
            self.message_backup.insert_one(message_doc)
        except PyMongoError as e:
            pass
        except Exception as e:
            pass

    def add_irrelevant_message(self, session_id: str, question: str, full_answer: str):
        message_doc = {
            "session_id": session_id,
            "question": question,
            "answer": full_answer,
            "timestamp": datetime.now(timezone.utc),
            "label": False

        }
        self.message_backup.insert_one(message_doc)

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
