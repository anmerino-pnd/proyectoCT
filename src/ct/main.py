from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ct.chat import QueryRequest, get_chat_history, async_chat_endpoint, delete_chat_history_endpoint

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint de prueba sin parámetros
@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "API FastAPI funcionando"}

# Endpoint de prueba POST sin parámetros requeridos
@app.post("/echo")
async def echo():
    return {"status": "ok", "message": "Received POST request"}

@app.get("/history/{user_id}")
def handle_history(user_id: str):
    # Normalizar el user_id
    user_id = user_id.lower() 
    return get_chat_history(user_id)


@app.post("/chat")
async def handle_chat(request: QueryRequest):
    return await async_chat_endpoint(request)

@app.delete("/history/{user_id}") # Usamos el mismo path pero con método DELETE
async def handle_delete_history(user_id: str):
    # Llama al endpoint handler que creaste en chat.py
    return await delete_chat_history_endpoint(user_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)