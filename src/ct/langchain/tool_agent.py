import time
import traceback
from toon import encode
from datetime import datetime, timezone
from ct.settings.prompt import prompt_dict
from ct.settings.schemas import UserContext
import logging

logger = logging.getLogger(__name__)

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.caches import InMemoryCache
from langchain_core.globals import get_llm_cache
from langchain_core.messages import trim_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage

from ct.tools.ct_info import who_are_we
from ct.tools.status import status_tool, StatusInput
from ct.tools.support import get_support_info, SupportInput
from ct.tools.inventory import inventory_tool, InventoryInput 
from ct.tools.algolia import algolia_search_tool, AlgoliaInput
from ct.tools.moneda_api import dolar_convertion_tool, DolarInput
from ct.tools.sales_rules_tool import sales_rules_tool, SalesInput
from ct.tools.sucursales import get_sucursales_info, SucursalesInput
from ct.tools.search_information import search_information_tool, search_by_key_tool, ClaveInput

from ct.settings.timing_tools import TimingCallbackHandler
from ct.settings.tokens import TokenCostProcess, MODEL_COST_PER_1K_TOKENS
from ct.settings.clients import (
    openai_api_key,
    gemini_api_key,
    mongo_uri, 
    mongo_collection_sessions, 
    mongo_collection_message_backup
)

timing_callback = TimingCallbackHandler()
token_cost_process = TokenCostProcess()

class ToolAgent:
    def __init__(self):
        self.model = "gemini-3-flash-preview"
        
        self.rate_limiter = InMemoryRateLimiter(
            requests_per_second=0.1,
            check_every_n_seconds=0.1,
            max_bucket_size=100,
        )

        self.llm = ChatGoogleGenerativeAI(
            model = self.model
        )

        # self.llm = ChatOpenAI(                    # En caso de volver a OpenAI
        #     model = self.model,
        #     rate_limiter = self.rate_limiter
        # )

        try:
            self.client = MongoClient(mongo_uri).get_default_database()
            self.sessions = self.client[mongo_collection_sessions]
            self.message_backup = self.client[mongo_collection_message_backup]

        except PyMongoError as e:
            raise
        except Exception as e:
            raise

        self.tools = [
            algolia_search_tool,
            sales_rules_tool,
            dolar_convertion_tool,
            status_tool,
            get_support_info,
            who_are_we,
            get_sucursales_info,
]
        self.graph = None

    def clear_session_history(self, session_id: str) -> bool:
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

    def build_graph(self):

        self.graph = create_agent(
            model= self.llm,
            tools= self.tools,
            system_prompt= encode(prompt_dict),
            context_schema=UserContext,
            cache=InMemoryCache()
            )

    async def run(self, query: str, session_id: str, lista_precio: int):
        full_history = self.get_session_history(session_id)
        chat_history = trim_messages(
            full_history,
            token_counter=lambda messages: sum(len(m.content.split()) for m in messages),
            max_tokens=4000,
            strategy="last",
            start_on="human",
            include_system=False,
            allow_partial=False,
        )

        start_time = time.perf_counter()

        if self.graph is None:
            self.build_graph()

        current_context = UserContext(
            session_id=session_id, 
            lista_precio=lista_precio
        )

        messages = chat_history + [HumanMessage(content=query)]

        inputs = {"messages": messages}

        full_answer = ""
        result = None

        try:
            result = await self.graph.ainvoke(
                inputs,
                context=current_context
                )
            last_message = result['messages'][-1]
            content = last_message.content

            if isinstance(content, str):
                full_answer = content
            elif isinstance(content, list):
                full_answer = "".join([part.get('text', '') for part in content if 'text' in part])
            else:
                full_answer = str(content)

            yield full_answer
        finally:
            duration = time.perf_counter() - start_time
            
            if result is not None and full_answer:
                try:
            
                    last_msg = result['messages'][-1]
                    usage_metadata = getattr(last_msg, 'usage_metadata', {}) or {}
                    
                    metadata = self.make_metadata(usage_metadata, duration)

                    verbose_log_str = self._generate_verbose_log(result['messages'])
                    
                    self.add_message(session_id, "human", query)
                    self.add_message(session_id, "assistant", full_answer)
                    self.add_message_backup(
                        session_id, 
                        query, 
                        full_answer, 
                        metadata,
                        verbose_log=verbose_log_str
                    )
                    
                except Exception as e:
                    print(f"❌ ERROR al guardar: {type(e).__name__}: {e}")
                    traceback.print_exc()

    def get_session_history(self, session_id: str) -> list[BaseMessage]: 
        messages_data = []
        try:
            session = self.sessions.find_one(
                {"session_id": session_id},
                {"last_messages": {"$slice": -15}}
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
            logger.error(f"Error crítico guardando en Mongo: {e}", exc_info=True)

    def add_message_backup(self, 
                           session_id: str, 
                           question: str, 
                           full_answer: str, 
                           metadata: dict,
                           verbose_log: str = ""):
        timestamp = datetime.now(timezone.utc)

        message_doc = {
            "session_id": session_id,
            "question": question,  
            "answer": full_answer,
            "verbose_log": verbose_log,
            "timestamp": timestamp,
            "input_tokens": metadata["tokens"]["input"],
            "output_tokens": metadata["tokens"]["output"],
            "total_tokens": metadata["tokens"]["total"],
            "cached_tokens": metadata['tokens']['cached_tokens'],
            "reasoning": metadata['tokens']['reasoning'],
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
            logger.error(f"Error crítico guardando en Mongo: {e}", exc_info=True)

    def add_irrelevant_message(self, session_id: str, question: str, full_answer: str):
        message_doc = {
            "session_id": session_id,
            "question": question,
            "answer": full_answer,
            "timestamp": datetime.now(timezone.utc),
            "label": False

        }
        self.message_backup.insert_one(message_doc)

    def make_metadata(self, usage_metadata: dict, duration: float = None) -> dict:
        if not usage_metadata:
            usage_metadata = {}
    
        input_tokens = usage_metadata.get('input_tokens', 0)
        output_tokens = usage_metadata.get('output_tokens', 0)
        total_tokens = usage_metadata.get('total_tokens', input_tokens + output_tokens)
        
        # Acceso seguro a diccionarios anidados
        input_details = usage_metadata.get('input_token_details', {})
        output_details = usage_metadata.get('output_token_details', {})
        
        cached_tokens = input_details.get('cache_read', 0)
        reasoning_tokens = output_details.get('reasoning', 0)

        # Obtener precios (con fallback)
        prices = MODEL_COST_PER_1K_TOKENS.get(self.model, {"input": 0.001, "output": 0.002})
    
        estimated_cost = (input_tokens / 1000) * prices['input'] + (output_tokens / 1000) * prices['output']

        metadata = { 
            "cost_model": self.model,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": total_tokens,
                "cached_tokens": cached_tokens,
                "reasoning": reasoning_tokens,
                "estimated_cost": round(estimated_cost, 6)
            },
            "duration": {
                "seconds": round(duration, 2) if duration else 0,
                "tokens_per_second": round(total_tokens / duration, 2) if duration and duration > 0 else 0
            }
        }
        return metadata

    def _generate_verbose_log(self, messages: list[BaseMessage]) -> str:
        log_buffer = []
        for msg in messages:
            # Verifica explícitamente si tiene tool_calls y que no esté vacío
            if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
                for tool_call in msg.tool_calls:
                    name = tool_call.get('name', 'Unknown Tool')
                    args = tool_call.get('args', {})
                    log_buffer.append(f"🤖 [Thinking] El asistente decidió usar: {name}")
                    log_buffer.append(f"   Args: {args}")
            
            elif isinstance(msg, ToolMessage): 
                tool_name = msg.name if msg.name else "Tool"
                log_buffer.append(f"🛠️ [Tool Output - {tool_name}]: {msg.content}")
        
        return "\n".join(log_buffer)