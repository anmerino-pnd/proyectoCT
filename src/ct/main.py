from bson import ObjectId
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING, ASCENDING
from ct.chat import (
    QueryRequest, 
    get_chat_history, 
    async_chat_endpoint, 
    delete_chat_history_endpoint
    )
from ct.settings.clients import (
    get_db,
    mongo_uri, 
    openai_api_key,
    mongo_collection_sessions, 
    mongo_collection_message_backup
)
from ct.tools.search_information import reload_vector_store

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/history/{user_id}")
def handle_history(user_id: str):
    return get_chat_history(user_id)

@app.post("/chat")
async def handle_chat(request: QueryRequest):
    return await async_chat_endpoint(request)

@app.delete("/history/{user_id}") 
async def handle_delete_history(user_id: str):
    return await delete_chat_history_endpoint(user_id)

@app.post("/internal/reload_vectorstores")
async def reload_vectors():
    try:
        reload_vector_store()
        return {"status": "ok", "message": "Vector store recargado."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

templates = Jinja2Templates(directory="ui")

@app.get("/logs", response_class=HTMLResponse)
async def msg_log(request: Request, msg_id: Optional[str] = None):
    db = get_db()
    message_backup = db[mongo_collection_message_backup]
    
    context = {
        "request": request,
        "found": False,
        "msg_id_input": msg_id if msg_id else "", 
        "error_msg": None
    }

    if msg_id:
        try:
            obj_id = ObjectId(msg_id.strip())
            msg = message_backup.find_one({"_id": obj_id})
            
            if msg:
                raw_cost = msg.get("estimated_cost")
                
                # 2. Validamos que sea un número (float o int) y formateamos
                if isinstance(raw_cost, (float, int)):
                    formatted_cost = f"${raw_cost:.6f} USD"
                else:
                    formatted_cost = "N/A"

                raw_time = msg.get("timestamp")
                formatted_time = ""
                
                if isinstance(raw_time, datetime):
                    # Asegurarnos de que tenga tzinfo UTC antes de convertir
                    if raw_time.tzinfo is None:
                        raw_time = raw_time.replace(tzinfo=ZoneInfo("UTC"))
                    
                    # Convertir a Hermosillo y formatear (YYYY-MM-DD HH:MM:SS)
                    local_time = raw_time.astimezone(ZoneInfo("America/Hermosillo"))
                    formatted_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    formatted_time = str(raw_time) if raw_time else "N/A"

                context["found"] = True
                context.update({
                    "session_id": msg.get("session_id", "N/A"),
                    "question": msg.get("question", "-"),
                    "answer": msg.get("answer", "-"),
                    "verbose_log": msg.get("verbose_log", {}),
                    "model_used": msg.get("model_used", "Unknown"),
                    "timestamp": formatted_time,
                    "estimated_cost": formatted_cost,
                    "duration_seconds": f"{float(msg.get('duration_seconds', 0)):.2f}s" if msg.get("duration_seconds") else "N/A"
                })
            else:
                context["error_msg"] = "No se encontró ningún log con ese ID."
        except Exception as e:
            context["error_msg"] = f"ID inválido: {str(e)}"

    return templates.TemplateResponse("msg_log.html", context)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)