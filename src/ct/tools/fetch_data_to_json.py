
from ct.settings.clients import ip, port, user, pwd, database
import mysql.connector
import json

def fetch_data_as_json(query):
    """
    Ejecuta una consulta SQL y devuelve los resultados como una cadena JSON.
    
    Args:
        query (str): La consulta SQL a ejecutar.
        host (str): La dirección IP del servidor de la base de datos.
        port (int): El puerto de la base de datos.
        user (str): El nombre de usuario.
        password (str): La contraseña del usuario.
        database_name (str): El nombre de la base de datos.

    Returns:
        str: Una cadena JSON que representa los resultados de la consulta.
             Devuelve None en caso de error o si no hay resultados.
    """
    cnx = None
    cursor = None
    try:
        # 1. Establece la conexión a la base de datos
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

        # 2. Ejecuta la consulta
        cursor.execute(query)

        # 3. Obtiene los nombres de las columnas del cursor.description
        # Esto es crucial para crear los pares clave-valor del JSON
        column_names = [col[0] for col in cursor.description]

        # 4. Obtiene todos los resultados de la consulta
        results = cursor.fetchall()
        
        # 5. Convierte cada fila en un diccionario y los agrega a una lista
        data_list = []
        for row in results:
            row_dict = dict(zip(column_names, row))
            data_list.append(row_dict)

        # 6. Serializa la lista de diccionarios a una cadena JSON
        return json.dumps(data_list, indent=4, ensure_ascii=False)

    except mysql.connector.Error as err:
        print(f"Error de base de datos: {err}")
        return None
    finally:
        # Cierra el cursor y la conexión de forma segura
        if cursor:
            cursor.close()
        if cnx and cnx.is_connected():
            cnx.close()