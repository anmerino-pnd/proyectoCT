import time
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from langchain.tools import Tool, StructuredTool # Import StructuredTool
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import trim_messages
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain.agents import create_openai_functions_agent, AgentExecutor

from ct.settings.clients import openai_api_key
from ct.tools.existences import existencias_tool, ExistenciasInput # Import ExistenciasInput
from ct.settings.tokens import TokenCostProcess, CostCalcAsyncHandler
from ct.tools.search_information import search_information_tool
from ct.settings.clients import mongo_uri, mongo_collection_sessions, mongo_collection_message_backup


class ToolAgent:
    def __init__(self):
        self.model = "gpt-4.1"

        try:
            self.client = MongoClient(mongo_uri).get_default_database()
            self.sessions = self.client[mongo_collection_sessions]
            self.message_backup = self.client[mongo_collection_message_backup]

        except PyMongoError as e:
            raise
        except Exception as e:
            raise

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
            """
Eres un asistente experto en ofrecer y recomendar productos y promociones. Respondes usando herramientas.

Cuando un usuario solicite un producto, primero usa 'search_information_tool' para buscar productos y después 'existencias_tool' para información extra.
Cuando el usuario solicite algo general o te pide ayuda para encontrar productos pero sin ser específico, primero genera una lista breve con los componentes clave.
Después, usa esa lista como guía para buscar productos reales con 'search_information_tool'.
Luego, para cada producto encontrado, llama a 'existencias_tool' usando los argumentos nombrados `clave` y `listaPrecio` por separado.
Ejemplo correcto de uso: existencias_tool(clave='CLAVE_DEL_PRODUCTO', listaPrecio={listaPrecio})

IMPORTANTE: SOLO si consideras que los productos `Promociones` son relevantes a la consulta del usuario, itera y aplica para CADA uno:

1. Si `precio_oferta` es mayor a 0.0: 
- SOLO muestralo como el precio final, sustituyelo por el precio original

2. Si `descuento` es mayor a 0.0%:
- Toma el precio original de 'existencias_tool' y aplicale el descuento mencionado

3. Si `EnCompraDe` y `Unidades` son mayor a 0.0:
- Menciona la promoción de compra en cantidad, por ejemplo:
    - En compra de X unidades, recibirás Y gratis
- Usa un tono breve y amable

4. Siempre revisa:
- Si el campo `limitadoA` está presente, menciona que la disponibilidad es limitada
- Usa el campo `fecha_fin` para aclarar la vigencia de la promoción
    - Este dato debe mostrarse siempre que haya promoción

Formato de respuesta SIEMPRE:
Presenta los productos en formato claro, ordenado, usando bullet points y usa Markdown:
- Nombre del producto como hipervínculo: [NOMBRE](https://ctonline.mx/buscar/productos?b=CLAVE)
- Muestra el precio con símbolo $ y la moneda (MXN o USD) SIEMPRE
- Informa la disponibilidad
- No uses párrafos largos pero da detalles
- No ofrezcas más de lo que se te pide
- No expliques más de lo necesario

SIEMPRE ACLARA:  
_Los precios y existencias están sujetos a cambios._

Historial:
{chat_history}
            """
            ),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])

        self.tools = [
            Tool(
                name='search_information_tool',
                func=search_information_tool,
                description="Busca productos relacionados con lo que se pide."
            ),
            # Changed to StructuredTool for better argument parsing
            StructuredTool.from_function(
                func=existencias_tool,
                name='existencias_tool',
                description="Esta herramienta sirve como referencia y devuelve precios, moneda y existencias de un producto por su clave y listaPrecio.",
                args_schema=ExistenciasInput # Explicitly link the Pydantic schema
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
        agent = create_openai_functions_agent(
            llm=ChatOpenAI(
                openai_api_key=openai_api_key,
                model_name=self.model,
                temperature=0.0,
                streaming=True,
            ),
            tools=self.tools,
            prompt=self.prompt
        )
        self.executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=40
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
            "listaPrecio": lista_precio
        }

        full_answer = ""

        try:
            async for output in self.executor.astream(inputs, config={"callbacks": [cost_handler]}):
                content = output.get("output", "")
                print(content)
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
