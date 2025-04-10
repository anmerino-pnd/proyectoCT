import time
from typing import Tuple # Se pueden usar diccionarios en lugar de tuplas?
from langchain_ollama import OllamaLLM
from ct.history import ChatHistoryManager
from ct.clients import openai_api_key as api
from langchain_openai import OpenAIEmbeddings
from ct.langchain.rag_assistant import RAGassistant

from ct.llm_types import LLMAPIResponseError, CallMetadata, call_metadata, LLMError

class OllamaAssistant(RAGassistant):
    def __init__(self):
        self.model = "deepseek-r1:latest"
        self.llm = OllamaLLM(model=self.model, temperature=0)
        self.vector_path = r"C:\Users\angel.merino\Documents\proyectoCT\datos\vdb_CT"
        self.embedding_model = OpenAIEmbeddings(api_key=api)
        super().__init__(llm=self.llm, VECTOR_DB_PATH=self.vector_path, embedding_model=self.embedding_model) 
        self.history = ChatHistoryManager()
        

    def offer(self, user_enquery: str, user_id: str, listaPrecio: str) -> Tuple[str, CallMetadata]:
        start_time = time.perf_counter()
        self.history.add_message(user_id, "human", user_enquery) 
        res = self.prompt(user_enquery, user_id, listaPrecio)
        self.history.add_message(user_id, "system", res['answer'])
        end_time = time.perf_counter()
        duration = end_time - start_time
        if res is None:
            raise LLMAPIResponseError(res, "assistant report")
        return (
            res['answer'],
            duration,
        )
    
    def make_simple_metadata(self, cb, duration : float) -> CallMetadata:
        input_tokens = cb.prompt_tokens
        output_tokens = cb.completion_tokens
        return call_metadata(
            provider="ollama",
            model=self.model,
            operation="NOHAY",
            duration=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )