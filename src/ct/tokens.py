from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import LLMResult
from typing import Any, Dict, List
import tiktoken

MODEL_COST_PER_1K_TOKENS = {
    "gpt-4.5-preview": {
        "input": 0.075,       # $75.00 por 1M tokens → $0.075 por 1K
        "output": 0.15        # $150.00 por 1M → $0.15 por 1K
    },
    "gpt-4o": {
        "input": 0.0025,      # $2.50 por 1M → $0.0025 por 1K
        "output": 0.01        # $10.00 por 1M → $0.01 por 1K
    },
    "gpt-4o-mini": {
        "input": 0.00015,      # $0.150 por 1M → $0.00015 por 1K
        "output": 0.0006       # $0.600 por 1M → $0.0006 por 1K
    },
}

class TokenCostProcess:
    def __init__(self):
        self.input_tokens  = 0
        self.output_tokens  = 0

    def sum_input_tokens(self, tokens: int):
        self.input_tokens  += tokens
    
    def sum_output_tokens(self, tokens: int):
        self.output_tokens += tokens

    @property
    def total_tokens(self):
        return self.input_tokens  + self.output_tokens
    
    def get_total_cost_for_model(self, model: str) -> float:
        cost_config = MODEL_COST_PER_1K_TOKENS.get(model, {})
        
        # Tokens nuevos (no cacheados)
        input_cost = (self.input_tokens * cost_config["input"]) / 1000
        output_cost = (self.output_tokens * cost_config["output"]) / 1000
        return input_cost + output_cost

    def get_cost_summary(self, model: str) -> str:
        cost = self.get_total_cost_for_model(model)
        cost_config = MODEL_COST_PER_1K_TOKENS[model]
        return (
            f"Tokens Usage:\n"
            f"  Input Tokens: {self.input_tokens} @ ${cost_config['input']}/1K\n"
            f"  Output Tokens: {self.output_tokens} @ ${cost_config['output']}/1K\n"
            f"Total Tokens: {self.total_tokens}\n"
            f"Total Estimated Cost: ${cost:.6f}"
        )

class CostCalcAsyncHandler(AsyncCallbackHandler):
    def __init__(self, model: str, token_cost_process: TokenCostProcess):
        self.model = model
        self.token_cost_process = token_cost_process
        self.encoding = tiktoken.encoding_for_model(model)

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
            if self.token_cost_process:
                for prompt in prompts:
                    tokens = len(self.encoding.encode(prompt))
                    self.token_cost_process.sum_input_tokens(tokens)

    async def on_llm_new_token(self, token: str, **kwargs):
        if self.token_cost_process:
            self.token_cost_process.sum_output_tokens(1)

     