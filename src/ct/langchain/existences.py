import mysql.connector
from langchain.tools import tool
from ct.clients import ip, port, user, pwd, database

@tool
def existences(clave: str) -> str:
    """Devuelve cuántas existencias hay de un producto dada su clave. Usa esta herramienta si el cliente pregunta por disponibilidad o cuántos quedan."""
    query = """
    SELECT pro.clave, SUM(e.cantidad) AS existencias
    FROM existencias e
    LEFT JOIN productos pro ON pro.idProductos = e.idProductos
    WHERE pro.clave = %s
    GROUP BY pro.clave
    """
    try:
        cnx = mysql.connector.connect(
            host=ip, port=port, user=user, password=pwd, database=database,
            read_timeout=60, write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query, (clave,))
        result = cursor.fetchone()
        if result:
            return f"Tenemos {result[1]} unidades del producto {result[0]}"
        return "No se encontró el producto o no tiene existencias."
    finally:
        cursor.close()
        cnx.close()
