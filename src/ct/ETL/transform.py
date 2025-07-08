import json
import pprint
import pandas as pd
from ct.ETL.extraction import Extraction
from pymongo import MongoClient
from ct.clients import mongo_uri, mongo_db, mongo_collection_specifications # Asume que tienes esta configuración


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
        products["lista_precio"] = products["lista_precio"].apply(json.loads) 
        
        columns = ['nombre', 'clave', 'categoria', 'marca', 'tipo',
                   'modelo', 'detalles', 'lista_precio', 'moneda'] 
        data_products = products[columns].copy()
        for col in data_products.columns:
            if col != 'lista_precio':
                data_products[col] = data_products[col].astype(str)
        return data_products
    
    def clean_products(self) -> dict:
        """
        Limpia los datos de productos, obteniendo las fichas técnicas de MongoDB
        o extrayéndolas si no existen.
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
        offer_id_cols = [
            'idProducto', 'nombre', 'clave', 'categoria', 'marca', 'tipo',
            'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
            'Unidades', 'limitadoA', 'ProductosGratis', 'fecha_inicio', 'fecha_fin', 'moneda' 
        ]


        grouped_sales = sales_raw.groupby(offer_id_cols).apply(
            lambda x: {
                "detalles_sucursales": list(
                    {
                        (str(lp), str(p)) 
                        for lp, p in zip(x['listaPrecio'], x['precio'])
                    }
                )
            }
        ).reset_index()

        sales_transformed = grouped_sales.rename(columns={0: 'lista_precio'})
        sales_transformed['lista_precio'] = sales_transformed['lista_precio'].apply(
            lambda d: sorted(
                    [
                        {"listaPrecio": lp, "precio": p}
                        for lp, p in d["lista_precio"]
                    ],
                    key=lambda item: int(item["listaPrecio"])  
                )
            )

        for col in sales_transformed.columns:
            if col not in ['listaPrecio']: 
                sales_transformed[col] = sales_transformed[col].astype(str)

        sales_transformed['descuento'] = sales_transformed['descuento'].apply(lambda x: f"{x}%" if x.replace('.', '', 1).isdigit() else x)
        

        final_columns = [
            'idProducto', 'nombre', 'clave', 'categoria', 'marca', 'tipo',
            'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
            'Unidades', 'limitadoA', 'ProductosGratis', 'fecha_inicio', 'fecha_fin',
            'moneda', 'listaPrecio' 
        ]
        
        existing_cols = [col for col in final_columns if col in sales_transformed.columns]
        data_sales = sales_transformed[existing_cols].copy()

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
