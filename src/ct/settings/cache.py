import redis
import cassio
from langchain_community.cache import RedisCache, RedisSemanticCache, InMemoryCache, CassandraSemanticCache
from ct.settings.clients import podman_redis_url, openai_api_key
from langchain.globals import set_llm_cache
from langchain_openai import OpenAIEmbeddings

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

redis_client = redis.Redis.from_url(podman_redis_url)
set_llm_cache(RedisCache(redis_client, ttl=600))

# redis_client = RedisSemanticCache(                                        # Error de pip install que no se arregló
#                 redis_url=podman_redis_url,
#                 embedding=OpenAIEmbeddings(api_key=openai_api_key))
# set_llm_cache(redis_client)