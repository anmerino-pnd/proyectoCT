from ct.ETL.pipeline import update_products, load_sales_products
from ct.settings.clients import reload_vectors_post
import requests

if __name__ == "__main__":
    changed = update_products()
    if changed:
        load_sales_products()  # merge de productos y ofertas
        print("Vector store regenerado. Notificando servidor...")
        requests.post(reload_vectors_post, timeout=10, verify=False)
    else:
        print("No hay nuevos productos. Nada que recargar.")
