from cachetools import TTLCache
from langchain.globals import set_llm_cache
from langchain.schema import Generation
from typing import Optional, List, Any

class TTLInMemoryCache:
    def __init__(self, maxsize=10000, ttl=600):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
    
    def lookup(self, prompt: str, llm_string: str) -> Optional[List[Generation]]:
        key = (prompt, llm_string)
        return self.cache.get(key)
    
    def update(self, prompt: str, llm_string: str, return_val: List[Generation]) -> None:
        key = (prompt, llm_string)
        self.cache[key] = return_val
    
    def clear(self) -> None:
        self.cache.clear()

# Usar el caché personalizado
set_llm_cache(TTLInMemoryCache(maxsize=10000, ttl=600))