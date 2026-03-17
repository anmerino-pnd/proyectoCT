import json
import pymysql
import http.client 
import pandas as pd
import mysql.connector
pymysql.install_as_MySQLdb()
from mysql.connector import errorcode
from ct.settings.clients import (
    ip, 
    port, 
    user, 
    pwd, 
    database, 
    url, 
    tokenapi, 
    tokenct, 
    cookie, 
    dominio, 
    boundary)

from typing import List, Dict, cast
import cloudscraper 
import json
import time
import requests 

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
    }
)

scraper.headers.update({
    'Token-api': tokenapi,
    'Token-ct': tokenct,
    'Cookie': cookie
})


class Extraction():
  def __init__(self):
    self.ip = ip
    self.port = port
    self.user = user
    self.pwd = pwd
    self.database = database

  def ids_query(self) -> str:
    query = """
    SELECT DISTINCT pro.idProductos
    FROM productos pro
    JOIN existencias e 
      ON pro.idProductos = e.idProductos
    JOIN precio pre 
      ON pro.idProductos = pre.idProducto
    WHERE pro.idProductos > 0
    AND pro.activo = 1
    ;
    """
    return query

  def get_valid_ids(self) -> list:
    cnx = None
    cursor = None  # ✅ inicializar antes del try garantiza que siempre estén definidas
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        cursor.execute(self.ids_query())
        ids_validos = [cast(tuple, row)[0] for row in cursor.fetchall()]  # ✅ cast a tuple
        return ids_validos
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Hay un error con la contraseña o el usuario")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe")
        else:
            print(err)
        return []
    finally:
        if cursor is not None:   # ✅ ya no necesitamos 'in locals()'
            cursor.close()
        if cnx is not None:
            cnx.close()

  def product_query(self, id):
      query = f"""
      SELECT 
          pro.descripcion_corta_icecat AS nombre,  
          clave,  
          cat.nombre AS categoria,
          m.nombre  AS marca,
          pro.tipo, 
          pro.modelo, 
          pro.descripcion, 
          pro.descripcion_corta,
          pro.palabrasClave
      FROM productos pro
      LEFT JOIN categorias cat 
        ON pro.idCategoria = cat.idCategoria
      LEFT JOIN marcas m 
        ON pro.idMarca = m.idMarca
      WHERE pro.idProductos IN ({id})
      GROUP BY pro.idProductos;
      """
      return query

  def get_products(self, ids_validos: list) -> pd.DataFrame:
    print(ids_validos)
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        filas = []
        for id in ids_validos:
            cursor.execute(self.product_query(id))
            filas.append(cursor.fetchall())

        # ✅ Guard para cursor.description
        if cursor.description is None:
            return pd.DataFrame()

        columnas = [desc[0] for desc in cursor.description]
        datos = []
        for file in filas:
            for producto in file:
                datos.append(producto)
        print(f"Cantidad de productos: {len(datos)}")
        productos = pd.DataFrame(datos, columns=columnas)
        return productos
    
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Hay un error con la contraseña o el usuario")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe")
        else:
            print(err)
        return pd.DataFrame()  # ✅ DataFrame vacío en lugar de None
    finally:
        if cursor is not None:  # ✅ ya no necesitamos 'in locals()'
            cursor.close()
        if cnx is not None:
            cnx.close()

  def current_sales_query(self) -> str:
      # Modificado para no usar JSON_ARRAYAGG y traer listaPrecio y precio en filas separadas
      query = f"""
SELECT 
    pro.descripcion_corta_icecat AS nombre,  
    pros.producto                      AS clave,  
    cat.nombre                        AS categoria,
    m.nombre                          AS marca,
    pro.tipo, 
    pro.modelo, 
    pro.descripcion, 
    pro.descripcion_corta,
    pro.palabrasClave
FROM promociones pros
  INNER JOIN productos pro  
    ON pro.idProductos = pros.idProducto
  LEFT JOIN precio pre 
    ON pros.idProducto = pre.idProducto
  LEFT JOIN categorias cat 
    ON pro.idCategoria = cat.idCategoria
  LEFT JOIN marcas m 
    ON pro.idMarca = m.idMarca
WHERE 
    -- promoción activa 
    pros.fecha_fin    >= CURRENT_DATE

    -- más validaciones
    AND pro.descripcion_corta_icecat != ''
    AND pre.idMoneda IS NOT NULL

GROUP BY 
    pros.idProducto 
ORDER BY 
    pros.importe     ASC,
    pre.listaPrecio;
    """
      return query 

  def get_current_sales(self) -> pd.DataFrame:
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        cursor.execute(self.current_sales_query())

        # ✅ Guard para cursor.description
        if cursor.description is None:
            return pd.DataFrame()

        columnas = [desc[0] for desc in cursor.description]
        datos = [producto for producto in cursor.fetchall()]
        print(f"Cantidad de productos: {len(datos)}")
        sales = pd.DataFrame(datos, columns=columnas)
        return sales

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Hay un error con la contraseña o el usuario")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe")
        else:
            print(err)
        return pd.DataFrame()  # ✅ DataFrame vacío en lugar de None
    finally:
        if cursor is not None:  # ✅ ya no necesitamos 'in locals()'
            cursor.close()
        if cnx is not None:
            cnx.close()

  def sales_query(self, id):
      query = f"""
        SELECT 
            pros.idProducto,
            pro.descripcion_corta_icecat AS nombre,  
            pros.producto                      AS clave,  
            cat.nombre                        AS categoria,
            m.nombre                          AS marca,
            pro.tipo, 
            pro.modelo, 
            pro.descripcion, 
            pro.descripcion_corta,
            pro.palabrasClave
        FROM promociones pros
        INNER JOIN productos pro  
            ON pro.idProductos = pros.idProducto
        LEFT JOIN precio pre 
            ON pros.idProducto = pre.idProducto
        LEFT JOIN categorias cat 
            ON pro.idCategoria = cat.idCategoria
        LEFT JOIN marcas m 
            ON pro.idMarca = m.idMarca
        WHERE 
            -- promoción ya empezó y sigue activa hoy
            pros.fecha_fin    >= CURRENT_DATE

            -- más validaciones
            AND pre.idMoneda IS NOT NULL
            AND pros.producto IN ({id})

        GROUP BY 
            pros.idProducto;
      """
      return query

  def get_sales(self, ids_validos: list) -> pd.DataFrame:
    print(ids_validos)
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        filas = []
        for id in ids_validos:
            cursor.execute(self.product_query(id))
            filas.append(cursor.fetchall())

        # ✅ Guard para cursor.description
        if cursor.description is None:
            return pd.DataFrame()

        columnas = [desc[0] for desc in cursor.description]
        datos = []
        for file in filas:
            for producto in file:
                datos.append(producto)
        print(f"Cantidad de ofertas: {len(datos)}")
        productos = pd.DataFrame(datos, columns=columnas)
        return productos
    
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Hay un error con la contraseña o el usuario")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe")
        else:
            print(err)
        return pd.DataFrame()  # ✅ DataFrame vacío en lugar de None
    finally:
        if cursor is not None:  # ✅ ya no necesitamos 'in locals()'
            cursor.close()
        if cnx is not None:
            cnx.close()

  def get_existences(self) -> pd.DataFrame:
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        cursor.execute("""
        SELECT pro.clave, SUM(e.cantidad) AS existencias
        FROM existencias e
        LEFT JOIN productos pro ON pro.idProductos = e.idProductos
        WHERE pro.idProductos > 0
        AND e.cantidad > 3
        GROUP BY pro.idProductos;
        """)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=["clave", "existencias"])
        return df

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Hay un error con la contraseña o el usuario")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe")
        else:
            print(err)
        return pd.DataFrame()  # ✅ DataFrame vacío en lugar de None
    finally:
        if cursor is not None:  # ✅ ya no necesitamos 'in locals()'
            cursor.close()
        if cnx is not None:
            cnx.close()

  def get_specifications_cloudscraper(self, claves: List[str], max_retries: int = 3, sleep_seconds: float = 0.15) -> Dict[str, dict]:
    specs = {}
    errors = {}
    for clave in claves:
       retries = 0
       success = False

       while retries < max_retries and not success:
            try:
                payload = {'claveProducto': clave}
                response = scraper.post(url, data=payload, timeout=5)  # timeout importante
                content_type = response.headers.get('Content-Type', '').lower()

                if response.status_code == 200:
                    if 'application/json' in content_type:
                        json_response = response.json()

                        if isinstance(json_response, dict):
                            respuesta = json_response.get("respuesta", {})
                            if respuesta.get("status") == "success":
                                specs[clave] = json_response
                                success = True
                                time.sleep(sleep_seconds)
                                break
                            else:
                                raise ValueError(f"Respuesta no exitosa para clave {clave}")
                        else:
                            raise ValueError("Estructura de JSON inválida")
                    elif '<html' in response.text.lower():
                        raise ValueError("Respuesta HTML inesperada (posible bloqueo)")
                    else:
                        raise ValueError("Respuesta desconocida sin JSON")
                elif response.status_code == 403:
                    raise RuntimeError("403 Forbidden: IP bloqueada")
                else:
                    raise RuntimeError(f"HTTP error {response.status_code}")

            except (requests.exceptions.RequestException, json.JSONDecodeError, cloudscraper.exceptions.CloudflareException) as e:
                retries += 1
                wait_time = min(1.5, sleep_seconds * (2 ** retries))  # backoff controlado
                time.sleep(wait_time)
                if retries == max_retries:
                    errors[clave] = str(e)
            except Exception as e:
                errors[clave] = str(e)
                break

    if errors:
        print(f"⚠️ {len(errors)} claves fallaron al obtener ficha técnica.")

    return specs

  def get_specifications(self, claves: list) -> dict:
    return self.get_specifications_cloudscraper(claves) 

  def update_products(self, claves_guardadas):
    query = """
    SELECT DISTINCT pro.clave
    FROM productos pro
    JOIN existencias e ON pro.idProductos = e.idProductos
    JOIN precio pre ON pro.idProductos = pre.idProducto
    WHERE pro.idProductos > 0
    AND pro.activo = 1;
    """
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        cursor.execute(query)

        # ✅ cast a tuple para acceder por índice
        claves_actuales = [cast(tuple, row)[0] for row in cursor.fetchall()]
        claves_nuevas: list = list(set(claves_actuales) - set(claves_guardadas))
        claves_sobrantes = list(set(claves_guardadas) - set(claves_actuales))
        print(f"Número de nuevas claves: {len(claves_nuevas)}")
        print(f"Número de claves sobrantes: {len(claves_sobrantes)}")

        ids_validos = []
        for clave_nueva in claves_nuevas:
            print(clave_nueva)
            cursor.execute(
                "SELECT DISTINCT idProductos FROM productos WHERE clave = %s",
                (clave_nueva,)
            )
            row = cursor.fetchone()
            if row:
                ids_validos.append(cast(tuple, row)[0])  # ✅ cast a tuple

        return ids_validos, claves_sobrantes

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("❌ Error: usuario o contraseña incorrectos.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("❌ Error: la base de datos no existe.")
        else:
            print(f"❌ Error de MySQL: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

  def update_sales(self, claves_guardadas):
    query = """
      SELECT DISTINCT pro.producto
      FROM promociones pro
      JOIN existencias e ON pro.idProducto = e.idProductos
      JOIN precio pre ON pro.idProducto = pre.idProducto;
    """
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(
            host=self.ip,
            port=self.port,
            user=self.user,
            password=self.pwd,
            database=self.database,
            read_timeout=60,
            write_timeout=15
        )
        cursor = cnx.cursor(buffered=False)
        cursor.execute(query)

        # ✅ cast a tuple para acceder por índice
        claves_actuales = [cast(tuple, row)[0] for row in cursor.fetchall()]
        claves_nuevas: list = list(set(claves_actuales) - set(claves_guardadas))
        claves_sobrantes = list(set(claves_guardadas) - set(claves_actuales))
        print(f"Número de nuevas claves: {len(claves_nuevas)}")
        print(f"Número de claves sobrantes: {len(claves_sobrantes)}")

        ids_validos = []
        for clave_nueva in claves_nuevas:
            print(clave_nueva)
            cursor.execute(
                "SELECT DISTINCT idProducto FROM promociones WHERE producto = %s",
                (clave_nueva,)
            )
            row = cursor.fetchone()
            if row:
                ids_validos.append(cast(tuple, row)[0])  # ✅ cast a tuple

        return ids_validos, claves_sobrantes

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("❌ Error: usuario o contraseña incorrectos.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("❌ Error: la base de datos no existe.")
        else:
            print(f"❌ Error de MySQL: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()
