from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from ct.openai.assistant import OpenAIAssistant
from ct.langchain.rag import LangchainRAG
from langchain.schema import HumanMessage
from typing import AsyncGenerator
from ct.clients import Clients
from pydantic import BaseModel

#assistant = OpenAIAssistant()
rag = LangchainRAG(r"C:\Users\angel.merino\Documents\proyectoCT\datos\productos_promociones_CT")
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


#async def async_chat_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
#    try:
#        listaPrecio = clients.get_lista_precio(request.cliente_clave)
#        if not listaPrecio:
#            raise HTTPException(status_code=400, detail="Clave no válida. Verifique e intente de nuevo.")
#        
#        async for chunk in assistant.async_offer(request.user_query, request.user_id, listaPrecio):
#            yield chunk  # Envía cada chunk al frontend de inmediato
#            
#    except Exception as e:
#        yield f"Error: {str(e)}"

async def async_chat_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
    try:
        listaPrecio = clients.get_lista_precio(request.cliente_clave)
        if not listaPrecio:
            raise HTTPException(status_code=400, detail="Clave no válida. Verifique e intente de nuevo.")
        
        async for chunk in rag.run(request.user_query, request.user_id, listaPrecio):
            yield chunk  # Envía cada chunk al frontend de inmediato
            
    except Exception as e:
        yield f"Error: {str(e)}"


async def async_chat_endpoint(request: QueryRequest):
    return StreamingResponse(async_chat_generator(request), media_type="text/event-stream")
