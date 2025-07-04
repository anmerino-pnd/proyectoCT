import json
import pprint
import pandas as pd
from ct.ETL.extraction import Extraction
# Asegúrate de importar MongoClient y la configuración de MongoDB para acceder a la nueva colección
from pymongo import MongoClient
from ct.clients import mongo_uri, mongo_db, mongo_collection_specifications # Asume que tienes esta configuración


class Transform:
    def __init__(self):
        self.data = Extraction()
        # Inicializa la conexión a MongoDB para la colección de especificaciones
        self.client = MongoClient("mongodb://localhost:27017")
        self.db = self.client[mongo_db]
        self.specifications_collection = self.db[mongo_collection_specifications]

    def extract_features(self, specifications):
        """
        Extrae características relevantes de la ficha técnica.
        """
        resultado = {
            'fichaTecnica': {},  
            'resumen': {}  
        }
        if "ProductFeature" in specifications:
            product_feature = specifications["ProductFeature"]

            if isinstance(product_feature, str):
                print(f"Advertencia: `ProductFeature` es una cadena en lugar de una lista. Valor: {product_feature}")
            elif isinstance(product_feature, list):  
                for feature in product_feature:
                    if not isinstance(feature, dict):  
                        print(f"Advertencia: Se esperaba un diccionario, pero se encontró {type(feature)}: {feature}")
                        continue  

                    local_value = feature.get("@attributes", {}).get("Presentation_Value", "No disponible")
                    name = feature.get("Feature", {}).get("Name", {}).get("@attributes", {}).get("Value", "Sin nombre")

                    resultado['fichaTecnica'][name] = local_value

        if "SummaryDescription" in specifications:
            resultado['resumen']["ShortSummary"] = specifications["SummaryDescription"].get("ShortSummaryDescription", "No disponible")
            resultado['resumen']["LongSummary"] = specifications["SummaryDescription"].get("LongSummaryDescription", "No disponible")

        return resultado

    def transform_specifications(self, specs: dict) -> dict:
        """
        Transforma las especificaciones brutas obtenidas de la extracción.
        """
        fichas_tecnicas = {}
        for clave_producto, info in specs.items():
            if not isinstance(info, dict):
                print(f"Advertencia: La clave {clave_producto} tiene un formato inesperado y será omitida.")
                continue
            else: 
                match info.get("respuesta", {}):
                    case {"data": data_field} if isinstance(data_field, dict):
                        specifications = data_field.get("Product", {})
                        if not specifications:
                            print(f"Advertencia: El producto {clave_producto} no tiene la clave 'Product'. Se omitirá.")
                            continue
                        fichas_tecnicas[clave_producto] = self.extract_features(specifications)
                    case _:
                        print(f"Advertencia: La clave {clave_producto} no tiene un formato esperado y será omitida.")
        return fichas_tecnicas
    
    def transform_products(self) -> pd.DataFrame:
        """
        Transforma los datos brutos de productos en un DataFrame limpio.
        """
        products : pd.DataFrame = self.data.get_products()
        if products.empty:
            return pd.DataFrame() # Retorna un DataFrame vacío si no hay productos
        
        products['descripcion'] = products['descripcion'].fillna('').astype(str).replace('0', '')
        products['descripcion_corta'] = products['descripcion_corta'].fillna('').astype(str).replace('0', '')
        products['palabrasClave'] = products['palabrasClave'].fillna('').astype(str).replace('0', '')
        products['detalles'] = products['descripcion'] + ' ' + products['descripcion_corta'] + ' ' + products['palabrasClave']
        products['detalles'] = products['detalles'].str.strip()
        products["detalles_precio"] = products["detalles_precio"].apply(json.loads)
        
        columns = ['nombre', 'clave', 'categoria', 'marca', 'tipo',
                   'modelo', 'detalles', 'detalles_precio', 'moneda']
        data_products = products[columns].copy()
        for col in data_products.columns:
            data_products[col] = data_products[col].astype(str)
        return data_products
    
    def clean_products(self) -> dict:
        """
        Limpia los datos de productos, obteniendo las fichas técnicas de MongoDB
        o extrayéndolas si no existen.
        """
        products = self.transform_products()
        
        claves = products['clave'].unique().tolist()
        # Claves para las que necesitamos buscar fichas técnicas (no en BD)
        claves_a_buscar = []
        fichas_tecnicas_existentes = {}

        for clave in claves:
            ficha_existente = self.specifications_collection.find_one({"clave": clave})
            if ficha_existente:
                fichas_tecnicas_existentes[clave] = ficha_existente['data'] # Asume que la data transformada está bajo 'data'
            else:
                claves_a_buscar.append(clave)
        
        # Extraer solo las fichas técnicas que no existen en la BD
        new_specs = {}
        if claves_a_buscar:
            print(f"Extrayendo {len(claves_a_buscar)} fichas técnicas nuevas...")
            raw_new_specs = self.data.get_specifications(claves_a_buscar)
            new_specs = self.transform_specifications(raw_new_specs)
            
            # Guardar las nuevas fichas técnicas en la colección de especificaciones
            for clave, data in new_specs.items():
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": data}}, # Guarda la clave y la ficha técnica transformada
                    upsert=True
                )
            print(f"Guardadas {len(new_specs)} fichas técnicas nuevas en MongoDB.")

        # Combinar fichas técnicas existentes y nuevas
        all_fichas_tecnicas = {**fichas_tecnicas_existentes, **new_specs}
        
        products_dict : dict = products.to_dict(orient='records')
        for producto in products_dict:
            clave_producto = producto['clave']
            if clave_producto in all_fichas_tecnicas:
                ficha = all_fichas_tecnicas[clave_producto]
                producto['fichaTecnica'] = ficha['fichaTecnica']
                producto['resumen'] = ficha['resumen']
            else:
                producto['fichaTecnica'] = {}
                producto['resumen'] = {}
                print(f"Advertencia: No se encontró ficha técnica para la clave {clave_producto}. Se añadirá vacía.")
        return products_dict

    def transform_sales(self) -> pd.DataFrame:
        """
        Transforma los datos brutos de ventas (ofertas) en un DataFrame limpio.
        """
        sales :pd.DataFrame = self.data.get_current_sales()
        if sales.empty:
            return pd.DataFrame() # Retorna un DataFrame vacío si no hay ventas

        sales['descripcion'] = sales['descripcion'].fillna('').astype(str).replace('0', '')
        sales['descripcion_corta'] = sales['descripcion_corta'].fillna('').astype(str).replace('0', '')
        sales['palabrasClave'] = sales['palabrasClave'].fillna('').astype(str).replace('0', '')
        sales['detalles'] = sales['descripcion'] + ' ' + sales['descripcion_corta'] + ' ' + sales['palabrasClave']
        sales['detalles'] = sales['detalles'].str.strip()
        
        columns = ['nombre', 'clave', 'categoria', 'marca', 'tipo', 
                   'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
                   'Unidades', 'limitadoA', 'fecha_inicio', 'fecha_fin', 'lista_precios', 'moneda']
        data_sales = sales[columns].copy()
        for col in data_sales.columns:
            data_sales[col] = data_sales[col].astype(str)
        data_sales['descuento'] = data_sales['descuento'].apply(lambda x: f"{x}%" if x.replace('.', '', 1).isdigit() else x)
        return data_sales
        
    def clean_sales(self) -> dict:
        """
        Limpia los datos de ventas (ofertas), obteniendo las fichas técnicas de MongoDB
        o extrayéndolas si no existen.
        """
        sales = self.transform_sales()
        if sales.empty:
            return []
        
        claves = sales['clave'].unique().tolist()

        # Claves para las que necesitamos buscar fichas técnicas (no en BD)
        claves_a_buscar = []
        fichas_tecnicas_existentes = {}

        for clave in claves:
            ficha_existente = self.specifications_collection.find_one({"clave": clave})
            if ficha_existente:
                fichas_tecnicas_existentes[clave] = ficha_existente['data']
            else:
                claves_a_buscar.append(clave)
        
        # Extraer solo las fichas técnicas que no existen en la BD
        new_specs = {}
        if claves_a_buscar:
            print(f"Extrayendo {len(claves_a_buscar)} fichas técnicas nuevas para ofertas...")
            raw_new_specs = self.data.get_specifications(claves_a_buscar)
            new_specs = self.transform_specifications(raw_new_specs)
            
            # Guardar las nuevas fichas técnicas en la colección de especificaciones
            for clave, data in new_specs.items():
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": data}},
                    upsert=True
                )
            print(f"Guardadas {len(new_specs)} fichas técnicas nuevas para ofertas en MongoDB.")

        # Combinar fichas técnicas existentes y nuevas
        all_fichas_tecnicas = {**fichas_tecnicas_existentes, **new_specs}

        sales_dict : dict = sales.to_dict(orient='records')
        for sale in sales_dict:
            clave_sale = sale['clave']
            if clave_sale in all_fichas_tecnicas:
                ficha = all_fichas_tecnicas[clave_sale]
                sale['fichaTecnica'] = ficha['fichaTecnica']
                sale['resumen'] = ficha['resumen']
            else:
                sale['fichaTecnica'] = {}
                sale['resumen'] = {}
                print(f"Advertencia: No se encontró ficha técnica para la clave {clave_sale}. Se añadirá vacía.")
        return sales_dict
