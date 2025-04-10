import json
import time
from typing import Tuple, AsyncGenerator
from ct.history import ChatHistoryManager
from ct.clients import openai_api_key as api
from ct.langchain.rag_assistant import RAGassistant
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from ct.tokens import TokenCostProcess, CostCalcAsyncHandler
from langchain_community.callbacks import get_openai_callback
from langchain_community.callbacks.openai_info import OpenAICallbackHandler
from ct.llm_types import LLMAPIResponseError, CallMetadata, call_metadata, LLMError

class OpenAIAssistant(RAGassistant):
    def __init__(self):
        self.model = "gpt-4o"
        self.llm = ChatOpenAI(model=self.model, api_key=api, temperature=0, streaming=True)
        self.vector_path = r"C:\Users\angel.merino\Documents\proyectoCT\datos\productos_promociones_CT"
        self.embedding_model = OpenAIEmbeddings(api_key=api)
        super().__init__(llm=self.llm, VECTOR_DB_PATH=self.vector_path, embedding_model=self.embedding_model) 
        self.history = ChatHistoryManager()
        
    
    async def async_offer(self, user_enquery: str, user_id: str, listaPrecio: str) -> AsyncGenerator[str, None]:        
        token_cost_process = TokenCostProcess()
        cost_handler = CostCalcAsyncHandler(
            model=self.model,
            token_cost_process=token_cost_process
        )

        # Agregamos el mensaje del usuario al historial
        self.history.add_message(user_id, "human", user_enquery)
        
        # Inicializamos una variable para almacenar la respuesta completa
        full_response = ""
        start_time = time.perf_counter()

        try:
            # Usamos astream para obtener el flujo de chunks
            async for chunk in self.async_prompt(
                user_enquery, 
                user_id, 
                listaPrecio, 
                callbacks=cost_handler):
                # Extraemos el valor de 'answer' de cada chunk
                chunk_answer = chunk.get("answer", "")
                full_response += chunk_answer  # Concatenamos solo el texto de la respuesta
                yield chunk_answer  # Devolvemos cada chunk en stream
            
            duration = time.perf_counter() - start_time
            metadata = self.make_metadata(token_cost_process, duration)
            
            self.history.add_message(user_id, "system", full_response, metadata)  # Guardamos el historial con metadata

            # Verificamos si la respuesta es válida
            if not full_response.strip():
                raise LLMAPIResponseError(None, "No se recibió respuesta del asistente.")
        
        except Exception as e:    
            raise LLMAPIResponseError(None, f"Error al procesar la solicitud: {str(e)}", exception=e)
    

    def make_metadata(self, token_cost_process: TokenCostProcess, duration: float = None) -> dict:
        """Versión simplificada de metadata"""
        cost = token_cost_process.get_total_cost_for_model(self.model)
        
        metadata = {
            "model": self.model,
            "tokens": {
                "input": token_cost_process.input_tokens,
                "output": token_cost_process.output_tokens,
                "total": token_cost_process.total_tokens,
                "cost": cost
            }
        }
        
        if duration is not None:
            metadata["duration"] = {
                "seconds": duration,
                "tokens_per_second": token_cost_process.total_tokens / duration if duration > 0 else 0
            }
        
        return metadata