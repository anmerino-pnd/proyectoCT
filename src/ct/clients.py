import os
import json
from pathlib import Path
import openai as openai_api
from dotenv import load_dotenv
from ct.config import CLIENTES_FILE

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

# Credenciales de OpenAI
openai_api_key: str = os.getenv("OPENAI_API_KEY")
openai = openai_api.OpenAI(api_key=openai_api_key)

class Clients:
    @staticmethod
    def load_clients():
        if os.path.exists(CLIENTES_FILE):
            with open(CLIENTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def get_lista_precio(cliente_clave):
        clientes = Clients.load_clients()
        return clientes.get(cliente_clave)
    
# IP de la API 

API_INTERNA_URL : str = os.getenv('API_INTERNA_URL')