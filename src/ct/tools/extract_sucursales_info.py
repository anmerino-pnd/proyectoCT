import time
import json
import sqlite3
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
    name = opt.text.strip()
    if value and value.isdigit():
        sucursales.append({"nombre": name, "idSucursal": value})

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


resultados = {}

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
                ubicacion = driver.find_element(By.CSS_SELECTOR, ".col-md-7").text
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
            
            # Extraer directorio
            directorio = []
            try:
                tabla = driver.find_element(By.ID, "table_directorio")
                filas = tabla.find_elements(By.TAG_NAME, "tr")[1:]
                
                for fila in filas:
                    cols = fila.find_elements(By.TAG_NAME, "td")
                    if len(cols) == 3:
                        directorio.append({
                            "puesto": cols[0].text.strip(),
                            "nombre": cols[1].text.strip(),
                            "correo": cols[2].text.strip()
                        })
            except Exception as e:
                print(f"  ⚠️ Error al extraer tabla: {e}")
            
            resultados[suc['nombre']] = {
                "ubicacion": ubicacion,
                "direccion": direccion,
                "telefono": telefono,
                "horario": horario,
                "directorio": directorio
            }

            
            print(f"✅ {suc['nombre']}: {len(directorio)} contactos")
            break  # Si funcionó, salir del loop de intentos
            
        except Exception as e:
            print(f"⚠️ Intento {intento+1}/{max_intentos} en {suc['nombre']}")
            print(f"   Error completo: {str(e)[:200]}")  # Mostrar parte del error
            
            if intento == max_intentos - 1:
                print(f"❌ Falló definitivamente {suc['nombre']}")
            else:
                # Reintentar recargando la página
                driver.get("https://ctonline.mx/empresa/sucursales")
                time.sleep(3)
    
    time.sleep(1.5)

driver.quit()


columns = ['sucursal', 'ubicacion', 'direccion' ,'telefono', 'horario', 'directorio']

df = pd.DataFrame(columns=columns)

for sucursal, info in resultados.items():
    # Convertir la fila a DataFrame temporal
    fila = pd.DataFrame([{
        "sucursal": sucursal,
        "ubicacion": info.get("ubicacion", ""),
        "direccion": info.get("direccion", ""),
        "telefono": info.get("telefono", ""),
        "horario": info.get("horario", ""),
        "directorio": info.get("directorio", [])
    }])
    
    # Concatenar al df principal
    df = pd.concat([df, fila], ignore_index=True)

df.to_csv(f"{DATA_DIR}/sucursales.csv", index=False)

df['directorio'] = df['directorio'].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)

conn = sqlite3.connect(f"{DATA_DIR}/ctonline2.db")
df.to_sql('sucursales', conn, if_exists='replace', index=False)
conn.close()

print("✅ Guardado en SQLite")
