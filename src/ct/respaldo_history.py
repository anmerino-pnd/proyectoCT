import shutil
import os
import time
from datetime import datetime

# Configuración
ORIGEN = os.path.expanduser("~/datos/history.json")
DESTINO_DIR = os.path.expanduser("~/datos/backups_history")
INTERVALO_MINUTOS = 5  # intervalo de respaldo en minutos

# Asegúrate de que exista el directorio destino
os.makedirs(DESTINO_DIR, exist_ok=True)

print(f"[INICIO] Monitoreando {ORIGEN}, respaldos en {DESTINO_DIR} cada {INTERVALO_MINUTOS} min.")

while True:
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if os.path.exists(ORIGEN):
        destino_archivo = os.path.join(DESTINO_DIR, "history_backup.json")
        shutil.copy2(ORIGEN, destino_archivo)
        print(f"[{timestamp}] Backup creado en {destino_archivo}")
    else:
        print(f"[{timestamp}] history.json no existe.")

    time.sleep(INTERVALO_MINUTOS * 60)
