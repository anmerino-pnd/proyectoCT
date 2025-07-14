import time
from langchain_openai import ChatOpenAI
from ct.langchain.existences import existences
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import trim_messages
from ct.langchain.assistant import LangchainAssistant
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.tools import Tool



class ToolAgent:
    def __init__(self, assistant: LangchainAssistant):
        self.model = "gpt-4.1"
        self.assistant = assistant
    
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
            "Eres un asistente que usa herramientas para informar sobre productos. "
            "No puedes hacer compras, apartados ni pedidos. "
            "Solo da respuestas claras y precisas, sin agregar más de lo que devuelve la herramienta. "
            "Aclara que disponibilidad y precios pueden cambiar.")
            ,
            ("system", "Historial de conversación:\n{chat_history}"),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])

        self.llm = assistant.llm

        self.executor = None  # Se inicializa solo si se necesita

        self.tools = [
            Tool(
                name= 'existencias_tool',
                func = existences.invoke,
                description=(
                "Usa esta herramienta exclusivamente para decirle al usuario cuántas unidades hay disponibles de un producto. "
                "Úsala solo si el usuario pregunta por una cantidad específica como: '¿cuántas tienen?', '¿quedan 10?', "
                "'¿hay más de 3?'."
            )
            )
        ]

    def build_executor(self):
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        self.executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            verbose=False
        )

    async def run_existencias(self, query: str, session_id: str = "default_session"):
        """Ejecuta el agente de existencias con cálculo de costo y registro"""

        # Trim de historial
        full_history = self.assistant.get_session_history(session_id)
        chat_history = trim_messages(
            full_history,
            token_counter=lambda messages: sum(len(m.content.split()) for m in messages),
            max_tokens=3000,
            strategy="last",
            start_on="human",
            include_system=True,
            allow_partial=False,
        )

        # Callback de costos y temporizador
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
            "chat_history": chat_history
        }

        full_answer = ""

        try:
            async for output in self.executor.astream(inputs, config={"callbacks": [cost_handler]}):
                content = output.get("output", "")
                full_answer += content
                yield content

        finally:
            duration = time.perf_counter() - start_time
            metadata = self.assistant.make_metadata(token_cost_process, duration)

            # Guardar conversación si hubo respuesta
            if full_answer:
                try:
                    self.assistant.add_message(session_id, "human", query)
                    self.assistant.add_message(session_id, "assistant", full_answer, metadata)
                    self.assistant.add_message_backup(session_id, query, full_answer, metadata)
                except Exception:
                    pass
