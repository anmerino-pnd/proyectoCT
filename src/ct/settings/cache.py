# import cassio
# from langchain_community.cache import CassandraSemanticCache, OpenSearchSemanticCache
# from langchain_core.globals import set_llm_cache
# from langchain_openai import OpenAIEmbeddings
# from ct.settings.clients import openai_api_key

# # # Conectar a Cassandra en Podman
# # cassio.init(
# #     contact_points=["localhost"],
# #     keyspace="llm_cache"
# # )

# # # Crear el keyspace si no existe
# # from cassandra.cluster import Cluster
# # cluster = Cluster(['localhost'])
# # session = cluster.connect()
# # session.execute("""
# #     CREATE KEYSPACE IF NOT EXISTS llm_cache
# #     WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
# # """)

# # embedding = OpenAIEmbeddings(api_key=openai_api_key)

# # set_llm_cache(
# #     CassandraSemanticCache(
# #         embedding=embedding,
# #         table_name="my_semantic_cache",
# #         ttl_seconds=600  # 10 minutos
# #     )
# # )

# import redis
# from langchain_community.cache import RedisCache
# from langchain.globals import set_llm_cache

# redis_client = redis.Redis.from_url("redis://localhost:6379")

# set_llm_cache(RedisCache(redis_client, ttl=600))

import time
from typing import Optional, Any
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache

class InMemoryCacheWithTTL(BaseCache):
    """Caché en memoria con Time-To-Live (TTL)."""
    
    def __init__(self, ttl_seconds: int = 600):
        """
        Args:
            ttl_seconds: Tiempo de vida del caché en segundos (default: 600 = 10 minutos)
        """
        self._cache = {}
        self._timestamps = {}
        self.ttl_seconds = ttl_seconds
    
    def _is_expired(self, key: str) -> bool:
        """Verifica si una entrada ha expirado."""
        if key not in self._timestamps:
            return True
        return time.time() - self._timestamps[key] > self.ttl_seconds
    
    def _clean_expired(self):
        """Limpia las entradas expiradas."""
        expired_keys = [
            key for key in self._timestamps
            if self._is_expired(key)
        ]
        for key in expired_keys:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
    
    def lookup(self, prompt: str, llm_string: str) -> Optional[Any]:
        """Busca en el caché."""
        key = f"{prompt}:{llm_string}"
        
        # Limpiar expirados periódicamente
        self._clean_expired()
        
        # Verificar si existe y no ha expirado
        if key in self._cache and not self._is_expired(key):
            return self._cache[key]
        
        return None
    
    def update(self, prompt: str, llm_string: str, return_val: Any) -> None:
        """Actualiza el caché."""
        key = f"{prompt}:{llm_string}"
        self._cache[key] = return_val
        self._timestamps[key] = time.time()
    
    def clear(self) -> None:
        """Limpia todo el caché."""
        self._cache.clear()
        self._timestamps.clear()


# Configurar el caché global con TTL de 10 minutos
set_llm_cache(InMemoryCacheWithTTL(ttl_seconds=600))