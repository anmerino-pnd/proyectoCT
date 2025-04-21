from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from ct.clients import openai_api_key as api

class LLM:
    def __init__(self):
        self.llm = None
        self.model = None
        self.temperature = 0.0

    def OpenAI(self):
        self.model = "gpt-4o"
        self.llm = ChatOpenAI(
            openai_api_key=api,
            model_name=self.model,
            temperature=self.temperature,
            streaming=True,
        )
        return self.llm, self.model
    
    def Ollama(self):
        self.model = "phi4:latest"
        self.llm = ChatOllama(
            model=self.model,
            temperature=self.temperature,
            streaming=True,
        )
        return self.llm, self.model

