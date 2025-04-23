from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from ct.openai.assistant import OpenAIAssistant
from ct.langchain.rag import LangchainRAG
from langchain.schema import HumanMessage
from typing import AsyncGenerator
from ct.clients import Clients
from pydantic import BaseModel
from ct.config import DATA_DIR

#assistant = OpenAIAssistant()

rag = LangchainRAG(DATA_DIR)
assistant = rag.assistant
clients = Clients()

class QueryRequest(BaseModel):
    user_query: str
    user_id: str
    cliente_clave: str 


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
        async for chunk in rag.run(request.user_query, request.user_id, request.cliente_clave):
            yield chunk  # Envía cada chunk al frontend de inmediato


async def async_chat_endpoint(request: QueryRequest):
    return StreamingResponse(async_chat_generator(request), media_type="text/event-stream")
