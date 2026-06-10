# Agente Conversacional con RAG y Herramientas para CT Internacional

Este repositorio contiene el código fuente de un avanzado agente conversacional (chatbot) diseñado para CT Internacional. El sistema utiliza una arquitectura de  **Generación Aumentada por Recuperación (RAG)** , un conjunto de herramientas especializadas y un sistema de moderación para ofrecer respuestas precisas y contextualizadas a las consultas de los usuarios sobre productos, promociones, estado de pedidos y más.

## 📜 Descripción General

El objetivo de este proyecto es proporcionar un asistente virtual inteligente que pueda:

* **Interactuar** con los usuarios de manera natural para resolver dudas comerciales y de soporte.
* **Consultar en tiempo real** bases de datos internas (MySQL y MongoDB) para obtener información sobre precios, inventario, promociones y estado de pedidos.
* **Clasificar** la intención del usuario para filtrar consultas irrelevantes o inapropiadas, optimizando costos y garantizando un entorno seguro.
* **Ofrecer una experiencia de usuario fluida** a través de una API robusta y escalable construida con FastAPI.
* **Generar reportes y análisis** sobre las interacciones para la toma de decisiones de negocio.

## 🏛️ Arquitectura del Sistema

El sistema se compone de varios módulos que trabajan en conjunto para procesar una consulta desde que el usuario la envía hasta que recibe una respuesta.

1. **API (FastAPI)** : Es el punto de entrada para todas las solicitudes. Gestiona los endpoints para el chat y el historial de conversaciones.
2. **Agente Moderador (`ModeratedToolAgent`)** : Es el orquestador principal. Primero, recibe la consulta y utiliza `QueryModerator` para clasificarla.
3. **Clasificador de Consultas (`QueryModerator`)** : Usando un modelo de lenguaje (GPT-4.1), determina si la consulta es `relevante`, `irrelevante` o `inapropiada`.
4. **Agente de Herramientas (`ToolAgent`)** : Si la consulta es `relevante`, este agente toma el control. Utiliza un LLM (GPT-4.1) junto con un conjunto de herramientas para encontrar la mejor respuesta.
5. **Herramientas (`Tools`)** : Son funciones que conectan al agente con fuentes de datos externas:

* `search_information_tool`: Realiza búsquedas semánticas en una base de datos vectorial (FAISS) de productos y promociones.
* `inventory_tool`: Consulta precios y existencias en la base de datos MySQL.
* `sales_rules_tool`: Aplica reglas de negocio y promociones específicas.
* `status_tool`: Busca el estado de un pedido en MongoDB.

1. **Bases de Datos** :

* **MongoDB** : Almacena el historial de conversaciones, sesiones de usuario y métricas detalladas para análisis.
* **MySQL** : Contiene los datos maestros de productos, precios y promociones.
* **FAISS** : Base de datos vectorial para la búsqueda de similitud.

1. **Dashboard de Reportes (Streamlit)** : Una aplicación independiente (`run_report.py`) que se conecta a MongoDB para visualizar métricas, analizar tendencias y monitorear el rendimiento del chatbot.

## ✨ Características Principales

* **Respuestas Basadas en RAG** : Combina la potencia de los LLMs con información recuperada de una base de conocimientos vectorial para dar respuestas precisas y actualizadas.
* **Uso Dinámico de Herramientas** : El agente decide de forma autónoma qué herramienta usar según la consulta del usuario.
* **Moderación de Contenido** : Filtra automáticamente las consultas para evitar el uso indebido y responder solo a temas relevantes para el negocio.
* **Gestión de Historial** : Mantiene el contexto de la conversación para interacciones más naturales y coherentes.
* **Sistema de Sanciones Progresivas** : Aplica baneos temporales a usuarios con comportamiento inapropiado recurrente.
* **API Asíncrona y Escalable** : Construida con FastAPI para un alto rendimiento y capacidad de streaming de respuestas.
* **Análisis y Reportes** : Dashboard interactivo para monitorear el uso, los costos y los temas de interés de los usuarios.
* **Pipeline ETL** : Proceso para extraer, transformar y cargar datos de productos y promociones, manteniendo la base de conocimientos siempre actualizada.

## 🛠️ Tech Stack

* **Backend** : FastAPI, Gunicorn
* **Inteligencia Artificial** : LangChain, OpenAI (`gpt-4.1`), FAISS
* **Bases de Datos** : MongoDB (con `pymongo`), MySQL (`mysql-connector-python`)
* **Análisis de Datos y Reportes** : Streamlit, Pandas, Plotly, NLTK, Spacy
* **CI/CD** : GitHub Actions + Podman/Buildah
* **Lenguaje** : Python 3.13

## 🚀 Instalación y Despliegue

Sigue estos pasos para configurar y ejecutar el backend del proyecto.

### Prerrequisitos

* Python 3.13.1
* `uv` (gestor de paquetes recomendado)
* Acceso a una instancia de MongoDB y MySQL.
* Un servidor con Ollama (opcional, si se usan modelos locales).

### 1. Clonar el Repositorio

```
git clone [https://github.com/anmerino-pnd/proyectoCT](https://github.com/anmerino-pnd/proyectoCT)
cd proyectoCT

```

### 2. Configurar el Entorno Virtual e Instalar Dependencias

Se recomienda usar `uv` por su velocidad.

```
pip install uv # En caso de no estar instalado
uv venv
source .venv/bin/activate  # Para Linux/macOS
# o `.venv\Scripts\activate` para Windows
uv sync --frozen          # Instala desde uv.lock (producción)
# o `uv sync --frozen --group test` si vas a correr la suite de pruebas

```

### 3. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto y añade las siguientes credenciales.

```
# Conexión a la base de datos SQL
ip=
port=
user=
pwd=
db=

# Clave de la API de OpenAI para correr sus modelos
OPENAI_API_KEY=

# Configuración para el servicio de fichas técnicas
url= '' 
Token-api=''
Token-ct=''
Content-Type=''
Cookie=''

sucursales_url= ""

dominio=""
boundary=''

# Conexión a MongoDB
MONGO_URI = "mongodb://" # En la URI debe estar incrustrado el nombre de la DB
MONGO_DB = ""
MONGO_COLLECTION_SESSIONS = "tbl_sessions"
MONGO_COLLECTION_MESSAGE_BACKUP = "tbl_message_backup"
MONGO_COLLECTION_PRODUCTS = "tbl_productos"
MONGO_COLLECTION_SALES = "tbl_ofertas"   
MONGO_COLLECTION_SPECIFICATIONS = "mongo_collection_specifications"
MONGO_COLLECTION_PEDIDOS="tbl_pedidos"
```

### 4. Ejecutar la Aplicación

Para desarrollo, puedes usar Uvicorn:

```
uvicorn ct.main:app --host 0.0.0.0 --port 8000 --reload

```

En producción la API corre como un **servicio de systemd** (`chatbot-api`), de modo que arranca
automáticamente en el boot y se reinicia sola ante caídas (`Restart=always`). El servicio ejecuta
Gunicorn con workers de Uvicorn:

```ini
# /etc/systemd/system/chatbot-api.service (resumen)
[Service]
User=angel.merino
WorkingDirectory=/home/angel.merino/proyectoCT
ExecStart=/home/angel.merino/proyectoCT/.venv/bin/python -m gunicorn ct.main:app \
  --workers 4 --bind 0.0.0.0:8000 \
  --certfile=static/ssl/cert.pem --keyfile=static/ssl/key.pem \
  -k uvicorn.workers.UvicornWorker --timeout 120 \
  --access-logfile - --error-logfile -
Restart=always
```

Operación del servicio:

```bash
sudo systemctl status chatbot-api      # estado / logs recientes
sudo systemctl restart chatbot-api     # reinicio completo
journalctl -u chatbot-api -f           # seguir logs en vivo
```

## ⚙️ Uso de la API

La API expone los siguientes endpoints principales:

* `POST /chat`: Envía una nueva consulta del usuario. La respuesta se transmite en tiempo real (streaming).
* `GET /history/{user_id}`: Obtiene el historial de conversación de un usuario.
* `DELETE /history/{user_id}`: Elimina el historial de un usuario.

**Ejemplo de solicitud a `/chat`:**

```
{
  "user_query": "¿Qué laptops para gaming me recomiendas?",
  "user_id": "cliente-12345",
  "listaPrecio": "1"
}

```

## 🧪 Tests y CI/CD

El proyecto incluye un *pipeline* de integración continua en `.github/workflows/ci.yml` que ejecuta automáticamente la suite de pruebas y construye la imagen del contenedor en cada `push` y `pull_request` contra `main`.

### Ejecutar la suite de pruebas localmente

```bash
# Instalar dependencias de test
uv sync --frozen --group test

# Correr toda la suite con cobertura
uv run pytest tests/

# Correr sin cobertura (más rápido)
uv run pytest tests/ --no-cov

# Filtrar por marker
uv run pytest tests/ -m unit
```

La configuración de `pytest` (paths, markers, cobertura) vive en `pyproject.toml`. Los reportes HTML de cobertura se generan en `htmlcov/`.

### Pipeline en GitHub Actions

El workflow tiene dos jobs encadenados:

1. **`test`**: instala `uv` con Python 3.13, sincroniza dependencias con `uv sync --frozen --group test` y ejecuta `pytest` con reporte de cobertura en XML.
2. **`build-podman`**: depende del job anterior. Usa `redhat-actions/buildah-build@v2` para construir la imagen `proyecto-ct:latest` a partir del `Dockerfile`. El paso de publicación a `ghcr.io` está incluido pero comentado por defecto — se puede activar habilitando permisos de escritura del workflow desde la configuración del repositorio.

Para construir la imagen localmente:

```bash
podman build -t proyecto-ct:latest .
podman run --rm -it -p 8000:8000 --env-file .env proyecto-ct:latest
```

Más detalles del *pipeline*, estructura de tests, lazy-init de clientes externos y solución de problemas comunes en la sección **6. Integración Continua (CI/CD)** del [sitio de documentación](./docs).

## 🔁 Despliegue Continuo (CD)

El despliegue sigue un modelo **pull (GitOps)**: el propio servidor sondea el repositorio y se
actualiza solo, sin que GitHub necesite acceso SSH ni a un registro de contenedores. Lo maneja el
script [`deploy.sh`](./deploy.sh), ejecutado por `cron` cada 5 minutos:

```cron
*/5 * * * * /bin/bash $HOME/proyectoCT/deploy.sh >> $HOME/proyectoCT/logs/deploy.cron.log 2>&1
```

En cada ejecución el script:

1. Hace `git fetch` y compara `HEAD` con `origin/main`. Si no hay cambios, termina en silencio.
2. **Valida el CI**: solo aplica el commit si todos sus *check-runs* en GitHub Actions quedaron en
   `success` (consulta vía `gh api`, requiere `GH_TOKEN` en `.env`). Si el CI sigue en curso o
   falló, pospone el despliegue hasta la siguiente corrida.
3. Aplica los cambios con `git merge --ff-only` y **clasifica** lo que cambió:
   - `pyproject.toml` / `uv.lock` → corre `uv sync --frozen` y reinicia el servicio completo
     (`sudo systemctl restart chatbot-api`).
   - Archivos en `src/` → recarga *graceful* de los workers (`pkill -HUP -f gunicorn`).
   - Solo documentación/Quarto/UI/tests → aplica el `pull` **sin reiniciar** el servicio.

Como `datos/vectorstores/`, `static/ssl/` y `.env` están en `.gitignore`, el `git pull` nunca
toca los índices FAISS, los certificados ni los secretos.

**Requisitos en el servidor:**

- `GH_TOKEN` en `.env` (PAT *fine-grained*, solo lectura de *Actions* y *Contents*).
- Regla sudoers para que el reinicio por cambio de dependencias no pida contraseña:
  ```
  angel.merino ALL=(root) NOPASSWD: /usr/bin/systemctl restart chatbot-api
  ```

Los logs del despliegue quedan en `logs/deploy.log`.

## 📊 Dashboard de Reportes

El dashboard de Streamlit corre en producción como su propio servicio de systemd
(`streamlit-reporte`, puerto `3000`), igual que la API. Para operarlo:

```bash
sudo systemctl restart streamlit-reporte
sudo systemctl status streamlit-reporte
journalctl -u streamlit-reporte -f
```

Para una ejecución manual durante el desarrollo:

```bash
streamlit run run_report.py --server.fileWatcherType none --server.port 3000
```

El detalle del archivo `.service` está en la documentación de despliegue (`quarto/6_documentacion.qmd`).

## 🔄 Actualización de la Base de Conocimientos (ETL)

Para mantener la información de productos y promociones actualizada, es necesario ejecutar el pipeline ETL periódicamente.

**Activar el entorno virtual:**

```
source .venv/bin/activate

```

**Ejecutar el pipeline:**

```
# Para actualizar solo productos (recomendado cada 2-3 meses)
python -c "from ct.ETL.pipeline import update_products; update_products()"

# Para actualizar solo promociones (recomendado mensualmente)
python -c "from ct.ETL.pipeline import update_sales; update_sales()"

# Para actualizar todo
python -c "from ct.ETL.pipeline import update_all; update_all()"

```

Se recomienda configurar un *cron job* para automatizar estas tareas.
