#!/usr/bin/env bash
set -euo pipefail

# CONFIGURACIÓN (ajusta si tus rutas son diferentes)
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
ETL_SCRIPT="$PROJECT_DIR/src/ct/ETL/update_vector_stores.py"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/reload_cron_wrapper.log"
TMP_OUTPUT="$LOG_DIR/reload_cron_wrapper.tmp"

# Asegura directorios
mkdir -p "$LOG_DIR"

echo "---- $(date -u +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

# 1) Ejecuta el ETL y captura salida
echo "[INFO] Ejecutando ETL: $ETL_SCRIPT" | tee -a "$LOG_FILE"
# Ejecuta con el Python del venv para evitar problemas de dependencias
# y también exportamos PYTHONPATH para que 'ct' sea importable
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" "$ETL_SCRIPT" >> "$TMP_OUTPUT" 2>&1 || {
    echo "[ERROR] Falló la ejecución del ETL. Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date -u +"%Y-%m-%d %H:%M:%S %Z") END (ETL FAIL) ----" >> "$LOG_FILE"
    exit 1
}

# Volcamos salida al log principal
cat "$TMP_OUTPUT" >> "$LOG_FILE"

# 2) Detecta si el ETL indicó que regeneró el vector store
if grep -q -i "Vector store regenerado" "$TMP_OUTPUT" || grep -q -i "Vector store creado" "$TMP_OUTPUT"; then
    echo "[INFO] Cambios detectados — recargando Gunicorn workers..." | tee -a "$LOG_FILE"

    # 3) Reiniciar el PID del proceso master de gunicorn y enviar HUP
    echo "[WARN] No se encontró 'gunicorn: master' via pgrep. Usando pkill -HUP gunicorn" | tee -a "$LOG_FILE"
    pkill -HUP -f gunicorn && echo "[INFO] pkill -HUP executed" | tee -a "$LOG_FILE" || echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
else
    echo "[INFO] No se detectaron cambios. No se recarga gunicorn." | tee -a "$LOG_FILE"
fi

# Limpieza temporal
rm -f "$TMP_OUTPUT"

echo "---- $(date -u +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"
