from ct.settings.clients import (
    ip,
    pwd,
    port,
    user,
    database,
    algolia_url,
    algolia_app_id,
    algolia_api_key,
    algolia_sort_url,
    algolia_content_type
)
import re
import json
import pymysql
import requests
import cloudscraper 
import mysql.connector
from toon import encode
from string import Template
pymysql.install_as_MySQLdb()
from pydantic import BaseModel, Field
from ct.settings.config import ID_SUCURSAL
from ct.tools.sales_rules_tool import get_id_sucursal

with open(ID_SUCURSAL, "r", encoding="utf-8") as f:
    SUCURSALES = json.load(f)

class AlgoliaInput(BaseModel):
    producto : str = Field(description="Búsqueda del producto de interés del usuario")
    session_id : str = Field(description="ID de la sesión del usuario")
    lista_precio : int = Field(description="Lista de precio a la que pertenece el usuario")
    lowest_price : bool = Field(description="Si el usuario quiere saber el producto con el precio más barato, True, si no, False. Por defecto es False",
                                default=False)

query = Template(
    """
SELECT
	cuenta,
	lista1,
	lista2,
	lista3,
	lista4,
	lista5,
	lista6,
	lista7
FROM clientes_hp
WHERE cuenta = '${account}';
"""
)

def _create_scraper(user_token: str) -> cloudscraper.CloudScraper:
    scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
    }
)
    scraper.headers.update({
        'X-Algolia-Application-Id': algolia_app_id,
        'X-Algolia-API-Key': algolia_api_key,
        'Content-Type': algolia_content_type,
        'X-Algolia-UserToken': user_token
    })

    return scraper

def get_user(user: str) -> str:
    match_ctin = re.match(r"^(\d{2}CTIN)", user)
    if match_ctin:
        return match_ctin.group(1)

    # Extrae la cuenta del session id (como "HMO4536" de "HMO4536_angel.merino")
    match_user = re.match(r"^([A-Z0-9]+)", user)
    if match_user:
        return match_user.group(1)
    else:
        raise ValueError(f"No se pudo extraer usuario")  

def query_exec(query) -> list:
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=ip, 
            port=port, 
            user=user, 
            password=pwd, 
            database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query)
        return cursor.fetchall()
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

def algolia_search_tool(
        producto: str, 
        session_id: str, 
        lista_precio: int,
        lowest_price : bool = False):
    
    lista_precio = str(lista_precio)
    userToken = re.sub(r'[._]', '-', session_id)
    scraper = _create_scraper(userToken)
    account = get_user(session_id)
    especial_hp = query_exec(query.substitute(account = account))
    if especial_hp:
        especial_values = especial_hp[0][1:]
        lista_especial_hp = [
            "" if v == 1 else f" AND NOT especial_hp = {i}"
            for i, v in enumerate(especial_values, start=1)
        ]
        filters = "especial_hp = 0 "
        for especial in lista_especial_hp:
            if '':
                continue
            else:
                filters += especial
        final_filters = filters + f" AND especial_cuenta: 'VPG' OR especial_cuenta: '{account}'"
    else:
        final_filters = f"especial_hp = 0 AND especial_cuenta: 'VPG'"
        
    print(final_filters)
    payload = json.dumps({
        "query": producto,
        "filters": final_filters,
        "hitsPerPage": 6,
        "page": 0,
        "optionalFilters": [["existencia_sucursal:1"]],
        "numericFilters": [],
        "ruleContexts": ["*"]
    })

    try: 
        response = scraper.post(
        url = algolia_sort_url if lowest_price else algolia_url,
        data = payload,
        timeout = 10
        )

        response.raise_for_status()

        data = response.json()
        hits = data.get('hits', [])

        if not hits:
            return f"  No se encontraron resultados para: {producto}"
        
        resultados = {}
        id_sucursal = get_id_sucursal(session_id)
        promo_key = f"A{id_sucursal}"

        for producto in hits:
            clave = producto.get('clave')
            if not clave:
                continue
            
            precios = producto.get('precios', {})
            if lista_precio not in precios:
                print(f"  Producto {clave} no tiene precio para lista {lista_precio}")
                continue
            
            # Verificar promoción
            cliente_promo = producto.get('cliente_promo', [])
            en_promocion = 'Sí' if promo_key in cliente_promo else 'No'
            existencia_sucursales = (
                producto.get('existencia_total', 0)
            )
            existencia_sucursal = (
                producto.get("existencia", {}).get(id_sucursal, 0)
            )
            
            resultados[clave] = {
                'marca': producto.get('marca', ''),
                'modelo': producto.get('modelo', ''),
                'descripcion': producto.get('descripcion', ''),
                'ficha_tecnica': producto.get('icecat', ''),
                'precio': precios[lista_precio],
                'total_en_otras_sucursales': existencia_sucursales if existencia_sucursales != 0 else "Sobre pedido",
                'total_en_su_sucursal' : existencia_sucursal if existencia_sucursal != 0 else "Sobre pedido",
                'moneda': producto.get('moneda', 'MXN'),
                'en_promocion': en_promocion,
                'url': producto.get('url', ''),
            }
        
        return encode(resultados)
    
    except requests.exceptions.Timeout:
        print(f"❌ Timeout en búsqueda de Algolia: {producto}")
        return {}
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error en request a Algolia: {e}")
        return {}
        
    except KeyError as e:
        print(f"❌ Respuesta de Algolia con estructura inesperada: {e}")
        return {}
        
    except Exception as e:
        print(f"❌ Error inesperado en algolia_query: {e}")
        return {}