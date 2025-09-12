import mysql.connector
from pydantic import BaseModel, Field
from ct.settings.clients import ip, port, user, pwd, database
import pymysql
pymysql.install_as_MySQLdb()


# 1. Definimos el esquema de entrada
class InventoryInput(BaseModel):
    clave: str = Field(description="Clave del producto")
    listaPrecio: int = Field(description="Lista de precio al que pertenece el usuario")

query = """
SELECT pro.clave, 
       SUM(e.cantidad) AS existencias, 
       pre.precio, 
       pre.idMoneda AS moneda,
       pro.modelo,
       pro.activo,
       CASE WHEN EXISTS(SELECT 1 FROM promociones WHERE producto = pro.clave) 
            THEN 'Sí' ELSE 'No' END AS en_promocion
FROM productos pro
LEFT JOIN existencias e ON pro.idProductos = e.idProductos
LEFT JOIN precio pre ON pro.idProductos = pre.idProducto AND pre.listaPrecio = %s
WHERE pro.clave = %s
GROUP BY pro.idProductos, pre.precio, pre.idMoneda;
    """

# 2. La función ahora es una función Python normal, sin el decorador @tool
def inventory_tool(clave: str, listaPrecio: int) -> str:
    lista_precio = listaPrecio
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
            # result indexes según tu SELECT:
            # 0 = clave
            # 1 = existencias
            # 2 = precio
            # 3 = idMoneda
            # 4 = modelo
            # 5 = activo
            # 6 = en_promocion
            clave_prod = result[0]
            existencias = result[1]
            precio = result[2]
            id_moneda = result[3]
            modelo = result[4]
            activo = result[5]
            en_promocion = result[6]

            moneda = "MXN" if id_moneda == 1 else "USD"

            # lógica ESD
            if modelo == "ESD" and activo == 1:
                disponibilidad = "sí hay disponibles"
            else:
                disponibilidad = f"{existencias} unidades disponibles"

            return (
                f"{clave_prod}: precio original: ${precio} {moneda}, "
                f"{disponibilidad}, ¿en promoción?: {en_promocion}"
            )
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

