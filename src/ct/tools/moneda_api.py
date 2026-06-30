import time
import mysql.connector
from typing import cast
from pydantic import BaseModel, Field
from langchain.tools import tool
from ct.settings.clients import get_mysql_connection
import pymysql
pymysql.install_as_MySQLdb()

class DolarInput(BaseModel):
    dolar: float = Field(description="Precio exacto en dólares del producto")


query = """
SELECT
	dolar,
	filtro AS peso_mexicano
FROM monedas_api
LIMIT 1
"""

# Cache del tipo de cambio: rara vez cambia entre requests. Evita pegarle a MySQL
# en cada conversión. TTL configurable; reseteable en tests con _fx_cache["rate"]=None.
_FX_TTL_SECONDS = 3600  # 1 hora
_fx_cache: dict = {"rate": None, "ts": 0.0}


def _get_tipo_cambio() -> float | None:
    """Devuelve el tipo de cambio MXN, cacheado con TTL. Usa el pool MySQL."""
    now = time.monotonic()
    if _fx_cache["rate"] is not None and (now - _fx_cache["ts"]) < _FX_TTL_SECONDS:
        return _fx_cache["rate"]

    cnx = get_mysql_connection()
    cursor = cnx.cursor()
    try:
        cursor.execute(query)
        row = cursor.fetchone()
        if row:
            rate = float(cast(tuple, row)[1])
            _fx_cache["rate"] = rate
            _fx_cache["ts"] = now
            return rate
    finally:
        cursor.close()
        cnx.close()  # devuelve la conexión al pool
    return _fx_cache["rate"]  # si la query no trajo nada, usa el último válido (si existe)


@tool(args_schema=DolarInput)
def dolar_convertion_tool(dolar: float) -> str | None:
    """Convierte el precio de USD a MXN"""
    try:
        tipo_cambio = _get_tipo_cambio()
        if tipo_cambio is not None:
            return f"El equivalente de {dolar} USD es {(dolar * tipo_cambio):.3f} MXN"
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
