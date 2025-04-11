import json
import pprint
import pandas as pd
from ct.ETL.extraction import Extraction

class Transform:
    def __init__(self):
        self.data = Extraction()

    def extract_features(self, specifications):
        resultado = {
        'fichaTecnica': {},  
        'resumen': {}  
    }
            # Extraer características de ProductFeature
        if "ProductFeature" in specifications:
            product_feature = specifications["ProductFeature"]

            # Si es una cadena, lo ignoramos o lo manejamos según sea necesario
            if isinstance(product_feature, str):
                print(f"Advertencia: `ProductFeature` es una cadena en lugar de una lista. Valor: {product_feature}")
            elif isinstance(product_feature, list):  
                for feature in product_feature:
                    if not isinstance(feature, dict):  # Saltar elementos que no sean diccionarios
                        print(f"Advertencia: Se esperaba un diccionario, pero se encontró {type(feature)}: {feature}")
                        continue  

                    local_value = feature.get("@attributes", {}).get("Presentation_Value", "No disponible")
                    name = feature.get("Feature", {}).get("Name", {}).get("@attributes", {}).get("Value", "Sin nombre")

                    resultado['fichaTecnica'][name] = local_value

        # Agregar SummaryDescription si está presente
        if "SummaryDescription" in specifications:
            resultado['resumen']["ShortSummary"] = specifications["SummaryDescription"].get("ShortSummaryDescription", "No disponible")
            resultado['resumen']["LongSummary"] = specifications["SummaryDescription"].get("LongSummaryDescription", "No disponible")

        return resultado

    def transform_specifications(self, specs: dict) -> dict:
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
        products : pd.DataFrame = self.data.get_products()
        products['descripcion'] = products['descripcion'].fillna('').astype(str).replace('0', '')
        products['descripcion_corta'] = products['descripcion_corta'].fillna('').astype(str).replace('0', '')
        products['palabrasClave'] = products['palabrasClave'].fillna('').astype(str).replace('0', '')
        products['detalles'] = products['descripcion'] + ' ' + products['descripcion_corta'] + ' ' + products['palabrasClave']
        products['detalles'] = products['detalles'].str.strip()
        products["detalles_precio"] = products["detalles_precio"].apply(json.loads)
        
        columns = ['idProductos', 'nombre', 'clave', 'categoria', 'marca', 'tipo',
       'modelo', 'detalles', 'detalles_precio', 'moneda']
        return products[columns]
    
    def clean_products(self) -> dict:
        products = self.transform_products()
        claves = products['clave'].unique().tolist()
        specs = self.data.get_specifications(claves)
        fichas_tecnicas = self.transform_specifications(specs)
        claves_fichas = fichas_tecnicas.keys()
        products_dict : dict = products.to_dict(orient='records')
        for producto in products_dict:
            if producto['clave'] in claves_fichas:  # Verificamos si la clave existe
                ficha = fichas_tecnicas[producto['clave']]
                producto['fichaTecnica'] = ficha['fichaTecnica']
                producto['resumen'] = ficha['resumen']
        pprint.pprint(products_dict[0].keys(), indent=4)
        pprint.pprint(products_dict[0], indent=4)
        return products_dict

    def transform_sales(self) -> pd.DataFrame:
        sales :pd.DataFrame = self.data.get_current_sales()
        sales['descripcion'] = sales['descripcion'].fillna('').astype(str).replace('0', '')
        sales['descripcion_corta'] = sales['descripcion_corta'].fillna('').astype(str).replace('0', '')
        sales['palabrasClave'] = sales['palabrasClave'].fillna('').astype(str).replace('0', '')
        sales['detalles'] = sales['descripcion'] + ' ' + sales['descripcion_corta'] + ' ' + sales['palabrasClave']
        sales['detalles'] = sales['detalles'].str.strip()
        
        columns = ['idProducto', 'nombre', 'producto', 'categoria', 'marca', 'tipo', 
                   'modelo', 'detalles', 'precio_oferta', 'descuento', 'EnCompraDE',
                   'Unidades', 'limitadoA', 'fecha_inicio', 'fecha_fin', 'lista_precios', 'moneda']
        data_sales = sales[columns].copy()
        for col in data_sales.columns:
            if col != 'idProducto':  
                data_sales[col] = data_sales[col].astype(str)
        data_sales['descuento'] = data_sales['descuento'].apply(lambda x: f"{x}%" if x.replace('.', '', 1).isdigit() else x)
        return data_sales
        
    def clean_sales(self) -> dict:
        sales = self.transform_sales()
        claves = sales['producto'].unique().tolist()
        specs = self.data.get_specifications(claves)
        fichas_tecnicas = self.transform_specifications(specs)
        claves_fichas = fichas_tecnicas.keys()
        sales_dict : dict = sales.to_dict(orient='records')
        for sale in sales_dict:
            if sale['producto'] in claves_fichas:
                ficha = fichas_tecnicas[sale['producto']]
                sale['fichaTecnica'] = ficha['fichaTecnica']
                sale['resumen'] = ficha['resumen']
        pprint.pprint(sales_dict[0].keys(), indent=4)
        pprint.pprint(sales_dict[0], indent=4)
        return sales_dict



    
