from ct.settings.clients import (
    algolia_url,
    algolia_app_id,
    algolia_api_key,
    algolia_sort_url,
    algolia_content_type,
)
import re
import json
import requests
import cloudscraper 
from toon import encode
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


def algolia_search_tool(
        producto: str, 
        session_id: str, 
        lista_precio: int,
        lowest_price : bool = False, 
        especial_hp : int = 0,
        especial_cuenta : str = 'VPG'):
    
    lista_precio = str(lista_precio)
    userToken = re.sub(r'[._]', '-', session_id)
    scraper = _create_scraper(userToken)
    
    final_filters = f"especial_hp = {especial_hp} AND especial_cuenta : {especial_cuenta}"
    
    payload = json.dumps({
        "query": producto,
        "filters": final_filters,
        "facetFilters": [],
        "facets": ["*"],
        "page": 0,
        "hitsPerPage": 30,
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
            en_promocion = promo_key in cliente_promo
            
            resultados[clave] = {
                'marca': producto.get('marca', ''),
                'modelo': producto.get('modelo', ''),
                'descripcion': producto.get('descripcion', ''),
                'ficha_tecnica': producto.get('icecat', ''),
                'existencia_todas_sucursales': producto.get('existencia_total', 0),
                'existencia_su_sucursal' : producto['existencia'][id_sucursal],
                'precio': precios[lista_precio],
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