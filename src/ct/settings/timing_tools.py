import time
from langchain.callbacks.base import BaseCallbackHandler

class TimingCallbackHandler(BaseCallbackHandler):
    """Callback para medir tiempos de ejecución de cada herramienta."""

    def __init__(self):
        self.tool_timings = []

    def on_llm_start(self, *args, **kwargs):
        self.run_start = time.time()
        print("🚀 Inicio de ejecución del agente")

    def on_llm_end(self, *args, **kwargs):
        total = time.time() - self.run_start
        print(f"🏁 Fin de ejecución del agente — Total {total:.2f}s\n")

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.current_tool = serialized.get("name", "unknown_tool")
        self.start_time = time.time()
        print(f"🧩 [Inicio] {self.current_tool} → {input_str[:60]}")

    def on_tool_end(self, output, **kwargs):
        elapsed = time.time() - getattr(self, "start_time", time.time())
        tool_name = getattr(self, "current_tool", "unknown_tool")
        self.tool_timings.append((tool_name, elapsed))
        print(f"\n✅ [Fin] {tool_name} — {elapsed:.2f}s")