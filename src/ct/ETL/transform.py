import json
import pprint
import pandas as pd
from ct.ETL.extraction import Extraction
from pymongo import MongoClient
from ct.settings.clients import mongo_uri, mongo_db, mongo_collection_specifications # Asume que tienes esta configuración


class Transform:
    def __init__(self):
        self.data = Extraction()
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
        Se ajusta para el cambio de nombre de columna de 'detalles_precio' a 'detalles_sucursales'.
        """
        products : pd.DataFrame = self.data.get_products()
        
        products['descripcion'] = products['descripcion'].fillna('').astype(str).replace('0', '')
        products['descripcion_corta'] = products['descripcion_corta'].fillna('').astype(str).replace('0', '')
        products['palabrasClave'] = products['palabrasClave'].fillna('').astype(str).replace('0', '')
        products['detalles'] = products['descripcion'] + ' ' + products['descripcion_corta'] + ' ' + products['palabrasClave']
        products['detalles'] = products['detalles'].str.strip()
        #products["lista_precio"] = products["lista_precio"].apply(json.loads) 
        
        columns = ['nombre', 'clave', 'categoria', 'marca', 'tipo',
                   'modelo', 'detalles']#, 'lista_precio', 'moneda'] 
        data_products = products[columns].copy()
        for col in data_products.columns:
            #if col != 'lista_precio':
            data_products[col] = data_products[col].astype(str)
        return data_products
    
    def clean_products(self) -> dict:
        """
        Limpia los datos de productos, obteniendo las fichas técnicas de MongoDB
        o extrayéndolas si no existen. Si no se encuentra o falla, se guarda una ficha vacía.
        """
        products = self.transform_products()
        claves = products['clave'].unique().tolist()

        claves_a_buscar = []
        fichas_tecnicas_existentes = {}

        for clave in claves:
            ficha_existente = self.specifications_collection.find_one({"clave": clave})
            if ficha_existente:
                fichas_tecnicas_existentes[clave] = ficha_existente['data']
            else:
                claves_a_buscar.append(clave)

        new_specs = {}
        if claves_a_buscar:
            print(f"Extrayendo {len(claves_a_buscar)} fichas técnicas nuevas...")
            raw_new_specs = self.data.get_specifications(claves_a_buscar)
            new_specs = self.transform_specifications(raw_new_specs)

            for clave, data in new_specs.items():
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": data}},
                    upsert=True
                )
            print(f"Guardadas {len(new_specs)} fichas técnicas nuevas en MongoDB.")

            # Guardar vacías las que fallaron
            claves_procesadas = set(fichas_tecnicas_existentes.keys()) | set(new_specs.keys())
            claves_fallidas = set(claves) - claves_procesadas
            for clave in claves_fallidas:
                print(f"Advertencia: No se encontró ficha técnica para la clave {clave}. Se añadirá vacía.")
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": {}}},
                    upsert=True
                )

        # Combinar todo
        all_fichas_tecnicas = {
            doc["clave"]: doc.get("data", {})
            for doc in self.specifications_collection.find({"clave": {"$in": claves}})
        }

        products_dict = products.to_dict(orient='records')
        for producto in products_dict:
            ficha = all_fichas_tecnicas.get(producto['clave'], {})
            producto['fichaTecnica'] = ficha.get('fichaTecnica', {})
            producto['resumen'] = ficha.get('resumen', {})
        return products_dict


    def transform_sales(self) -> pd.DataFrame:
        """
        Transforma los datos brutos de ventas (ofertas) en un DataFrame limpio y consolida
        los detalles de precios por lista para cada oferta única, asegurando que 'precios_por_lista'
        contenga entradas distintas y que 'moneda' se maneje como una columna de la oferta principal.
        """
        sales_raw: pd.DataFrame = self.data.get_current_sales()
        if sales_raw.empty:
            return pd.DataFrame()

        # Limpieza de columnas de texto
        sales_raw['descripcion'] = sales_raw['descripcion'].fillna('').astype(str).replace('0', '')
        sales_raw['descripcion_corta'] = sales_raw['descripcion_corta'].fillna('').astype(str).replace('0', '')
        sales_raw['palabrasClave'] = sales_raw['palabrasClave'].fillna('').astype(str).replace('0', '')
        sales_raw['detalles'] = sales_raw['descripcion'] + ' ' + sales_raw['descripcion_corta'] + ' ' + sales_raw['palabrasClave']
        sales_raw['detalles'] = sales_raw['detalles'].str.strip()

        # Columnas para identificar una oferta única (incluyendo 'moneda' aquí)
        # offer_id_cols = ['nombre', 'clave', 'categoria', 'marca', 'tipo',
        #     'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
        #     'Unidades', 'limitadoA', 'ProductosGratis', 'fecha_inicio', 'fecha_fin', 'moneda' 
        # ]


        # grouped_sales = sales_raw.groupby(offer_id_cols).apply(
        #     lambda x: {
        #         "lista_precio": list(
        #             {
        #                 (str(lp), str(p)) 
        #                 for lp, p in zip(x['listaPrecio'], x['precio'])
        #             }
        #         )
        #     }
        # ).reset_index()

        # sales_transformed = grouped_sales.rename(columns={0: 'lista_precio'})
        # sales_transformed['lista_precio'] = sales_transformed['lista_precio'].apply(
        #     lambda d: sorted(
        #             [
        #                 {"listaPrecio": lp, "precio": p}
        #                 for lp, p in d["lista_precio"]
        #             ],
        #             key=lambda item: int(item["listaPrecio"])  
        #         )
        #     )

        for col in sales_raw.columns:
        #     if col not in ['lista_precio']: 
                sales_raw[col] = sales_raw[col].astype(str)

        sales_raw['descuento'] = sales_raw['descuento'].apply(lambda x: f"{x}%" if x.replace('.', '', 1).isdigit() else x)
        sales_raw['moneda'] = sales_raw['moneda'].replace({'0': 'USD', '1': 'MXN'})

        final_columns = [
            'idProducto', 'nombre', 'clave', 'categoria', 'marca', 'tipo',
            'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
            'Unidades', 'limitadoA', 'ProductosGratis', 'fecha_inicio', 'fecha_fin',
            'moneda',# 'lista_precio' 
        ]
        
        existing_cols = [col for col in final_columns if col in sales_raw.columns]
        data_sales = sales_raw[existing_cols].copy()

        return data_sales
        
    def clean_sales(self) -> dict:
        """
        Limpia los datos de ventas (ofertas), obteniendo las fichas técnicas de MongoDB
        o extrayéndolas si no existen. Si no se encuentra o falla, se guarda una ficha vacía.
        """
        sales = self.transform_sales()
        if sales.empty:
            return []

        claves = sales['clave'].unique().tolist()

        claves_a_buscar = []
        fichas_tecnicas_existentes = {}

        for clave in claves:
            ficha_existente = self.specifications_collection.find_one({"clave": clave})
            if ficha_existente:
                fichas_tecnicas_existentes[clave] = ficha_existente['data']
            else:
                claves_a_buscar.append(clave)

        new_specs = {}
        if claves_a_buscar:
            print(f"Extrayendo {len(claves_a_buscar)} fichas técnicas nuevas para ofertas...")
            raw_new_specs = self.data.get_specifications(claves_a_buscar)
            new_specs = self.transform_specifications(raw_new_specs)

            for clave, data in new_specs.items():
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": data}},
                    upsert=True
                )
            print(f"Guardadas {len(new_specs)} fichas técnicas nuevas para ofertas en MongoDB.")

            # Guardar vacías las que fallaron
            claves_procesadas = set(fichas_tecnicas_existentes.keys()) | set(new_specs.keys())
            claves_fallidas = set(claves) - claves_procesadas
            for clave in claves_fallidas:
                print(f"Advertencia: No se encontró ficha técnica para la clave {clave}. Se añadirá vacía.")
                self.specifications_collection.update_one(
                    {"clave": clave},
                    {"$set": {"clave": clave, "data": {}}},
                    upsert=True
                )

        # Combinar todo
        all_fichas_tecnicas = {
            doc["clave"]: doc.get("data", {})
            for doc in self.specifications_collection.find({"clave": {"$in": claves}})
        }

        sales_dict = sales.to_dict(orient='records')
        for sale in sales_dict:
            ficha = all_fichas_tecnicas.get(sale['clave'], {})
            sale['fichaTecnica'] = ficha.get('fichaTecnica', {})
            sale['resumen'] = ficha.get('resumen', {})

        return sales_dict
