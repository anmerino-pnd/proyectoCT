#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# CONFIGURACIÓN
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/update_sales.log"
TMP_OUTPUT="$LOG_DIR/update_sales.tmp"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a  # exporta automáticamente todas las variables leídas
    source "$PROJECT_DIR/.env"
    set +a
else
    echo "[WARN] No se encontró el archivo .env en $PROJECT_DIR/.env" >&2
fi

mkdir -p "$LOG_DIR"

echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

# --- Ejecutar update_sales ---
echo "[INFO] Actualizando ofertas del mes actual" | tee -a "$LOG_FILE"
if PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import update_sales; update_sales()" >> "$TMP_OUTPUT" 2>&1; then
    echo "[INFO] update_sales() ejecutado correctamente" | tee -a "$LOG_FILE"
else
    echo "[ERROR] Falló update_sales(). Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END (UPDATE_SALES FAIL) ----" >> "$LOG_FILE"
    exit 1
fi

# --- Ejecutar load_sales_products ---
echo "[INFO] Cargando productos relacionados a las ofertas" | tee -a "$LOG_FILE"
if PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales_products; load_sales_products()" >> "$TMP_OUTPUT" 2>&1; then
    echo "[INFO] load_sales_products() ejecutado correctamente" | tee -a "$LOG_FILE"
else 
    echo "[ERROR] Falló load_sales_products(). Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END (LOAD_SALES_PRODUCTS FAIL) ----" >> "$LOG_FILE"
    exit 1
fi

cat "$TMP_OUTPUT" >> "$LOG_FILE"

if grep -qiE "Vector stores combinados exitosamente" "$TMP_OUTPUT" ; then
    echo "[INFO] Cambios detectados en ofertas — recargando Gunicorn workers..." | tee -a "$LOG_FILE"
    if pkill -HUP -f gunicorn; then
        echo "[INFO] pkill -HUP ejecutado" | tee -a "$LOG_FILE" 
    else 
        echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
    fi
else
    echo "[INFO] No se detectaron cambios en ofertas. No se recarga Gunicorn." | tee -a "$LOG_FILE"
fi

rm -f "$TMP_OUTPUT"
echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"