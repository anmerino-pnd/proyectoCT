import os
import json
import logging
from pathlib import Path
from bson import ObjectId
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
    mongo_collection_message_backup
)
from pydantic import BaseModel, Field
from ct.tools.search_information import reload_vector_store
from ct.settings.security import cors_origins, verify_origin, rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    reload_vector_store()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),   # env CHATBOT_ALLOWED_ORIGINS; '*' si no se define
    allow_credentials=False,        # el widget no usa cookies; evita el combo inválido con '*'
    allow_methods=["*"],
    allow_headers=["*"],
)

# SDK del widget servido desde este servidor: el compañero embebe
# <script src="https://<dominio>/sdk/sdk.js" data-user-id=... data-user-key=...>
app.mount("/sdk", StaticFiles(directory="ui"), name="sdk")

@app.get("/history/{user_id}", dependencies=[Depends(verify_origin)])
def handle_history(user_id: str):
    return get_chat_history(user_id)

@app.post("/chat", dependencies=[Depends(verify_origin), Depends(rate_limit)])
async def handle_chat(request: QueryRequest):
    return await async_chat_endpoint(request)

@app.delete("/history/{user_id}", dependencies=[Depends(verify_origin)])
async def handle_delete_history(user_id: str):
    return await delete_chat_history_endpoint(user_id)


logger = logging.getLogger(__name__)
_ui_event_warned = False
_ALLOWED_UI_EVENTS = {"open", "close", "expand", "collapse", "product_click"}

# Telemetría de UI a ARCHIVO (JSONL), no a MongoDB: el usuario de Mongo no puede
# crear colecciones nuevas. Un append por evento es atómico entre workers en POSIX.
# Configurable con CHATBOT_UI_EVENTS_LOG; rotación vía logrotate del sistema.
_UI_EVENTS_LOG = Path(os.getenv("CHATBOT_UI_EVENTS_LOG", "logs/ui_events.jsonl"))


def _write_ui_event(record: dict) -> None:
    _UI_EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _UI_EVENTS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class UIEventRequest(BaseModel):
    event: str
    user_id: str = ""
    meta: dict = Field(default_factory=dict)


@app.post("/ui-event", dependencies=[Depends(verify_origin)], status_code=204)
async def handle_ui_event(payload: UIEventRequest, request: Request):
    """Telemetría ligera del widget (open/expand/collapse/close/product_click).
    Fire-and-forget a archivo: nunca debe romper la UX."""
    if payload.event not in _ALLOWED_UI_EVENTS:
        return
    try:
        ip = None
        for header in ("cf-connecting-ip", "x-forwarded-for"):
            value = request.headers.get(header)
            if value:
                ip = value.split(",")[0].strip()
                break
        if ip is None:
            ip = request.client.host if request.client else "unknown"
        _write_ui_event({
            "event": payload.event,
            "user_id": payload.user_id,
            "meta": payload.meta,
            "ip": ip,
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        })
    except Exception as e:
        # Nunca rompemos la UX por telemetría. Logueamos UNA vez si el archivo falla.
        global _ui_event_warned
        if not _ui_event_warned:
            _ui_event_warned = True
            logger.warning("ui-event no escrito (%s): %s", _UI_EVENTS_LOG, e)

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