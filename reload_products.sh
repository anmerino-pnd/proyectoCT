#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# CONFIGURACIÓN
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
ETL_SCRIPT="$PROJECT_DIR/src/ct/ETL/update_vector_stores.py"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/reload_cron_wrapper.log"
TMP_OUTPUT="$LOG_DIR/reload_cron_wrapper.tmp"

mkdir -p "$LOG_DIR"

echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

echo "[INFO] Ejecutando ETL: $ETL_SCRIPT" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" "$ETL_SCRIPT" >> "$TMP_OUTPUT" 2>&1 || {
    echo "[ERROR] Falló la ejecución del ETL. Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END (ETL FAIL) ----" >> "$LOG_FILE"
    exit 1
}

cat "$TMP_OUTPUT" >> "$LOG_FILE"

if grep -q -i "Vector store regenerado" "$TMP_OUTPUT" || grep -q -i "Vector store creado" "$TMP_OUTPUT"; then
    echo "[INFO] Cambios detectados — recargando Gunicorn workers..." | tee -a "$LOG_FILE"
    pkill -HUP -f gunicorn && echo "[INFO] pkill -HUP executed" | tee -a "$LOG_FILE" || echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
else
    echo "[INFO] No se detectaron cambios. No se recarga gunicorn." | tee -a "$LOG_FILE"
fi

rm -f "$TMP_OUTPUT"
echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"
