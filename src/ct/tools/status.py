import re
import pytz
import locale
import mysql.connector
from functools import lru_cache
from pymongo import MongoClient
from pydantic import BaseModel, Field
from typing import Optional, Tuple, cast
from ct.settings.schemas import UserContext
from langchain.tools import ToolRuntime, tool
from ct.settings.clients import (
    mongo_collection_pedidos_prod,
    mongo_uri_prod,
    ip,
    port,
    user,
    pwd,
    database)
from pymongo import ASCENDING
import pymysql
pymysql.install_as_MySQLdb()


pedidos = None  # parcheable desde tests; inicializado lazy por _load_pedidos()


def _load_pedidos():
    global pedidos
    if pedidos is None:
        client = MongoClient(mongo_uri_prod).get_default_database()
        pedidos = client[mongo_collection_pedidos_prod]
    return pedidos


@lru_cache(maxsize=1)
def _ensure_es_locale() -> None:
    try:
        locale.setlocale(locale.LC_TIME, "es_MX.UTF-8")
    except locale.Error:
        pass


cdmx = pytz.timezone("America/Mexico_City")

class StatusInput(BaseModel):
    factura: str = Field(description="Número de factura para seguir y encontrar su estatus")

query = """
SELECT COUNT(*) AS descargas_enviadas
FROM esd_licencias_usuarios
WHERE folio_pedido = %s
"""

def descargas_enviadas(factura: str) -> Optional[int] | str:
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query, (factura,))
        result = cast(Optional[Tuple[int, ...]], cursor.fetchone())

        if result:
            return result[0]
        return None
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

@tool(args_schema=StatusInput)
def status_tool(factura: str, runtime: ToolRuntime[UserContext]) -> str:
    """Con el folio factura de un pedido, saber su estado de envío"""
    cliente = runtime.context.session_id.split('_')[0]

    if re.match(r"^W[A-Z0-9]{2,3}-", factura):
        campo_de_busqueda = "pedido.encabezado.folio"
    else:
        campo_de_busqueda = "estatus.Facturado.folioFactura"

    filtro_de_consulta = {campo_de_busqueda: factura}

    if not re.match(r"^(\d{2})CTIN", runtime.context.session_id):
        # Si es un cliente, solo puede ver sus propios pedidos.
        filtro_de_consulta["pedido.encabezado.cliente"] = cliente

    pedido = _load_pedidos().find_one(
        filtro_de_consulta,
        {"_id": 0, "estatus": 1, "pedido.detalle.producto": 1},
        sort=[("pedido.fecha", ASCENDING)]  # Asumo que ASCENDING está definido
    )

    if not pedido:
        return "¿El folio es correcto?, si es correcto, no se encontró el pedido."
    
    # Obtener el último estatus
    ultimo_estatus = list(pedido["estatus"])[-1]

    match ultimo_estatus:
        case "Pendiente":
            return "Pedido en generación"
        case "Confirmado":
            return "Pedido creado"
        case "Facturado":
            return "La factura del producto ha sido generada"
        case "Enviado":
            return "La guía del pedido ha sido generada"
        case "Terminado" | "FacturaESDActualizada":
            productos = pedido['pedido']['detalle']['producto']
            total = sum(producto['cantidad'] for producto in productos)
            return f"ESD totales: {total}, total de descargas enviadas: {descargas_enviadas(factura)}"
        case "Preautorizado" | "Autorizado":
            return "Procesando tu pedido"
        case "Transito":
            _ensure_es_locale()
            dt_utc = pytz.utc.localize(pedido["estatus"]["Transito"]["fecha"])
            dt_cdmx = dt_utc.astimezone(cdmx)
            return dt_cdmx.strftime(
                "El pedido salió en movimiento el %d de %B del %Y a las %H:%M:%S, horario Ciudad de México"
            )
        case "Entregado":
            return "Pedido entregado al domicilio"
        case "Rechazado":
            return "Estamos revisando tu pedido, gracias por la paciencia"
        case "Cancelado":
            return "El pedido ha sido cancelado"
        case _:
            return "Estamos trabajando en su pedido"
