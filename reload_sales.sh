#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# CONFIGURACIÓN
PROJECT_DIR="$HOME/proyectoCT"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/monthly_sales_etl.log"
TMP_OUTPUT="$LOG_DIR/monthly_sales_etl.tmp"

mkdir -p "$LOG_DIR"

# --- Lógica de fecha ---
day_of_month=$(date +%d)
day_of_week=$(date +%u)  # 1=lunes ... 7=domingo

# Si no es día 1 ni 2, salir
if [[ "$day_of_month" != "01" && "$day_of_month" != "02" ]]; then
    exit 0
fi

# Si es día 1 y domingo (7), salir — se ejecutará mañana (día 2)
if [[ "$day_of_month" == "01" && "$day_of_week" == "7" ]]; then
    echo "[$(date)] Domingo día 1 — se pospone al día 2." >> "$LOG_FILE"
    exit 0
fi

# Si es día 2 y ayer fue domingo, ejecutar
if [[ "$day_of_month" == "02" ]]; then
    yesterday=$(date -d "yesterday" +%u)
    if [[ "$yesterday" != "7" ]]; then
        # No fue domingo ayer → ya se ejecutó o no toca
        exit 0
    fi
fi

echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") START ----" >> "$LOG_FILE"

# --- Ejecución de los scripts Python ---
echo "[INFO] Ejecutando carga mensual de ofertas" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales; load_sales()" >> "$TMP_OUTPUT" 2>&1

echo "[INFO] Ejecutando carga de productos y ofertas" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PY" -c "from ct.ETL.pipeline import load_sales_products; load_sales_products()" >> "$TMP_OUTPUT" 2>&1

cat "$TMP_OUTPUT" >> "$LOG_FILE"

# --- Lógica de recarga de Gunicorn (opcional) ---
if grep -qiE "✅ Vector store de ventas (ofertas) actualizado correctamente." "$TMP_OUTPUT"; then
    echo "[INFO] Cambios detectados — recargando Gunicorn workers..." | tee -a "$LOG_FILE"
    pkill -HUP -f gunicorn && echo "[INFO] pkill -HUP ejecutado" | tee -a "$LOG_FILE" || echo "[ERROR] pkill falló" | tee -a "$LOG_FILE"
else
    echo "[INFO] No se detectaron cambios. No se recarga Gunicorn." | tee -a "$LOG_FILE"
fi

rm -f "$TMP_OUTPUT"
echo "---- $(date +"%Y-%m-%d %H:%M:%S %Z") END ----" >> "$LOG_FILE"
