import os
import openai as openai_api
from pydantic import BaseModel
from dotenv import load_dotenv

class QueryRequest(BaseModel):
    user_query: str
    user_id: str
    listaPrecio: str 

load_dotenv()

# Credenciales de la empresa
ip: str = os.getenv('IP')
port: int = os.getenv('PORT')
user: str = os.getenv('USER')
pwd: str = os.getenv('PSSWD')
database: str = os.getenv('DB')

# Credenciales de la empresa dev
ip_dev: str = os.getenv('IP_DEV')
port_dev: int = os.getenv('PORT_DEV')
user_dev: str = os.getenv('USER_DEV')
pwd_dev: str = os.getenv('PWD_DEV')
database_dev: str = os.getenv('DB_DEV')

# Información del servicio
sucursales_url : str = os.getenv('SUCURSALES_URL')
url: str = os.getenv('URL')
tokenapi: str = os.getenv('TOKEN_API')
tokenct: str = os.getenv('TOKEN_CT')
contentType: str = os.getenv('CONTENT_TYPE')
cookie: str = os.getenv('COOKIE')
dominio : str = os.getenv('DOMINIO')
boundary: str = os.getenv('BOUNDARY')

mongo_uri: str = os.getenv('MONGO_URI')
mongo_db: str = os.getenv('MONGO_DB')
mongo_collection_sessions: str = os.getenv('MONGO_COLLECTION_SESSIONS')
mongo_collection_message_backup: str = os.getenv('MONGO_COLLECTION_MESSAGE_BACKUP')
mongo_collection_products: str = os.getenv('MONGO_COLLECTION_PRODUCTS')
mongo_collection_sales: str = os.getenv('MONGO_COLLECTION_SALES')
mongo_collection_specifications : str = os.getenv("MONGO_COLLECTION_SPECIFICATIONS")
mongo_collection_pedidos: str = os.getenv("MONGO_COLLECTION_PEDIDOS")

# Credenciales de OpenAI
openai_api_key: str = os.getenv("OPENAI_API_KEY")
openai = openai_api.OpenAI(api_key=openai_api_key)

podman_redis_url: str = os.getenv("PODMAN_REDIS_URL")
reload_vectors_post : str = os.getenv("RELOAD_VECTORS_POST")

algolia_url = os.getenv("ALGOLIA_URL")
algolia_app_id = os.getenv("ALGOLIA_APP_ID")
algolia_api_key = os.getenv("ALGOLIA_API_KEY")
algolia_content_type = os.getenv("ALGOLIA_CONTENT_TYPE")
