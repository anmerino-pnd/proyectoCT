from ct.settings.clients import mongo_collection_pedidos, mongo_uri
from pydantic import BaseModel, Field
from pymongo import MongoClient

client = MongoClient(mongo_uri).get_default_database()
pedidos = client[mongo_collection_pedidos]

class PedidosInput(BaseModel):
    factura: str = Field(description="Número de factura para seguir y encontrar su estatus")

def pedidos_tool(factura: str) -> str:
    doc = pedidos.find_one(
        {"pedido.encabezado.folio": factura},
        {"_id": 0, "estatus": 1}
        )
    if doc:
        return doc
    return "No se encontró el pedido."