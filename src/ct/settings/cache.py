import redis
import gptcache
from langchain_community.cache import (
    GPTCache,
    RedisCache, 
    InMemoryCache, 
    RedisSemanticCache, 
    CassandraSemanticCache,)
from langchain.globals import set_llm_cache
from gptcache.processor.pre import get_prompt
from langchain_openai import OpenAIEmbeddings
from ct.settings.clients import podman_redis_url, openai_api_key
from gptcache.manager.factory import get_data_manager, CacheBase, VectorBase

# # Conectar a Cassandra en Podman
# cassio.init(
#     address="localhost:9142",
#     keyspace="langchain_cache"
#     )

# embedding = OpenAIEmbeddings(api_key=openai_api_key)

# set_llm_cache(
#     CassandraSemanticCache(
#         embedding=embedding,
#         table_name="my_semantic_cache",
#         ttl_seconds=600  # 10 minutos
#     )
# )

# cache_client = InMemoryCache()
# set_llm_cache(cache_client)

def init_gptcache(cache_obj: gptcache.Cache):
    cache_obj.init(
        pre_embedding_func=get_prompt,
        data_manager=get_data_manager(CacheBase('sqlite'), VectorBase('faiss', dimension=128))
        )

set_llm_cache(GPTCache(init_gptcache))


# redis_client = redis.Redis.from_url(podman_redis_url)
# set_llm_cache(RedisCache(redis_client, ttl=600))

# redis_client = RedisSemanticCache(                                        # Error de pip install que no se arregló
#                 redis_url=podman_redis_url,
#                 embedding=OpenAIEmbeddings(api_key=openai_api_key))
# set_llm_cache(redis_client)