from pathlib import Path
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse
from ct.openai.assistant import OpenAIAssistant
from ct.langchain.rag import LangchainRAG
from langchain.schema import HumanMessage
from typing import AsyncGenerator
from ct.clients import Clients
from pydantic import BaseModel
from ct.config import DATA_DIR

import logging # Importar módulo logging

# Obtener logger para este módulo
logger = logging.getLogger(__name__)

#assistant = OpenAIAssistant()

rag = LangchainRAG(DATA_DIR)
assistant = rag.assistant
clients = Clients()

class QueryRequest(BaseModel):
    user_query: str
    user_id: str
    listaPrecio: str 


# En chat.py
def get_chat_history(user_id: str):
    """Devuelve el historial de chat de un usuario en formato JSON."""
    print(f"🔍 Buscando historial para user_id: '{user_id}'")
    history = assistant.get_session_history(user_id)
    
    if not history.messages:
        print("⚠️ No hay mensajes en el historial")  # Debug 3
        return []

    return [{"role": "user" if isinstance(msg, HumanMessage) else "bot", "content": msg.content} for msg in history.messages]


async def async_chat_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
        async for chunk in rag.run(request.user_query, request.user_id, request.listaPrecio):
            yield chunk  # Envía cada chunk al frontend de inmediato


async def async_chat_endpoint(request: QueryRequest):
    return StreamingResponse(async_chat_generator(request), media_type="text/event-stream")

async def delete_chat_history_endpoint(user_id: str):
    """
    Endpoint para eliminar el historial de chat de un usuario.
    Responde 204 No Content si se elimina o si no existía (operación idempotente).
    """
    user_id_normalized = user_id.lower() # Normaliza igual que en handle_history
    try:
        # Llama al nuevo método del asistente
        session_deleted = assistant.clear_session_history(user_id_normalized)

        if session_deleted:
            logger.info(f"✅ Historial eliminado exitosamente para user_id: '{user_id_normalized}'.")
        else:
             logger.info(f"ℹ️ Intentando eliminar historial para user_id: '{user_id_normalized}', pero no se encontró.")


        return Response(status_code=204)


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar historial: {e}") # Informar al cliente

