from ct.settings.clients import mongo_collection_pedidos, mongo_uri
from pydantic import BaseModel, Field
from pymongo import MongoClient
import locale
import pytz
import re

locale.setlocale(locale.LC_TIME, "es_MX.UTF-8")
client = MongoClient(mongo_uri).get_default_database()
pedidos = client[mongo_collection_pedidos]
cdmx = pytz.timezone("America/Mexico_City")

class StatusInput(BaseModel):
    factura: str = Field(description="Número de factura para seguir y encontrar su estatus")
    session_id : str = Field(description="Con la sesión verificamos que el usuario que pregunta tenga el permiso de saber el estado")

def status_tool(factura: str, session_id: str) -> str:
    validacion = None
    cliente = session_id.split('_')[0]
    
    if re.match(r"^(\d{2})CTIN", session_id) is not None:
        pedido = pedidos.find_one(
        {"pedido.encabezado.folio": factura},
        {"_id": 0, "estatus": 1}
    )   
        validacion = True
    else: 
        pedido = pedidos.find_one(
            {"pedido.encabezado.folio": factura},
            {"_id": 0, "pedido.encabezado.cliente": 1, "estatus": 1}
        )
        validacion = cliente == pedido["pedido"]["encabezado"]["cliente"]

    if validacion == True:
        match list(pedido['estatus'])[-1]:
            case 'Pendiente':
                return "Pedido en generación"
            case 'Confirmado':
                return "Pedido creado"
            case 'Facturado':
                return "La factura del producto ha sido generada"
            case 'Enviado':
                return "La guía del pedido ha sido generada"
            case 'Terminado' | 'FacturaESDActualizada':
                return "Descarga digital entregada"
            case 'Preautorizado' | 'Autorizado':
                return "Procesando tu pedido"
            case 'Transito':
                dt_utc = pytz.utc.localize(pedido['estatus']['Transito']['fecha'])
                dt_cdmx = dt_utc.astimezone(cdmx)
                return dt_cdmx.strftime("El pedido salió en movimiento el %d de %B del %Y a las %H:%M:%S, horario Ciudad de México")
            case 'Entregado':
                return "Pedido entregado al domicilio"
            case 'Rechazado':
                return "Estamos revisando tu pedido, gracias por la paciencia"
            case 'Cancelado':
                return "El pedido ha sido cancelado"
            case _:
                return "Estamos trabajando en su pedido"
    else:
        return "No se encontró el pedido."