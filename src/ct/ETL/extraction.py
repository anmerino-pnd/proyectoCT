import json
import http.client 
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
from ct.clients import ip, port, user, pwd, database, url, tokenapi, tokenct, cookie, dominio, boundary

from typing import List, Dict
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
    WHERE e.cantidad > 10
    AND pro.idProductos > 0
    ;
    """
    return query

  def get_valid_ids(self) -> list:
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
      ids_validos = [row[0] for row in cursor.fetchall()]
      return ids_validos
    except mysql.connector.Error as err:
      if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
          print("Hay un error con la contraseña o el usuario")
      elif err.errno == errorcode.ER_BAD_DB_ERROR:
          print("La base de datos no existe")
      else:
          print(err)
    finally:
      cursor.close()
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
            pro.palabrasClave,
            JSON_ARRAYAGG(
                JSON_OBJECT(
                    'listaPrecio', pre.listaPrecio,
                    'precio', pre.precio
                )
            ) AS detalles_precio,
            pre.idMoneda AS moneda
        FROM productos pro
        LEFT JOIN precio pre 
          ON pro.idProductos = pre.idProducto 
        LEFT JOIN categorias cat 
          ON pro.idCategoria = cat.idCategoria
        LEFT JOIN marcas m 
          ON pro.idMarca = m.idMarca
        WHERE pro.idProductos IN ({id})
        GROUP BY pro.idProductos
        ;"""
     return query

  def get_products(self) -> pd.DataFrame:
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
      ids_validos = self.get_valid_ids()
      filas = []
      for id in ids_validos:
          cursor.execute(self.product_query(id))
          filas.append(cursor.fetchall())
      columnas = [desc[0] for desc in cursor.description]
      datos = []
      for file in filas:
          for producto in file:
              datos.append(producto)
      productos = pd.DataFrame(datos, columns=columnas)
      return productos
    
    except mysql.connector.Error as err:
      if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
          print("Hay un error con la contraseña o el usuario")
      elif err.errno == errorcode.ER_BAD_DB_ERROR:
          print("La base de datos no existe")
      else:
          print(err)
      return None
    finally:
      cursor.close()
      cnx.close()

  def current_sales_query(self) -> str:
      query = f"""
      SELECT 
          pros.idProducto,
          pro.descripcion_corta_icecat AS nombre,  
          pros.producto AS clave,  
          cat.nombre AS categoria,
          m.nombre  AS marca,
          pro.tipo, 
          pro.modelo, 
          pro.descripcion, 
          pro.descripcion_corta,
          pro.palabrasClave,
          pros.importe AS precio_oferta,
          pros.porcentaje AS descuento,
          pros.EnCompraDE,
          pros.Unidades, 
          pros.limitadoA, 
          pros.ProductosGratis,
          pros.fecha_inicio,
          pros.fecha_fin,
          JSON_UNQUOTE(
        JSON_ARRAYAGG(
            DISTINCT JSON_OBJECT(
          'listaPrecio', pre.listaPrecio,
          'precio', pre.precio
            )
        )
          ) AS lista_precios,
          pre.idMoneda AS moneda
      FROM promociones pros
      INNER JOIN productos pro  
        ON pro.idProductos = pros.idProducto
      LEFT JOIN (
          SELECT DISTINCT idProducto, listaPrecio, precio, idMoneda
          FROM precio
      ) pre 
        ON pros.idProducto = pre.idProducto 
      LEFT JOIN categorias cat 
        ON pro.idCategoria = cat.idCategoria
      LEFT JOIN marcas m 
        ON pro.idMarca = m.idMarca
      WHERE pros.fecha_fin >= CURRENT_DATE
      AND pro.descripcion_corta_icecat != '' 
      GROUP BY pros.idProducto
      HAVING lista_precios IS NOT NULL AND moneda IS NOT NULL
      ORDER BY pros.importe ASC
        ;"""
      return query 

  def get_current_sales(self) -> pd.DataFrame:
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
      columnas = [desc[0] for desc in cursor.description]
      datos = [producto for producto in cursor.fetchall()]
      sales = pd.DataFrame(datos, columns=columnas)
      sales['fecha_inicio'] = pd.to_datetime(sales['fecha_inicio']).dt.strftime('%Y-%m-%d')
      sales['fecha_fin'] = pd.to_datetime(sales['fecha_fin']).dt.strftime('%Y-%m-%d')
      return sales
    except mysql.connector.Error as err:
      if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
          print("Hay un error con la contraseña o el usuario")
      elif err.errno == errorcode.ER_BAD_DB_ERROR:
          print("La base de datos no existe")
      else:
          print(err)
      return None
    finally:
      cursor.close()
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
