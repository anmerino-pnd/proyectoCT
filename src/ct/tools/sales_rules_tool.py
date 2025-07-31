import re
import json
import mysql.connector
from datetime import datetime
from pydantic import BaseModel
from ct.settings.clients import ip, port, user, pwd, database
from ct.settings.config import ID_SUCURSAL
import pymysql
pymysql.install_as_MySQLdb()


with open(ID_SUCURSAL, "r", encoding="utf-8") as f:
    SUCURSALES = json.load(f)

class SalesInput(BaseModel):
    clave: str
    listaPrecio: int
    session_id: str

def obtener_id_sucursal(session_id: str) -> str:
    match_ctin = re.match(r"^(\d{2})CTIN", session_id)
    if match_ctin:
        return match_ctin.group(1).lstrip("0")

    # Extrae las letras al inicio del session_id (como "HMO" de "HMO4536")
    match_nemonico = re.match(r"^([A-Z]+)", session_id)
    if match_nemonico:
        nemonico = match_nemonico.group(1)
    else:
        raise ValueError(f"No se pudo extraer nemonico de {session_id}")

    for entry in SUCURSALES:
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
GROUP BY 
    pros.idProducto, 
    pros.fecha_inicio
ORDER BY 
    pros.fecha_inicio DESC

LIMIT 1;
"""

def sales_rules_tool(clave: str, listaPrecio: int, session_id: str) -> str:
    cnx = None
    cursor = None
    try:
        id_sucursal = obtener_id_sucursal(session_id)

        cnx = mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query_sales(), (listaPrecio, clave, id_sucursal))
        result = cursor.fetchone()

        if result:
            precio = result[0]          # Precio original
            precio_oferta = result[1]   # Precio de promoción
            descuento = result[2]       # Descuento en porcentaje
            EnCompraDe = result[3]
            Unidades = result[4]
            limitadoA = result[5]
            fecha_inicio = result[7]
            fecha_fin = result[8]
            moneda = "MXN" if result[9] == 1 else "USD"

            mensaje = []
            ahora = datetime.now().date()

            if fecha_inicio and fecha_inicio > ahora:
                return f"{clave}: ${precio:.2f} {moneda} (sin promoción vigente)"

            precio_final = precio

            if precio_oferta > 0:
                if precio_oferta > precio:
                    return f"{clave}: Cambio de precio base a ${precio_oferta:.2f} {moneda}, no se considera promoción"
                else:
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

        return f"{clave}: El producto ya no se encuentra en promoción"

    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()