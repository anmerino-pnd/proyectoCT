# QWEN.md - Contexto para Asistentes

## Project Overview

**Proyecto CT**: Un agente conversacional basado en RAG (Retrieval Augmented Generation) para **CT Internacional**, una empresa de tecnología y cómputo. El sistema funciona como un chatbot empresarial que proporciona respuestas precisas y contextualizadas sobre productos, promociones, pedidos y soporte técnico.

### Arquitectura Principal

El sistema sigue una arquitectura de **agente orquestado** con tres fases principales:

1. **API Gateway (FastAPI)**: Punto de entrada que gestiona endpoints `/chat`, `/history/{user_id}`, y `/delete-history/{user_id}`
2. **Moderación (`QueryModerator`)**: Clasifica cada consulta en `relevante`, `irrelevante` o `inapropiado` usando GPT-4.1
3. **Agente de Herramientas (`ToolAgent`)**: Si la consulta es relevante, utiliza un LLM + herramientas para generar respuestas con información recuperada de bases de datos

### Tech Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI, Gunicorn, Uvicorn |
| LLM | OpenAI GPT-4.1, GPT-5, GPT-5-mini, GPT-5-nano (configurable) |
| Embeddings | OpenAI Embeddings, FAISS |
| Bases de Datos | MongoDB (historial, sesiones), MySQL (productos, precios), FAISS (vector store) |
| Análisis | Streamlit, Pandas, Plotly, NLTK, SpaCy |
| Frontend | SDK JavaScript (widget web), React components (react-chatbot-kit) |

### Estructura de Directorios

```
proyectoCT/
├── src/ct/                    # Código fuente principal (package-dir en pyproject.toml)
│   ├── main.py               # FastAPI app (entry point)
│   ├── chat.py               # Endpoints y lógica de chat
│   ├── settings/             # Configuración y esquema
│   │   ├── clients.py        # Credenciales (DB, OpenAI, etc.)
│   │   ├── config.py         # Rutas y paths
│   │   ├── prompt.py         # Prompts del LLM
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── tokens.py         # Precios tokens por modelo
│   │   └── timing_tools.py   # Tracking de costos
│   ├── tools/                # Herramientas del agente
│   │   ├── inventory.py      # Consulta MySQL de existencias
│   │   ├── algolia.py        # Búsqueda de productos
│   │   ├── sales_rules_tool.py # Reglas de promoción
│   │   ├── status.py         # Estado de pedidos
│   │   └── ...               # Otras herramientas
│   ├── langchain/            # Implementación de agentes
│   │   ├── tool_agent.py     # Agente principal de respuesta
│   │   ├── moderated_tool_agent.py  # Orquestador (moderación + tool agent)
│   │   └── moderator_agent.py # QueryModerator (clasificación)
│   ├── ETL/                  # Pipeline de datos
│   │   ├── extraction.py     # Extracción de productos/ofertas
│   │   ├── load.py           # Carga en FAISS
│   │   ├── transform.py      # Limpieza y transformación
│   │   └── pipeline.py       # Orquestación
│   ├── reportes/             # Dashboard Streamlit
│   │   └── run_report.py     # Análisis de conversaciones
│   └── evaluation/           # Evaluación RAG
│       └── evaluator.py      # Métricas y evaluación
├── datos/                    # Datos brutos y vector stores
│   ├── vectorstores/         # FAISS stores (productos, promociones)
│   ├── base_de_conocimientos
│   └── ...
├── ui/                       # Frontend widget
│   ├── sdk.js               # Widget JavaScript
│   ├── app.js               # Lógica del chat
│   └── styles.css           # Estilos
├── static/                   # Assets estáticos
│   └── ssl/                  # Certificados SSL
├── data_pipeline/            # Notebooks (git-ignored)
└── tests/                    # Tests (git-ignored)
```

## Building and Running

### Prerrequisitos

- **Python**: 3.12.9 o superior
- **uv**: Gestor de paquetes recomendado (más rápido que pip)
- **Bases de Datos**: MongoDB, MySQL con credenciales configuradas
- **OpenAI API Key**: Para generar embeddings y consultas

### Instalación

```bash
# 1. Clonar/entrar al proyecto
cd proyectoCT

# 2. Configurar entorno virtual
uv venv
.venv\Scripts\activate  # Windows
# o
source .venv/bin/activate  # Linux/macOS

# 3. Instalar dependencias
uv pip install -e .

# O usar uv directamente
uv pip install -e .
```

### Ejecución

#### Desarrollo (Uvicorn)

```bash
uvicorn ct.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Producción (Gunicorn)

```bash
nohup gunicorn ct.main:app \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --certfile=static/ssl/cert.pem \
  --keyfile=static/ssl/key.pem \
  -k uvicorn.workers.UvicornWorker \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - &
```

#### Dashboard de Reportes (Streamlit)

```bash
nohup streamlit run run_report.py \
  --server.fileWatcherType none \
  --server.port 3000 &
```

### API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/chat` | POST | Envía consulta, recibe streaming de respuesta |
| `/history/{user_id}` | GET | Obtiene historial de conversaciones |
| `/history/{user_id}` | DELETE | Elimina historial de un usuario |
| `/logs/{msg_id}` | GET | Log de costos y tiempos |

### Ejemplo de Solicitud a `/chat`

```json
{
  "user_query": "¿Qué laptops para gaming me recomiendas?",
  "user_id": "cliente-12345",
  "listaPrecio": "1"
}
```

## Development Conventions

### Código Python

- **Package Structure**: Código fuente está en `src/ct/` (configurado en `pyproject.toml`)
- **Type Hints**: Uso obligatorio de Pydantic schemas para validación
- **Async**: Endpoints de chat son asíncronos (`async def`)
- **Logging**: Uso de `logging.getLogger(__name__)` para logs
- **Error Handling**: Try-except blocks con mensajes descriptivos

### Tests

- **Framework**: pytest
- **Markers**: `unit`, `integration`, `slow`
- **Coverage**: `pytest-cov` con reportes en `htmlcov/`
- **Config**: `[tool.pytest.ini_options]` en `pyproject.toml`

### ETL Pipeline

1. **Extracción**: `extraction.py` - Consulta MySQL para productos/ofertas
2. **Transformación**: `transform.py` - Limpieza, separación contexto/información
3. **Carga**: `load.py` - Creación de FAISS vector stores
4. **Orquestación**: `pipeline.py` - Funciones `update_products()`, `update_sales()`, `update_all()`

### Costos y Token Tracking

- `tokens.py`: Precios por modelo (`MODEL_COST_PER_1K_TOKENS`)
- `timing_tools.py`: Handler de callbacks para tracking tokens y costos
- Cada respuesta guarda: tokens, costos, duración, modelo usado

### Moderación y Baneos

- `moderator_agent.py`: QueryModerator clasifica consultas
- Escalamiento progresivo: 1 intento (sin baneo) → 7 días máximo
- MongoDB: Campos `inappropriate_tries`, `banned_until`

### Frontend (JavaScript)

- `sdk.js`: Widget CTAIWidget que inyecta HTML en la página
- `app.js`: Lógica del chat (envío, historial, Markdown parsing)
- Config: `window.CTAI_CONFIG = { userId, userKey, apiBase }`

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/ct/main.py` | FastAPI app, endpoints principales |
| `src/ct/chat.py` | Endpoints de chat, histórico |
| `src/ct/settings/clients.py` | Credenciales DB, OpenAI, etc. |
| `src/ct/settings/prompt.py` | Prompts del LLM para herramientas |
| `src/ct/settings/tokens.py` | Precios tokens por modelo |
| `src/ct/langchain/tool_agent.py` | Agente principal de respuesta |
| `src/ct/langchain/moderated_tool_agent.py` | Orquestador (moderación + tool agent) |
| `src/ct/tools/inventory.py` | Consulta MySQL de existencias |
| `src/ct/tools/algolia.py` | Búsqueda de productos |
| `src/ct/ETL/pipeline.py` | Orquestación ETL |
| `src/ct/ETL/extraction.py` | Extracción de productos/ofertas |
| `src/ct/ETL/load.py` | Carga en FAISS |
| `src/ct/reportes/run_report.py` | Dashboard Streamlit |
| `ui/sdk.js` | Widget JavaScript para páginas web |
| `ui/app.js` | Lógica del chat en frontend |

## Common Tasks

### Actualizar Vector Store

```python
# Actualizar solo productos
python -c "from ct.ETL.pipeline import update_products; update_products()"

# Actualizar solo promociones
python -c "from ct.ETL.pipeline import update_sales; update_sales()"

# Actualizar todo
python -c "from ct.ETL.pipeline import update_all; update_all()"
```

### Ejecutar Evaluación RAG

```python
# Evaluar últimos 10 mensajes
from ct.evaluation.evaluator import RAGASEvaluator
evaluator = RAGASEvaluator()
results = await evaluator.evaluate_batch()
```

### Ver Logs de Costos

```bash
# Ver log de costos específico
curl http://localhost:8000/logs/{msg_id}
```
