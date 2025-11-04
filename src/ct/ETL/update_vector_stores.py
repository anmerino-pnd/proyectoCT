from ct.ETL.pipeline import update_products
from ct.settings.clients import reload_vectors_post
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


if __name__ == "__main__":
    changed = update_products()
    if changed == True:
        print("Vector store regenerado. Notificando servidor...")
        requests.post(reload_vectors_post, timeout=10, verify=False)
    else:
        print("No hay nuevos productos. Nada que recargar.")
