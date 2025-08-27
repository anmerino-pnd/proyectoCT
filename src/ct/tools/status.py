from pydantic import BaseModel, Field
from pymongo import MongoClient
import locale
import pytz
import re
import mysql.connector
from ct.settings.clients import (
    mongo_collection_pedidos, 
    mongo_uri,
    ip,
    port,
    user,
    pwd,
    database)
import pymysql
pymysql.install_as_MySQLdb()

locale.setlocale(locale.LC_TIME, "es_MX.UTF-8")
client = MongoClient(mongo_uri).get_default_database()
pedidos = client[mongo_collection_pedidos]
cdmx = pytz.timezone("America/Mexico_City")

class StatusInput(BaseModel):
    factura: str = Field(description="Número de factura para seguir y encontrar su estatus")
    session_id : str = Field(description="Con la sesión verificamos que el usuario que pregunta tenga el permiso de saber el estado")

query = """
SELECT COUNT(*) AS descargas_enviadas
FROM esd_licencias_usuarios
WHERE folio_pedido = %s
"""

def descargas_enviadas(factura: str):
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor(query, (factura))
        result = cursor.fetchone()

        if result:
            return result[0]
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()
    pass

def status_tool(factura: str, session_id: str) -> str:
    cliente = session_id.split('_')[0]
    
    if re.match(r"^(\d{2})CTIN", session_id):
        # Vendedores internos -> pueden ver todos
        pedido = pedidos.find_one(
            {"pedido.encabezado.folio": factura},
            {"_id": 0, "estatus": 1, "pedido.detalle.producto":1, "pedido.esd":1}
        )
        print(pedido)
        validacion = pedido is not None
    else:
        # Clientes normales -> solo ven sus pedidos
        pedido = pedidos.find_one(
            {
                "pedido.encabezado.folio": factura,
                "pedido.encabezado.cliente": cliente
            },
            {"_id": 0, "estatus": 1, "pedido.detalle.producto":1, "pedido.esd":1}
        )
        print(pedido)
        validacion = pedido is not None

    if not validacion:
        return "No se encontró el pedido."

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
            return f"Descargas totales: {total}, total enviados: {descargas_enviadas(factura)}"
        case "Preautorizado" | "Autorizado":
            return "Procesando tu pedido"
        case "Transito":
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
