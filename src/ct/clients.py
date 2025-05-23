import os
import json
from pathlib import Path
import openai as openai_api
from dotenv import load_dotenv

load_dotenv()

# Credenciales de la empresa
ip: str = os.getenv('ip')
port: int = os.getenv('port')
user: str = os.getenv('user')
pwd: str = os.getenv('pwd')
database: str = os.getenv('db')

# Información del servicio
url: str = os.getenv('url')
tokenapi: str = os.getenv('Token-api')
tokenct: str = os.getenv('Token-ct')
contentType: str = os.getenv('Token-ct')
cookie: str = os.getenv('Token-ct')

dominio : str = os.getenv('dominio')
boundary: str = os.getenv('boundary')

mongo_uri: str = os.getenv('MONGO_URI')
mongo_db: str = os.getenv('MONGO_DB')
mongo_collection: str = os.getenv('MONGO_COLLECTION')
mongo_collection_backup: str = os.getenv('MONGO_COLLECTION_BACKUP')

# Credenciales de OpenAI
openai_api_key: str = os.getenv("OPENAI_API_KEY")
openai = openai_api.OpenAI(api_key=openai_api_key)

