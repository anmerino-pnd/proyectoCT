import mysql.connector
from pydantic import BaseModel
# from langchain.tools import tool # REMOVE THIS IMPORT if not used elsewhere
from ct.settings.clients import ip, port, user, pwd, database
import pymysql
pymysql.install_as_MySQLdb()


# 1. Definimos el esquema de entrada
class ExistenciasInput(BaseModel):
    clave: str
    listaPrecio: int

# 2. La función ahora es una función Python normal, sin el decorador @tool
def existencias_tool(clave: str, listaPrecio: int) -> str:
    lista_precio = listaPrecio # Use the directly passed listaPrecio

    query = """
    SELECT
        pro.clave,
        SUM(e.cantidad) AS existencias,
        pre.precio,
        pre.idMoneda AS moneda,
        CASE 
            WHEN prom.producto IS NOT NULL THEN 'Sí'
            ELSE 'No'
        END AS en_promocion
    FROM productos pro
    LEFT JOIN existencias e ON pro.idProductos = e.idProductos
    LEFT JOIN precio pre ON pro.idProductos = pre.idProducto AND pre.listaPrecio = %s
    LEFT JOIN promociones prom ON pro.clave = prom.producto
    WHERE pro.clave = %s
    GROUP BY pro.idProductos
    """

    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query, (lista_precio, clave))
        result = cursor.fetchone()
        if result:
            moneda = "MXN" if result[3] == 1 else "USD"
            return f"{result[0]}: precio original: ${result[2]} {moneda}, {result[1]} unidades disponibles, ¿en promoción?: {result[4]}"
        return "No se encontró el producto o no tiene existencias."
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

