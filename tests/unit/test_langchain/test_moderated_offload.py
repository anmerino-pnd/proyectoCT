"""Smoke test del orquestador tras mover las llamadas Mongo síncronas a
`asyncio.to_thread`. Verifica que el cableado async sigue funcionando: las
funciones síncronas (ensure_session, check_if_banned, find_one,
update_inappropriate_session, add_irrelevant_message) se ejecutan vía hilo y el
generador async produce los chunks correctos en cada rama de moderación.

Se evita el __init__ pesado (ChatOpenAI/MongoClient) construyendo la instancia
con __new__ e inyectando mocks.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from ct.langchain.moderated_tool_agent import ModeratedToolAgent

pytestmark = pytest.mark.unit


def _make_agent():
    agent = ModeratedToolAgent.__new__(ModeratedToolAgent)
    agent.tool_agent = MagicMock()
    agent.moderator = MagicMock()
    return agent


async def _collect(async_gen):
    return [chunk async for chunk in async_gen]


async def test_rama_relevante_streamea(monkeypatch):
    agent = _make_agent()
    agent.tool_agent.ensure_session = MagicMock(return_value={})           # síncrono → to_thread
    agent.moderator.check_if_banned = MagicMock(return_value=None)         # síncrono → to_thread
    agent.moderator.classify_query = AsyncMock(return_value="relevante")

    async def _fake_run(query, session_id, lista_precio):
        yield "hola "
        yield "mundo"
    agent.tool_agent.run = _fake_run

    out = await _collect(agent.run("busca laptop", "HMO_u1", "1"))
    assert out == ["hola ", "mundo"]
    agent.tool_agent.ensure_session.assert_called_once_with("HMO_u1")


async def test_rama_baneado_corta():
    agent = _make_agent()
    agent.tool_agent.ensure_session = MagicMock(return_value={})
    agent.moderator.check_if_banned = MagicMock(return_value="Estás baneado")
    agent.moderator.classify_query = AsyncMock(return_value="relevante")

    out = await _collect(agent.run("hola", "HMO_u1", "1"))
    assert out == ["Estás baneado"]
    # No debe intentar clasificar si ya está baneado.
    agent.moderator.classify_query.assert_not_called()


async def test_rama_irrelevante_persiste_via_hilo():
    agent = _make_agent()
    agent.tool_agent.ensure_session = MagicMock(return_value={})
    agent.moderator.check_if_banned = MagicMock(return_value=None)
    agent.moderator.classify_query = AsyncMock(return_value="irrelevante")
    agent.moderator.polite_answer = MagicMock(return_value="Solo tecnología 😊")
    agent.tool_agent.add_irrelevant_message = MagicMock()

    out = await _collect(agent.run("cómo cocino pollo", "HMO_u1", "1"))
    assert out == ["Solo tecnología 😊"]
    agent.tool_agent.add_irrelevant_message.assert_called_once()


async def test_rama_inapropiado_actualiza_via_hilo():
    agent = _make_agent()
    agent.tool_agent.ensure_session = MagicMock(return_value={})
    agent.moderator.check_if_banned = MagicMock(return_value=None)
    agent.moderator.classify_query = AsyncMock(return_value="inapropiado")
    agent.tool_agent.sessions = MagicMock()
    agent.tool_agent.sessions.find_one = MagicMock(return_value={})
    agent.moderator.evaluate_inappropriate_behavior = MagicMock(
        return_value=("Lenguaje inapropiado", 2, None)
    )
    agent.moderator.update_inappropriate_session = MagicMock()

    out = await _collect(agent.run("insulto", "HMO_u1", "1"))
    assert out == ["Lenguaje inapropiado"]
    agent.moderator.update_inappropriate_session.assert_called_once()
