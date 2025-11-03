#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# CONFIGURACIÓN
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/update_sales.log"
TMP_OUTPUT="$LOG_DIR/update_sales.tmp"

mkdir -p "$LOG_DIR"

echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

# --- Ejecutar update_sales ---
echo "[INFO] Actualizando ofertas del mes actual" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import update_sales; update_sales()" >> "$TMP_OUTPUT" 2>&1 || {
    echo "[ERROR] Falló update_sales(). Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END (UPDATE_SALES FAIL) ----" >> "$LOG_FILE"
    exit 1
}

# --- Ejecutar load_sales_products ---
echo "[INFO] Cargando productos relacionados a las ofertas" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales_products; load_sales_products()" >> "$TMP_OUTPUT" 2>&1 || {
    echo "[ERROR] Falló load_sales_products(). Ver salida en $TMP_OUTPUT" | tee -a "$LOG_FILE"
    cat "$TMP_OUTPUT" >> "$LOG_FILE"
    echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END (LOAD_SALES_PRODUCTS FAIL) ----" >> "$LOG_FILE"
    exit 1
}

cat "$TMP_OUTPUT" >> "$LOG_FILE"

# --- Lógica de recarga de Gunicorn ---
if grep -qiE "✅ Vector store de ventas (ofertas) actualizado correctamente." "$TMP_OUTPUT" || \
   grep -qiE "Vector store regenerado|Vector store creado" "$TMP_OUTPUT"; then
    echo "[INFO] Cambios detectados en ofertas — recargando Gunicorn workers..." | tee -a "$LOG_FILE"
    pkill -HUP -f gunicorn && echo "[INFO] pkill -HUP ejecutado" | tee -a "$LOG_FILE" || echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
else
    echo "[INFO] No se detectaron cambios en ofertas. No se recarga Gunicorn." | tee -a "$LOG_FILE"
fi

rm -f "$TMP_OUTPUT"
echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"