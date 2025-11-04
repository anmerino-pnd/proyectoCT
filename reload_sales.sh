#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# CONFIGURACIÓN
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/reload_sales.log"
TMP_OUTPUT="$LOG_DIR/reload_sales.tmp"
LOCK_FILE="$LOG_DIR/reload_sales.lock"  

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a  # exporta automáticamente todas las variables leídas
    source "$PROJECT_DIR/.env"
    set +a
else
    echo "[WARN] No se encontró el archivo .env en $PROJECT_DIR/.env" >&2
fi

mkdir -p "$LOG_DIR"

# --- Lógica de fecha ---
day_of_month=$(date +%d)
day_of_week=$(date +%u)

# Si no es día 1 ni 2, salir
if [[ "$day_of_month" != "01" && "$day_of_month" != "02" ]]; then
    echo "[$(date)] Se ejecutó fuera de la fecha correspondiente."
    exit 0
fi

# Si es día 1 y domingo, posponer al día 2
if [[ "$day_of_month" == "01" && "$day_of_week" == "7" ]]; then
    echo "[$(date)] Domingo día 1 — se pospone al día 2." >> "$LOG_FILE"
    exit 0
fi

# Si es día 2 y ayer NO fue domingo, revisar si ya se ejecutó
if [[ "$day_of_month" == "02" ]]; then
    yesterday=$(date -d "yesterday" +%u)
    if [[ "$yesterday" != "7" ]]; then
        # ✅ MEJORA: Verificar si ya se ejecutó exitosamente este mes
        current_month=$(date +%Y-%m)
        if [[ -f "$LOCK_FILE" ]] && grep -q "^$current_month$" "$LOCK_FILE"; then
            echo "[INFO] Ya se ejecutó exitosamente este mes ($current_month). Saliendo." >> "$LOG_FILE"
            exit 0
        else
            echo "[WARN] No se encontró ejecución exitosa del día 1. Ejecutando recuperación." >> "$LOG_FILE"
        fi
    fi
fi

echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

echo "[INFO] Ejecutando carga mensual de ventas" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales; load_sales()" >> "$TMP_OUTPUT" 2>&1

echo "[INFO] Ejecutando carga de productos de ventas" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales_products; load_sales_products()" >> "$TMP_OUTPUT" 2>&1

# ✅ MEJORA: Marcar ejecución exitosa
if [ $? -eq 0 ]; then
    date +%Y-%m > "$LOCK_FILE"
    echo "[INFO] Ejecución exitosa registrada" | tee -a "$LOG_FILE"
fi

cat "$TMP_OUTPUT" >> "$LOG_FILE"

# --- Lógica de recarga de Gunicorn ---
if grep -qiE "Vector stores combinados exitosamente" "$TMP_OUTPUT"; then
    echo "[INFO] Cambios detectados — recargando Gunicorn workers..." | tee -a "$LOG_FILE"
    if pkill -HUP -f gunicorn; then
        echo "[INFO] pkill -HUP ejecutado" | tee -a "$LOG_FILE" 
    else
        echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
else
    echo "[INFO] No se detectaron cambios. No se recarga Gunicorn." | tee -a "$LOG_FILE"
fi

rm -f "$TMP_OUTPUT"
echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"