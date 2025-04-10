import json
import http.client 
import pandas as pd
import mysql.connector
from mysql.connector import errorcode
from ct.clients import ip, port, user, pwd, database, url, tokenapi, tokenct, cookie, dominio, boundary

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
    limit 3
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
            pro.idProductos, 
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
            ) AS detalles_precio
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
            pros.idProducto,
            pro.descripcion_corta_icecat AS nombre,  
            pros.producto,  
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
            ) AS lista_precios  
        FROM promociones pros
        INNER JOIN productos pro  
          ON pro.idProductos = pros.idProducto
        LEFT JOIN (
            SELECT DISTINCT idProducto, listaPrecio, precio
            FROM precio
        ) pre 
          ON pros.idProducto = pre.idProducto 
        LEFT JOIN categorias cat 
          ON pro.idCategoria = cat.idCategoria
        LEFT JOIN marcas m 
          ON pro.idMarca = m.idMarca
        WHERE pros.fecha_fin >= CURRENT_DATE
        GROUP BY pros.idProducto
        ORDER BY pros.importe ASC
        limit 3
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
  


  def get_specifications(self, claves: list) -> dict:
    conn = http.client.HTTPSConnection(dominio)
    headers = {
      'Token-api': tokenapi,
      'Token-ct': tokenct,
      'Cookie': cookie,
      'Content-type': 'multipart/form-data; boundary={}'.format(boundary)
    }
    specs = {}
    try:
        for clave in claves:
            # Crear el cuerpo de la solicitud de una sola vez con un formato más limpio
            body = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="claveProducto"\r\n'
                f'Content-Type: text/plain\r\n'
                f'\r\n'
                f'{clave}\r\n'
                f'--{boundary}--\r\n'
            ).encode('utf-8')  # Convertir todo a bytes de una vez
            
            conn.request("POST", "/producto/obtenerFichaTecnicaXml", body, headers)
            res = conn.getresponse()
            if res.status == 200:
                response_data = res.read()  # Leer los datos de la respuesta
                json_response = json.loads(response_data.decode('utf-8'))
                specs[clave] = json_response                
            else:
                print(f"Error {res.status} para el producto {clave}: {res.read().decode('utf-8')}")
        return specs
    except http.client.HTTPException as e:
        print(f"Error en la conexión HTTP para el producto {clave}: {e}")
    except ConnectionError as e:
        print(f"Error de conexión para el producto {clave}: {e}")
    except TimeoutError as e:
        print(f"La solicitud superó el tiempo límite para el producto {clave}: {e}")
    except Exception as e:
        print(f"Ocurrió un error inesperado para el producto {clave}: {e}")
    finally:
        conn.close()