import redis
import gptcache
from gptcache import Cache
from gptcache.embedding import Onnx  
from langchain_community.cache import (
    GPTCache,
    RedisCache, 
    InMemoryCache, 
    RedisSemanticCache, 
    CassandraSemanticCache,)
from langchain.globals import set_llm_cache
from gptcache.processor.pre import get_prompt
from langchain_openai import OpenAIEmbeddings
from gptcache.adapter.api import init_similar_cache
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

# def init_gptcache(cache_obj: Cache):
#     embedding_func = Onnx()  # o usa OpenAIEmbeddings
#     cache_obj.init(
#         pre_embedding_func=lambda text, **_: embedding_func.to_embeddings(text),
#         data_manager=get_data_manager(
#             CacheBase("sqlite"),
#             VectorBase("faiss", dimension=embedding_func.dimension)
#         ),
#     )

# set_llm_cache(GPTCache(init_gptcache))


# redis_client = redis.Redis.from_url(podman_redis_url)
# set_llm_cache(RedisCache(redis_client, ttl=600))

redis_client = RedisSemanticCache(                                        # Error de pip install que no se arregló
                redis_url=podman_redis_url,
                embedding=OpenAIEmbeddings(api_key=openai_api_key))
set_llm_cache(redis_client)