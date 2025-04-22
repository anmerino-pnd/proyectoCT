from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ct.chat import QueryRequest, get_chat_history, async_chat_endpoint

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
    # Normalizar el user_id
    user_id = user_id.lower() 
    return get_chat_history(user_id)


@app.post("/chat")
async def handle_chat(request: QueryRequest):
    print(f"Recibido: user_query={request.user_query}, user_id={request.user_id}, cliente_clave={request.cliente_clave}")
    return await async_chat_endpoint(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)