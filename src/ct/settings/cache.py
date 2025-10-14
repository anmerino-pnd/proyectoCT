import cassio
from langchain_community.cache import CassandraSemanticCache, OpenSearchSemanticCache
from langchain_core.globals import set_llm_cache
from langchain_openai import OpenAIEmbeddings
from ct.settings.clients import openai_api_key

# Conectar a Cassandra en Podman
cassio.init(
    contact_points=["localhost"],
    keyspace="llm_cache"
)

# Crear el keyspace si no existe
from cassandra.cluster import Cluster
cluster = Cluster(['localhost'])
session = cluster.connect()
session.execute("""
    CREATE KEYSPACE IF NOT EXISTS llm_cache
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
""")

embedding = OpenAIEmbeddings(api_key=openai_api_key)

set_llm_cache(
    CassandraSemanticCache(
        embedding=embedding,
        table_name="my_semantic_cache",
        ttl_seconds=600  # 10 minutos
    )
)