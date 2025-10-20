from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ct.chat import (
    QueryRequest, 
    get_chat_history, 
    async_chat_endpoint, 
    delete_chat_history_endpoint
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)