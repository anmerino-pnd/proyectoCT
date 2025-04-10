from langchain_openai import ChatOpenAI
from ct.clients import openai_api_key as api

class LLM:
    def __init__(self):
        self.model = "gpt-4o"
        self.llm = ChatOpenAI(model=self.model, api_key=api, temperature=0, streaming=True)