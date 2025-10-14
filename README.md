
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
* **Lenguaje** : Python 3.12

## 🚀 Instalación y Despliegue

Sigue estos pasos para configurar y ejecutar el backend del proyecto.

### Prerrequisitos

* Python 3.12.9
* `uv` (gestor de paquetes recomendado)
* Acceso a una instancia de MongoDB y MySQL.
* Un servidor con Ollama (opcional, si se usan modelos locales).

### 1. Clonar el Repositorio

```
git clone [https://github.com/tu-usuario/tu-repositorio.git](https://github.com/tu-usuario/tu-repositorio.git)
cd tu-repositorio

```

### 2. Configurar el Entorno Virtual e Instalar Dependencias

Se recomienda usar `uv` por su velocidad.

```
# Instalar uv si no lo tienes
pip install uv

# Crear y activar el entorno virtual
uv venv
source .venv/bin/activate  # En Linux/macOS
# .venv\Scripts\activate   # En Windows

# Instalar las dependencias
uv pip install -r requirements.txt

```

### 3. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto y añade las siguientes credenciales.

```
# Conexión a la base de datos SQL
DB_IP=
DB_PORT=
DB_USER=
DB_PWD=
DB_NAME=

# Clave de la API de OpenAI
OPENAI_API_KEY=sk-...

# Conexión a MongoDB
MONGO_URI="mongodb+srv://..."
MONGO_COLLECTION_SESSIONS="sessions"
MONGO_COLLECTION_MESSAGE_BACKUP="message_backup"
# ... otras colecciones ...

```

### 4. Ejecutar la Aplicación

Para desarrollo, puedes usar Uvicorn:

```
uvicorn ct.main:app --host 0.0.0.0 --port 8000 --reload

```

Para producción, se recomienda Gunicorn con workers de Uvicorn:

```
gunicorn ct.main:app --workers 4 --bind 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker

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

## 📊 Dashboard de Reportes

Para analizar las conversaciones y visualizar métricas de rendimiento, ejecuta la aplicación de Streamlit:

```
streamlit run run_report.py

```

Esto iniciará un servidor web local con el dashboard interactivo.

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
