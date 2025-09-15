import pandas as pd
from ct.ETL.extraction import Extraction
from pymongo import MongoClient
from ct.settings.clients import mongo_db, mongo_collection_specifications 


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
    
    def _get_all_specifications(self, claves: list) -> dict:
        """
        Método privado para obtener fichas técnicas, tanto de la BD como nuevas.
        """
        claves_a_buscar = []
        fichas_tecnicas_existentes = {}

        for clave in claves:
            ficha_existente = self.specifications_collection.find_one({"clave": clave})
            if ficha_existente:
                fichas_tecnicas_existentes[clave] = ficha_existente.get('data', {})
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
        
        return {**fichas_tecnicas_existentes, **new_specs}

    def transform_products(self) -> pd.DataFrame:
        """
        Transforma los datos brutos de productos en un DataFrame limpio y estandarizado.
        """
        products = self.data.get_products()
        if products.empty:
            return pd.DataFrame()

        cols_to_clean = ['descripcion', 'descripcion_corta', 'palabrasClave']
        for col in cols_to_clean:
            products[col] = products[col].fillna('').astype(str).replace('0', '').str.strip()

        products['informacion'] = products['descripcion'].str.cat(
            products[['descripcion_corta', 'palabrasClave', 'categoria', 'tipo', 'marca']],
            sep=' '
        ).str.strip()
        
        cols_info = ['nombre', 'modelo']
        for col in cols_info:
            products[col] = products[col].fillna('').astype(str)

        products['contexto'] = products[cols_info[0]].str.cat(
            products[cols_info[1:]],
            sep=', '
        ).str.strip()

        final_cols = ['clave', 'contexto', 'informacion']
        return products[final_cols].copy()
    
    def clean_products(self) -> dict:
        """
        Limpia los datos, separa la información de contexto del contenido principal
        y devuelve un diccionario listo para ser procesado y chunked.
        """
        products = self.transform_products()
        if products.empty:
            return {}

        claves = products['clave'].unique().tolist()
        all_fichas_tecnicas = self._get_all_specifications(claves)

        documentos_finales = {}
        for index, row in products.iterrows():
            clave = row['clave']
            
            # La información clave que queremos repetir en cada chunk
            informacion_contexto = row['contexto']
            
            contenido_parts = []

            if row['informacion']:
                contenido_parts.append(f"{row['informacion']}")

            ficha = all_fichas_tecnicas.get(clave)
            if ficha:
                resumen = ficha.get('resumen', {})
                if resumen:
                    resumen_texto = f"{resumen.get('ShortSummary', '')} {resumen.get('LongSummary', '')}".strip()
                    if resumen_texto and resumen_texto != "No disponible":
                        contenido_parts.append(f"{resumen_texto}")
                
                detalles_ficha = ficha.get('fichaTecnica', {})
                if detalles_ficha:
                    detalles_str = ", ".join([f"{k}: {v}" for k, v in detalles_ficha.items()])
                    contenido_parts.append(f"{detalles_str}.")

            # Guardamos el contexto y el contenido por separado
            documentos_finales[clave] = {
                "contexto": informacion_contexto,
                "informacion": " ".join(contenido_parts)
            }
            
        return documentos_finales

    def transform_sales(self) -> pd.DataFrame:
        """
        Transforma los datos brutos de ventas (ofertas) en un DataFrame limpio.
        """
        sales_raw: pd.DataFrame = self.data.get_current_sales()
        if sales_raw.empty:
            return pd.DataFrame()

        cols_detalles = ['descripcion', 'descripcion_corta', 'palabrasClave']
        for col in cols_detalles:
            sales_raw[col] = sales_raw[col].fillna('').astype(str).replace('0', '').str.strip()
        
        sales_raw['informacion'] = sales_raw['descripcion'].str.cat(
            sales_raw[['descripcion_corta', 'palabrasClave', 'categoria', 'tipo', 'marca']], 
            sep=' '
        ).str.strip()

        cols_info = ['nombre', 'modelo']
        for col in cols_info:
            sales_raw[col] = sales_raw[col].fillna('').astype(str)

        sales_raw['contexto'] = sales_raw[cols_info[0]].str.cat(
            sales_raw[cols_info[1:]], 
            sep=', '
        ).str.strip()

        final_cols = ['clave', 'contexto', 'informacion']
        return sales_raw[final_cols].copy()

    def clean_sales(self) -> dict:
        """
        Limpia los datos de ventas, separando la información de contexto del contenido,
        similar a clean_products.
        """
        sales = self.transform_sales()
        if sales.empty:
            return {}

        claves = sales['clave'].unique().tolist()
        all_fichas_tecnicas = self._get_all_specifications(claves)

        documentos_finales = {}
        for index, row in sales.iterrows():
            clave = row['clave']
            
            informacion_contexto = row['contexto']
            contenido_parts = [] 

            if row['informacion']:
                contenido_parts.append(f"{row['informacion']}.")

            ficha = all_fichas_tecnicas.get(clave)
            if ficha:
                resumen = ficha.get('resumen', {})
                if resumen:
                    resumen_texto = f"{resumen.get('ShortSummary', '')} {resumen.get('LongSummary', '')}".strip()
                    if resumen_texto and resumen_texto != "No disponible":
                        contenido_parts.append(f"{resumen_texto}")
                
                detalles_ficha = ficha.get('fichaTecnica', {})
                if detalles_ficha:
                    detalles_str = ", ".join([f"{k}: {v}" for k, v in detalles_ficha.items()])
                    contenido_parts.append(f"{detalles_str}.")

            documentos_finales[clave] = {
                "contexto": informacion_contexto,
                "informacion": " ".join(contenido_parts)
            }
            
        return documentos_finales
