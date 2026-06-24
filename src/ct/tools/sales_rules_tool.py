import re
import json
import mysql.connector
from datetime import datetime
from pydantic import BaseModel, Field
from ct.settings.config import ID_SUCURSAL
from ct.settings.schemas import UserContext
from langchain.tools import ToolRuntime, tool
from ct.settings.clients import get_mysql_connection
import pymysql
pymysql.install_as_MySQLdb()


SUCURSALES: list | None = None


def _load_sucursales() -> list:
    """Carga lazy del archivo idSucursal.json. Respeta valores parcheados en tests."""
    global SUCURSALES
    if SUCURSALES is None:
        with open(ID_SUCURSAL, "r", encoding="utf-8") as f:
            SUCURSALES = json.load(f)
    return SUCURSALES


class SalesInput(BaseModel):
    claves: list[str] = Field(
        description="Lista de claves de productos en promoción a verificar en UNA sola llamada "
                    "(p.ej. ['CPULEN9780','IMPMTB980'])"
    )

def get_id_sucursal(session_id: str) -> str:
    match_ctin = re.match(r"^(\d{2})CTIN", session_id)
    if match_ctin:
        return match_ctin.group(1).lstrip("0")

    # Extrae las letras al inicio del session_id (como "HMO" de "HMO4536")
    match_nemonico = re.match(r"^([A-Z]+)", session_id)
    if match_nemonico:
        nemonico = match_nemonico.group(1)
    else:
        raise ValueError(f"No se pudo extraer nemonico de {session_id}")

    for entry in _load_sucursales():
        if entry.get("nemonico") == nemonico:
            return str(entry.get("idSucursal"))

    raise ValueError(f"No se encontró idSucursal para el session_id: {session_id}")

def query_sales():
    return """
SELECT 
    pre.precio 			       AS precio_regular,
    pros.importe                       AS precio_oferta,
    pros.porcentaje                    AS descuento,
    pros.EnCompraDE,
    pros.Unidades, 
    pros.limitadoA, 
    pros.ProductosGratis,
    pros.fecha_inicio,
    pros.fecha_fin,
    pre.idMoneda                       AS moneda
FROM promociones pros
  INNER JOIN productos pro  
    ON pro.idProductos = pros.idProducto
  LEFT JOIN precio pre 
    ON pros.idProducto = pre.idProducto
    AND pre.listaPrecio = %s
WHERE 
    pros.fecha_fin    >= CURRENT_DATE
    AND pros.fecha_inicio <= CURRENT_DATE
    AND pro.descripcion_corta_icecat != ''
    AND pre.idMoneda IS NOT NULL
    AND pros.producto = %s
    AND pros.sucursal_promo = %s
ORDER BY 
    pros.fecha_inicio DESC

LIMIT 1;
"""

def _format_promo(clave: str, result) -> str:
    """Construye el mensaje de promoción de UNA clave a partir de la fila de la BD (o None)."""
    if not result:
        return f"{clave}: El producto ya no se encuentra en promoción"

    precio = result[0]          # Precio original
    precio_oferta = result[1]   # Precio de promoción
    descuento = result[2]       # Descuento en porcentaje
    EnCompraDe = result[3]
    Unidades = result[4]
    limitadoA = result[5]
    fecha_inicio = result[7]
    fecha_fin = result[8]
    moneda = "MXN" if result[9] == 1 else "USD"

    ahora = datetime.now().date()
    if fecha_inicio and fecha_inicio > ahora:
        return f"{clave}: ${precio:.2f} {moneda} (sin promoción vigente)"

    mensaje = []
    precio_final = precio
    if precio_oferta > 0:
        if precio_oferta > precio:
            return f"{clave}: Cambio de precio base a ${precio_oferta:.2f} {moneda}, no se considera promoción"
        precio_final = precio_oferta
        mensaje.append(f"{clave}: ${precio_final:.2f} {moneda}")
    elif descuento > 0:
        precio_final = round(precio * (1 - descuento / 100), 2)
        mensaje.append(f"{clave}: ~${precio:.2f}~ ${precio_final:.2f} {moneda} ({descuento:.0f}% desc)")
    elif EnCompraDe > 0 and Unidades > 0:
        mensaje.append(f"{clave}: En compra de {EnCompraDe}, recibe {Unidades} gratis")

    if limitadoA > 0:
        mensaje.append(f"Limitado a {limitadoA} unidades por cliente")
    if fecha_fin:
        mensaje.append(f"Vigente hasta el {fecha_fin.strftime('%d-%b-%Y')}")

    return ", ".join(mensaje)


@tool(args_schema=SalesInput)
def sales_rules_tool(claves: list[str],
                     runtime: ToolRuntime[UserContext]) -> str:
    """Reglas de ofertas y promociones. Acepta VARIAS claves en una sola llamada (una conexión)."""
    cnx = None
    cursor = None
    try:
        id_sucursal = get_id_sucursal(runtime.context.session_id)

        cnx = get_mysql_connection()
        cursor = cnx.cursor()

        partes = []
        for clave in claves:
            cursor.execute(query_sales(), (runtime.context.lista_precio, clave, id_sucursal))
            partes.append(_format_promo(clave, cursor.fetchone()))

        return "\n".join(partes)

    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()