import os
import logging
from functools import lru_cache

import openai as openai_api
import mysql.connector
from mysql.connector import pooling
from pydantic import BaseModel
from dotenv import load_dotenv
from pymongo import MongoClient
import google.genai as google_api

class QueryRequest(BaseModel):
    user_query: str
    user_id: str
    listaPrecio: str 

load_dotenv()

# Credenciales de la empresa
ip: str = os.getenv('IP', '')
port: int = int(os.getenv('PORT', 0))
user: str = os.getenv('USER', '')
pwd: str = os.getenv('PSSWD', '')
database: str = os.getenv('DB', '')

# Credenciales de la empresa dev
ip_dev: str = os.getenv('IP_DEV', '')
port_dev: int = int(os.getenv('PORT_DEV', 0))
user_dev: str = os.getenv('USER_DEV', '')
pwd_dev: str = os.getenv('PWD_DEV', '')
database_dev: str = os.getenv('DB_DEV', '')

# Información del servicio
sucursales_url : str = os.getenv('SUCURSALES_URL', '')
url: str = os.getenv('URL', '')
tokenapi: str = os.getenv('TOKEN_API', '')
tokenct: str = os.getenv('TOKEN_CT', '')
contentType: str = os.getenv('CONTENT_TYPE', '')
cookie: str = os.getenv('COOKIE', '')
dominio : str = os.getenv('DOMINIO', '')
boundary: str = os.getenv('BOUNDARY', '')

mongo_uri: str = os.getenv('MONGO_URI', '')
mongo_db: str = os.getenv('MONGO_DB', '')
mongo_collection_sessions: str = os.getenv('MONGO_COLLECTION_SESSIONS', '')
mongo_collection_message_backup: str = os.getenv('MONGO_COLLECTION_MESSAGE_BACKUP', '')
mongo_collection_products: str = os.getenv('MONGO_COLLECTION_PRODUCTS', '')
mongo_collection_sales: str = os.getenv('MONGO_COLLECTION_SALES', '')
mongo_collection_specifications : str = os.getenv("MONGO_COLLECTION_SPECIFICATIONS", '')
mongo_collection_pedidos: str = os.getenv("MONGO_COLLECTION_PEDIDOS", '')

mongo_uri_prod: str = os.getenv('MONGO_URI_PROD', '')
mongo_db_prod: str = os.getenv('MONGO_DB_PROD', '')
mongo_collection_pedidos_prod: str = os.getenv("MONGO_COLLECTION_PEDIDOS_PROD", '')

# Credenciales de OpenAI
openai_api_key: str = os.getenv("OPENAI_API_KEY", '')
openai = openai_api.OpenAI(api_key=openai_api_key)
gemini_api_key: str = os.getenv("GOOGLE_API_KEY", '')
#gemini = google_api.Client(api_key=gemini_api_key)
ollama_api_key : str = os.getenv("OLLAMA_API_KEY", '')

podman_redis_url: str = os.getenv("PODMAN_REDIS_URL", '')
reload_vectors_post : str = os.getenv("RELOAD_VECTORS_POST", '')

algolia_url: str = os.getenv("ALGOLIA_URL", '')
algolia_sort_url: str = os.getenv("ALGOLIA_SORT_URL", '')
algolia_app_id: str = os.getenv("ALGOLIA_APP_ID", '')
algolia_api_key: str = os.getenv("ALGOLIA_API_KEY", '')
algolia_content_type: str = os.getenv("ALGOLIA_CONTENT_TYPE", '')
@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    return MongoClient(mongo_uri)


def get_db():
    return get_mongo_client().get_default_database()


logger = logging.getLogger(__name__)

# --- Pool de conexiones MySQL (evita el handshake completo en cada llamada a herramientas) ---
_mysql_pool = None

def _get_mysql_pool():
    global _mysql_pool
    if _mysql_pool is None:
        _mysql_pool = pooling.MySQLConnectionPool(
            pool_name="ct_mysql_pool",
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", "5")),  # por worker; ajusta a tu max_connections
            pool_reset_session=True,
            host=ip, port=port, user=user, password=pwd, database=database,
        )
    return _mysql_pool

def get_mysql_connection():
    """Devuelve una conexión MySQL reutilizable desde el pool.

    Reusar conexiones evita el TCP+auth de cada llamada. Hace ping con reconexión por si
    la conexión quedó inactiva, y cae a una conexión directa si el pool se agota.
    """
    try:
        cnx = _get_mysql_pool().get_connection()
    except Exception as e:
        logger.warning("Pool MySQL agotado/no disponible; conexión directa de respaldo: %s", e)
        return mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15,
        )
    try:
        cnx.ping(reconnect=True, attempts=2, delay=0)
    except Exception as e:
        # La conexión del pool quedó muerta: la devolvemos al pool y caemos a una directa
        # para no entregar una conexión inutilizable al llamador.
        logger.warning("Ping de conexión del pool falló (%s); usando conexión directa.", e)
        try:
            cnx.close()
        except Exception:
            pass
        return mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15,
        )
    return cnx