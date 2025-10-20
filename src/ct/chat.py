from typing import AsyncGenerator
from fastapi import HTTPException
from langchain.schema import HumanMessage
from ct.settings.clients import QueryRequest
from fastapi.responses import StreamingResponse
from ct.langchain.moderated_tool_agent import ModeratedToolAgent


assistant = ModeratedToolAgent()


def get_chat_history(user_id: str):
    """Devuelve el historial de chat de un usuario en formato JSON."""
    history = assistant.tool_agent.get_session_history(user_id)
    
    if not history:
        return []

    return [{"role": "user" if isinstance(msg, HumanMessage) else "bot", "content": msg.content} for msg in history]

async def async_chat_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
        async for chunk in assistant.run(request.user_query, request.user_id, request.listaPrecio):
            yield chunk  

async def async_chat_endpoint(request: QueryRequest):
    return StreamingResponse(async_chat_generator(request), media_type="text/event-stream")

async def delete_chat_history_endpoint(user_id: str):
    """
    Endpoint para eliminar el historial de chat de un usuario.
    Responde 204 No Content si se elimina o si no existía (operación idempotente).
    """
    try:
        assistant.tool_agent.clear_session_history(user_id)

        return "success"


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar historial: {e}") # Informar al cliente
