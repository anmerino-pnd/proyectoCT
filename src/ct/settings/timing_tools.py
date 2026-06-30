import time
import logging
from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class TimingCallbackHandler(BaseCallbackHandler):
    """Mide la latencia de cada tool durante un turno del agente.

    Pensado para usarse **una instancia por request** (se pasa en
    `config={"callbacks": [handler]}` al `astream`). Es seguro ante tools que
    corren en paralelo porque indexa por `run_id` en lugar de un único atributo
    compartido. No imprime a stdout (evita ruido bajo carga); deja traza en DEBUG.
    """

    def __init__(self) -> None:
        # run_id -> (tool_name, start_perf)
        self._in_flight: dict = {}
        # lista de {"tool": str, "seconds": float} en orden de finalización
        self.tool_timings: list[dict] = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        run_id = kwargs.get("run_id")
        name = (serialized or {}).get("name", "unknown_tool")
        self._in_flight[run_id] = (name, time.perf_counter())

    def on_tool_end(self, output, **kwargs):
        run_id = kwargs.get("run_id")
        name, start = self._in_flight.pop(run_id, (None, None))
        if start is None:
            return
        elapsed = round(time.perf_counter() - start, 4)
        self.tool_timings.append({"tool": name or "unknown_tool", "seconds": elapsed})
        logger.debug("tool %s -> %.3fs", name, elapsed)

    def on_tool_error(self, error, **kwargs):
        run_id = kwargs.get("run_id")
        name, start = self._in_flight.pop(run_id, (None, None))
        if start is None:
            return
        elapsed = round(time.perf_counter() - start, 4)
        self.tool_timings.append({"tool": name or "unknown_tool", "seconds": elapsed, "error": True})
        logger.debug("tool %s ERROR -> %.3fs (%s)", name, elapsed, error)

    # --- Resúmenes para persistir / inspeccionar ---
    def summary(self) -> dict:
        """Agrega por tool: nº de llamadas y segundos totales."""
        agg: dict = {}
        for t in self.tool_timings:
            slot = agg.setdefault(t["tool"], {"calls": 0, "seconds": 0.0})
            slot["calls"] += 1
            slot["seconds"] = round(slot["seconds"] + t["seconds"], 4)
        return agg
