"""
Modelo LLM falso para pruebas de carga locales (F3).

Se inyecta SOLO cuando `CT_FAKE_LLM=1`. Reemplaza a ChatOpenAI en el agente para
ejercer la infra real (event loop, threadpool, MySQL/Mongo, SSE, persistencia) sin
costo ni rate limit de OpenAI. Emite un stream de tokens canónico con latencia
asíncrona configurable (simula el tiempo de generación del LLM real):

    CT_FAKE_LLM=1               activa el modo
    CT_FAKE_LLM_TOKENS=120      nº de tokens a emitir (default 120)
    CT_FAKE_LLM_TPS=40          tokens por segundo simulados (default 40)
    CT_FAKE_LLM_TTFT_MS=300     time-to-first-token en ms (default 300)

No emite tool-calls: mide el camino del request (incluida la persistencia Mongo en
el event loop), que es la hipótesis principal de escalabilidad. `bind_tools` se
acepta y se ignora para ser compatible con `create_agent`.
"""
from __future__ import annotations
import os
import asyncio
from typing import Any, AsyncIterator, Iterator, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class FakeStreamingChatModel(BaseChatModel):
    """LLM falso que stremea una respuesta canónica con latencia simulada."""

    answer: str = (
        "Claro, con gusto te ayudo. Esta es una respuesta de prueba generada por el "
        "modelo simulado para medir la capacidad del servidor bajo carga concurrente, "
        "sin llamar a OpenAI ni consumir tokens reales."
    )
    n_tokens: int = 120
    tokens_per_second: float = 40.0
    ttft_ms: int = 300

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Releer de entorno en cada instancia (permite ajustar sin redeploy).
        self.n_tokens = _cfg_int("CT_FAKE_LLM_TOKENS", 120)
        self.tokens_per_second = float(_cfg_int("CT_FAKE_LLM_TPS", 40))
        self.ttft_ms = _cfg_int("CT_FAKE_LLM_TTFT_MS", 300)

    @property
    def _llm_type(self) -> str:
        return "fake-streaming-chat-model"

    def bind_tools(self, tools: Any = None, **kwargs: Any) -> "FakeStreamingChatModel":
        # create_agent llama bind_tools; en modo fake ignoramos las tools.
        return self

    def _tokens(self) -> list[str]:
        base = self.answer.split(" ")
        out: list[str] = []
        i = 0
        while len(out) < self.n_tokens:
            out.append(base[i % len(base)] + " ")
            i += 1
        return out

    def _generate(self, messages, stop=None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None,
                  **kwargs: Any) -> ChatResult:
        text = "".join(self._tokens())
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _astream(self, messages, stop=None,
                       run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
                       **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        await asyncio.sleep(self.ttft_ms / 1000.0)
        delay = 1.0 / self.tokens_per_second if self.tokens_per_second > 0 else 0.0
        for tok in self._tokens():
            yield ChatGenerationChunk(message=AIMessageChunk(content=tok))
            if delay:
                await asyncio.sleep(delay)

    def _stream(self, messages, stop=None,
                run_manager: Optional[CallbackManagerForLLMRun] = None,
                **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        for tok in self._tokens():
            yield ChatGenerationChunk(message=AIMessageChunk(content=tok))


def fake_llm_enabled() -> bool:
    return os.getenv("CT_FAKE_LLM") == "1"
