import time
import json
import sqlite3
import unicodedata
import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
from ct.settings.config import DATA_DIR
from ct.settings.clients import sucursales_url

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

scraper = cloudscraper.create_scraper()
resp = scraper.get(sucursales_url)
soup = BeautifulSoup(resp.text, "html.parser")

sucursales = []
for opt in soup.select("#select_sucursal option"):
    value = opt.get("value")
    name = unicodedata.normalize('NFKD', opt.text.strip().lower())
    name_no_accent = "".join([c for c in name if not unicodedata.combining(c)])
    if value and value.isdigit():
        sucursales.append({"nombre": name_no_accent, "idSucursal": value})

print(f"Encontradas {len(sucursales)} sucursales")

chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Modo headless moderno
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)
driver.get(sucursales_url)

# Esperar a que cargue completamente la página inicial
time.sleep(3)


chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Modo headless moderno
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)
driver.get("https://ctonline.mx/empresa/sucursales")

# Esperar a que cargue completamente la página inicial
time.sleep(3)
filas = []
for suc in sucursales:
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            # Buscar el select FRESCO con más tiempo de espera
            select_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "select_sucursal"))
            )
            
            # Scroll al elemento (ayuda en headless)
            driver.execute_script("arguments[0].scrollIntoView(true);", select_element)
            time.sleep(0.5)
            
            select = Select(select_element)
            select.select_by_value(suc['idSucursal'])
            
            # Esperar más tiempo en headless
            time.sleep(4)  # Aumentado de 3 a 4 segundos
            
            # Buscar elementos FRESCOS
            try:
                direccion = driver.find_element(By.CSS_SELECTOR, ".address").text
            except Exception as e:
                print(f"  ⚠️ No se encontró dirección: {e}")
                direccion = ""
                
            try:
                ubicacion = driver.find_element(By.CSS_SELECTOR, ".col-md-7").text.lower()
            except:
                ubicacion = ""

            try:
                telefono = driver.find_element(By.CSS_SELECTOR, ".phone").text
            except:
                telefono = ""
                
            try:
                horario = driver.find_element(By.CSS_SELECTOR, ".time").text
            except:
                horario = ""
            
            # Extraer directorio como lista
            directorio_contactos = []
            try:
                tabla = driver.find_element(By.ID, "table_directorio")
                filas_tabla = tabla.find_elements(By.TAG_NAME, "tr")[1:]
                
                for fila in filas_tabla:
                    cols = fila.find_elements(By.TAG_NAME, "td")
                    if len(cols) == 3:
                        directorio_contactos.append({
                            "puesto": cols[0].text.strip(),
                            "nombre": cols[1].text.strip(),
                            "correo": cols[2].text.strip()
                        })
            except Exception as e:
                print(f"  ⚠️ Error al extraer tabla: {e}")
            
            # 👇 Crear una fila por cada contacto
            if directorio_contactos:
                for contacto in directorio_contactos:
                    filas.append({
                        "sucursal": suc['nombre'],
                        "ubicacion": ubicacion,
                        "direccion": direccion,
                        "telefono": telefono,
                        "horario": horario,
                        "puesto": contacto["puesto"],
                        "nombre": contacto["nombre"],
                        "correo": contacto["correo"]
                    })
            else:
                # Si no hay contactos, guardar solo info de sucursal
                filas.append({
                    "sucursal": suc['nombre'],
                    "ubicacion": ubicacion,
                    "direccion": direccion,
                    "telefono": telefono,
                    "horario": horario,
                    "puesto": "",
                    "nombre": "",
                    "correo": ""
                })
            
            print(f"✅ {suc['nombre']}: {len(directorio_contactos)} contactos")
            break
            
        except Exception as e:
            print(f"⚠️ Intento {intento+1}/{max_intentos} en {suc['nombre']}")
            print(f"   Error: {str(e)[:200]}")
            
            if intento == max_intentos - 1:
                print(f"❌ Falló definitivamente {suc['nombre']}")
            else:
                driver.get(sucursales_url)
                time.sleep(3)
    
    time.sleep(1.5)

driver.quit()


df = pd.DataFrame(filas)
df.to_csv(f"{DATA_DIR}/sucursales.csv", index=False)
print(f"✅ {len(df)} registros guardados en CSV")
