import mysql.connector
from pydantic import BaseModel
from ct.settings.clients import ip, port, user, pwd, database
import pymysql
pymysql.install_as_MySQLdb()

class DolarInput(BaseModel):
    dolar: float

    
query = """
SELECT 
	dolar, 
	filtro AS peso_mexicano
FROM monedas_api
LIMIT 1
"""

def dolar_a_peso_tool(dolar: float) -> str:
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=ip,
            port=port,
            user=user,
            password=pwd,
            database=database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        if result:
            return f"El equivalente de {dolar} USD es {(dolar * result[1]):.3f} MXN"
    except mysql.connector.Error as err:
        return f"Error de base de datos: {err}"
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()