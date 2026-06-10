#!/usr/bin/env bash
set -euo pipefail
export TZ="America/Hermosillo"

# =============================================================================
# deploy.sh — CD basado en pull (GitOps) para proyectoCT
#
# Pensado para correr por cron cada 5 min en el servidor de producción:
#   */5 * * * * /bin/bash $HOME/proyectoCT/deploy.sh >> $HOME/proyectoCT/logs/deploy.cron.log 2>&1
#
# Flujo:
#   1. Lock (flock) para no solapar ejecuciones.
#   2. git fetch y comparación HEAD vs origin/main. Sin cambios -> sale en silencio.
#   3. Gate de CI: solo aplica el commit si TODOS sus check-runs quedaron en success.
#   4. Aplica con merge --ff-only y clasifica los archivos que cambiaron.
#   5. Cambios en deps (pyproject/uv.lock) -> uv sync + restart completo del servicio.
#      Cambios en src/ -> recarga graceful (HUP). Solo docs/quarto/etc. -> sin reinicio.
# =============================================================================

# ---- CONFIGURACIÓN ----------------------------------------------------------
PROJECT_DIR="$HOME/proyectoCT"
BRANCH="main"
REPO="anmerino-pnd/proyectoCT"          # owner/repo en GitHub (para el gate de CI)
SERVICE="chatbot-api"                    # servicio systemd de producción

LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/deploy.log"
LOCK_FILE="$LOG_DIR/deploy.lock"

# Recarga graceful de workers (cambios de código en src/). Sin sudo: el proceso
# corre como el mismo usuario que el cron.
RELOAD_CMD=(pkill -HUP -f gunicorn)
# Reinicio completo (cambios de dependencias). Servicio systemd de sistema ->
# requiere sudoers NOPASSWD para este comando exacto.
RESTART_CMD=(sudo systemctl restart "$SERVICE")

mkdir -p "$LOG_DIR"

log() { echo "[$(date +"%Y-%m-%d %H:%M:%S %Z")] $*" >> "$LOG_FILE"; }

# ---- Lock: evita ejecuciones solapadas --------------------------------------
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "[INFO] Ya hay un deploy en curso. Saliendo."
    exit 0
fi

cd "$PROJECT_DIR"

# ---- Cargar variables de entorno (necesitamos GH_TOKEN para el gate de CI) --
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

# ---- 1. Traer cambios remotos sin aplicarlos --------------------------------
git fetch --quiet origin "$BRANCH"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    # Sin cambios: caso más común, salimos sin ruido en el log.
    exit 0
fi

log "---- START ($LOCAL -> $REMOTE) ----"

# ---- 2. Gate de CI: solo desplegar commits cuyo CI pasó ---------------------
# Los GitHub Actions se reportan como "check-runs" del commit (no en el endpoint
# legacy /status). Exigimos que todos estén completed y success/skipped/neutral.
if ! command -v gh >/dev/null 2>&1; then
    log "[ERROR] 'gh' no está instalado; no se puede validar el CI. Se pospone el deploy."
    exit 0
fi
if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
    log "[ERROR] Falta GH_TOKEN en .env; no se puede validar el CI. Se pospone el deploy."
    exit 0
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

CI_STATE=$(gh api "repos/$REPO/commits/$REMOTE/check-runs" --jq '
    if .total_count == 0 then "none"
    elif ([.check_runs[] | select(.status != "completed")] | length) > 0 then "pending"
    elif ([.check_runs[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral")] | length) > 0 then "failed"
    else "success" end
' 2>>"$LOG_FILE" || echo "error")

if [ "$CI_STATE" != "success" ]; then
    log "[INFO] CI del commit $REMOTE = '$CI_STATE' (no 'success'). Se pospone el deploy."
    log "---- END (CI gate) ----"
    exit 0
fi

# ---- 3. Qué archivos cambian entre local y remoto ---------------------------
CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
log "[INFO] Archivos cambiados:"$'\n'"$CHANGED"

# ---- 4. Aplicar los cambios -------------------------------------------------
if ! git merge --ff-only "origin/$BRANCH" >>"$LOG_FILE" 2>&1; then
    log "[ERROR] git merge --ff-only falló (¿divergencia local en el servidor?). Se aborta el deploy."
    log "---- END (merge FAIL) ----"
    exit 1
fi

# ---- 5. Clasificar los cambios ----------------------------------------------
NEEDS_RESTART=false
DEPS_CHANGED=false
if echo "$CHANGED" | grep -qE '^(pyproject\.toml|uv\.lock)$'; then
    DEPS_CHANGED=true
    NEEDS_RESTART=true
fi
if echo "$CHANGED" | grep -qE '^src/'; then
    NEEDS_RESTART=true
fi

# ---- 6. Dependencias: uv sync ANTES de reiniciar (fail-safe) ----------------
if $DEPS_CHANGED; then
    log "[INFO] Cambiaron dependencias — ejecutando 'uv sync --frozen'."
    if ! uv sync --frozen >>"$LOG_FILE" 2>&1; then
        log "[ERROR] 'uv sync' falló. NO se reinicia para no romper producción."
        log "---- END (uv sync FAIL) ----"
        exit 1
    fi
fi

# ---- 7. Reiniciar / recargar solo si aplica ---------------------------------
if $NEEDS_RESTART; then
    if $DEPS_CHANGED; then
        log "[INFO] Cambio de dependencias — reinicio completo: ${RESTART_CMD[*]}"
        if "${RESTART_CMD[@]}" >>"$LOG_FILE" 2>&1; then
            log "[INFO] Reinicio OK."
        else
            log "[ERROR] Reinicio falló (revisar sudoers NOPASSWD para 'systemctl restart $SERVICE')."
        fi
    else
        log "[INFO] Cambio de código en src/ — recarga graceful: ${RELOAD_CMD[*]}"
        if "${RELOAD_CMD[@]}" >>"$LOG_FILE" 2>&1; then
            log "[INFO] Recarga (HUP) OK."
        else
            log "[ERROR] Recarga (HUP) falló."
        fi
    fi
else
    log "[INFO] Cambios no requieren reinicio (docs/quarto/ui/tests/etc.). Pull aplicado."
fi

log "---- END ----"
