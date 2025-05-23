import json
import http.client 
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
from ct.clients import ip, port, user, pwd, database, url, tokenapi, tokenct, cookie, dominio, boundary

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
    WHERE e.cantidad > 0
    AND pro.idProductos > 0
    LIMIT 10
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
        GROUP BY pro.idProductos;"""
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
            pro.descripcion_corta_icecat AS nombre,  
            pros.producto as clave,  
            cat.nombre AS categoria,
            m.nombre  AS marca,
            pro.tipo, 
            pro.modelo, 
            pro.descripcion, 
            pro.descripcion_corta,
            pro.palabrasClave,
            pros.importe as precio_oferta,
            pros.porcentaje as descuento,
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
        ORDER BY pros.importe ASC
        LIMIT 10
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


  def get_specifications_cloudscraper(self, claves: list) -> dict:
      specs = {}
      for clave in claves:
          try:
              payload = {'claveProducto': clave}
              response = scraper.post(url, data=payload)
              if response.status_code == 200:
                  content_type = response.headers.get('Content-Type', '').lower()

                  if 'application/json' in content_type:
                      try:
                          json_response = response.json()

                          # Validar contenido lógico del JSON
                          if isinstance(json_response, dict):
                              respuesta = json_response.get("respuesta", {})
                              if respuesta.get("status") == "success":
                                  specs[clave] = json_response
                          else:
                              raise RuntimeError(f"[{clave}] JSON no tiene formato esperado: {json_response}")

                      except (json.JSONDecodeError, ValueError) as e:
                          raise RuntimeError(f"[{clave}] JSON inválido o estructura inesperada: {e}")

                  else:
                      if response.text.strip().startswith('<!DOCTYPE html>') or '<html' in response.text.lower():
                          raise RuntimeError(f"[{clave}] HTML inesperado (posible redirección/Cloudflare)")
                      else:
                          raise RuntimeError(f"[{clave}] Respuesta 200 sin JSON ni HTML. Content-Type: {content_type}")

              elif response.status_code == 403:
                  raise RuntimeError(f"[{clave}] Error 403 (Forbidden). Cloudscraper bloqueado.")

              else:
                  raise RuntimeError(f"[{clave}] HTTP Error {response.status_code}")

          except requests.exceptions.Timeout:
              raise RuntimeError(f"[{clave}] Timeout con cloudscraper")
          except requests.exceptions.RequestException as e:
              raise RuntimeError(f"[{clave}] Error de red: {e}")
          except cloudscraper.exceptions.CloudflareException as e:
              raise RuntimeError(f"[{clave}] CloudflareException: {e}")
          except Exception as e:
              raise RuntimeError(f"[{clave}] Error inesperado: {e}")

      return specs


  def get_specifications(self, claves: list) -> dict:
    return self.get_specifications_cloudscraper(claves) 
