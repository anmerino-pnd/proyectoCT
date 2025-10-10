import pytz
import nltk
import spacy
import numpy as np
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
import plotly.express as px
from datetime import datetime
from pymongo import MongoClient
import plotly.graph_objects as go
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords as nltk_stopwords
from sklearn.feature_extraction.text import CountVectorizer
from ct.settings.clients import mongo_uri, mongo_collection_message_backup

# Descargar recursos de NLTK si no están disponibles
nltk_needed = ['wordnet', 'punkt', 'stopwords']
for resource in nltk_needed:
    try:
        nltk.data.find(resource)
    except LookupError:
        nltk.download(resource)

# Cargar modelo de spaCy
@st.cache_resource
def load_spacy_model():
    """Load the Spanish spaCy model."""
    try:
        return spacy.load("es_core_news_lg")
    except OSError:
        return spacy.load("es_core_news_sm")
   
nlp = load_spacy_model()

# Configurar stopwords
combined_stopwords = set()
if nlp:
    spacy_stopwords = nlp.Defaults.stop_words
    combined_stopwords.update(spacy_stopwords)

nltk_stopwords = set(nltk_stopwords.words('spanish'))
combined_stopwords.update(nltk_stopwords)

custom_stopwords = {"mx", "https", "dame", "hola", "quiero", "puedes", "gustaría",
                    "interesan", "opción", "opciones", "opcion", "favor", "sirve",
                    "diste", "fijar", "debería", "viene", "palabra", "qué", "necesito","hi", "buscar",
                    "ocupar"
                    }
combined_stopwords.update(custom_stopwords)

if nlp:
    for word in combined_stopwords:
        nlp.vocab[word].is_stop = True  

st.title("Análisis de Historial de Conversaciones")

# Conectar a la base de datos de MongoDB
@st.cache_resource
def get_mongo_collection():
    """Establishes MongoDB connection and returns the collection."""
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    return db[mongo_collection_message_backup]

coleccion = get_mongo_collection()

# Obtener años disponibles
def get_available_years_from_db(_coleccion):
    """Fetches distinct years from the MongoDB collection using aggregation.
       Assumes 'timestamp' field is an ISODate object in MongoDB."""
    try:
        pipeline = [
            {"$project": {"year": {"$year": "$timestamp"}}},
            {"$group": {"_id": "$year"}},
            {"$sort": {"_id": 1}}
        ]
        years = [doc['_id'] for doc in _coleccion.aggregate(pipeline)]
        return sorted(list(set(years))) # Ensure unique and sorted
    except Exception as e:
        st.error(f"Error al obtener años disponibles de la base de datos: {e}")
        return []
    
# Obtener meses disponibles
def get_available_months_from_db(_coleccion, year):
    """Fetches distinct months for a given year from the MongoDB collection."""
    try:
        hermosillo_tz = pytz.timezone("America/Hermosillo")

        start_of_year_hermosillo = hermosillo_tz.localize(datetime(year, 1, 1, 0, 0, 0, 0))
        end_of_year_hermosillo = hermosillo_tz.localize(datetime(year + 1, 1, 1, 0, 0, 0, 0))

        pipeline = [
            {"$match": {
                "timestamp": {
                    "$gte": start_of_year_hermosillo,
                    "$lt": end_of_year_hermosillo
                }
            }},
            {"$project": {"month": {"$month": "$timestamp"}}},
            {"$group": {"_id": "$month"}},
            {"$sort": {"_id": 1}}
        ]
        months = [doc['_id'] for doc in _coleccion.aggregate(pipeline)]
        return sorted(list(set(months)))  # Ensure unique and sorted
    except Exception as e:
        st.error(f"Error al obtener meses disponibles de la base de datos: {e}")
        return []
    
st.sidebar.header("Configuración de Filtros")
time_filter_mode = st.sidebar.radio(
    "Modo de Filtro de Tiempo",
    ['Análisis por año', 'Análisis por mes'],
    )

avalaible_years = get_available_years_from_db(coleccion)

if avalaible_years:
    selected_year = st.sidebar.selectbox(
        "Selecciona un Año",
        options=avalaible_years,
        index=len(avalaible_years) - 1
    )

query_filter = {}
selected_month = None
selected_month_name = None

hermosillo_tz = pytz.timezone("America/Hermosillo")

if time_filter_mode == 'Análisis por mes':
    if selected_year:
        available_months = get_available_months_from_db(coleccion, selected_year)
        month_names_map = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        if available_months:
            available_months_names = [month_names_map[m] for m in available_months]
            selected_month = st.sidebar.selectbox(
                "Selecciona un Mes",
                options=available_months_names,
                index=len(available_months_names) - 1
            )
            selected_month = {
                v: k for k, v in month_names_map.items()
            }.get(selected_month, None)

start_date_dt = None
end_date_dt = None

if selected_year:
    if time_filter_mode == 'Análisis por año':
        start_date_dt = hermosillo_tz.localize(datetime(selected_year, 1, 1, 0, 0, 0, 0)).astimezone(pytz.utc)
        end_date_dt = hermosillo_tz.localize(datetime(selected_year + 1, 1, 1, 0, 0, 0, 0)).astimezone(pytz.utc)

    elif time_filter_mode == 'Análisis por mes' and selected_month:
        start_date_dt = hermosillo_tz.localize(datetime(selected_year, selected_month, 1, 0, 0, 0, 0)).astimezone(pytz.utc)

        if selected_month == 12:
            end_date_dt = hermosillo_tz.localize(datetime(selected_year + 1, 1, 1, 0, 0, 0, 0)).astimezone(pytz.utc)
        else:
            end_date_dt = hermosillo_tz.localize(datetime(selected_year, selected_month + 1, 1, 0, 0, 0, 0)).astimezone(pytz.utc)

query_filter = {
    "timestamp": {
        "$gte": start_date_dt,
        "$lt": end_date_dt
    }
}

# --- FILTROS DE USUARIO NUEVOS ---
# Obtener una lista de todos los 'session_id' únicos para el filtro de usuario
try:
    all_users = coleccion.distinct('session_id', query_filter)
except Exception as e:
    st.error(f"Error al obtener la lista de usuarios: {e}")
    all_users = []

selected_users = st.sidebar.multiselect(
    "Selecciona usuarios para incluir o excluir",
    options=sorted(all_users),
    default=[]
)

user_filter_mode = st.sidebar.radio(
    "Modo de filtro de usuario",
    ['Excluir', 'Incluir'],
    index=0
)

# Aplicar el filtro de usuario a la consulta
if selected_users:
    if user_filter_mode == 'Excluir':
        query_filter['session_id'] = {'$nin': selected_users}
    else:
        query_filter['session_id'] = {'$in': selected_users}
# --- FIN DE FILTROS DE USUARIO NUEVOS ---

def fetch_messages_from_db(_coleccion, query_filter):
    """Fetches messages from the MongoDB collection based on the provided query filter."""
    try:
        # Asegurarse de que el filtro de timestamp no sea nulo
        if query_filter.get("timestamp", {}).get("$gte") is None or query_filter.get("timestamp", {}).get("$lt") is None:
             st.warning("No se ha seleccionado un rango de fechas válido. Por favor, elige un año y/o mes.")
             return []

        messages = list(_coleccion.find(query_filter))
        if not messages:
            st.warning("No se encontraron mensajes para el filtro seleccionado.")
        return messages
    except Exception as e:
        st.error(f"Error al obtener mensajes de la base de datos: {e}")
        return []
    
data = fetch_messages_from_db(coleccion, query_filter)

if data:
    def preprocess_docs(_docs):
        processed_docs = []
        for doc in _docs:
            row_data = {
                'session_id': doc.get('session_id'),
                'question': doc.get('question'), # Directly get 'question'
                'answer': doc.get('answer'),     # Directly get 'answer'
                'timestamp': doc.get('timestamp'),
                'input_tokens': doc.get('input_tokens', 0),
                'output_tokens': doc.get('output_tokens', 0),
                'total_tokens': doc.get('total_tokens', 0),
                'cost': doc.get('estimated_cost', 0.0), # 'estimated_cost' for cost
                'response_time': doc.get('duration_seconds', 0.0), # 'duration_seconds' for response time
                'tokens_per_second': doc.get('tokens_per_second', 0.0),
                'model': doc.get('model_used') # 'model_used' for model
            }
            processed_docs.append(row_data)
        df = pd.DataFrame(processed_docs)

        df['full_date'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
        tz = pytz.timezone("America/Hermosillo")
        df['full_date'] = df['full_date'].dt.tz_convert(tz)

        df['date'] = df['full_date'].dt.date
        df['year'] = df['full_date'].dt.year
        df['month'] = df['full_date'].dt.month
        df['day'] = df['full_date'].dt.day
        df['hour'] = df['full_date'].dt.hour

        df['word_count_question'] = df['question'].apply(lambda x: len(word_tokenize(x)) if isinstance(x, str) else 0)
        df['word_count_answer'] = df['answer'].apply(lambda x: len(word_tokenize(x)) if isinstance(x, str) else 0)

        return df
    
    df = preprocess_docs(data)

    st.sidebar.header("Tabla de Contenidos")
    st.sidebar.markdown("[Tabla de Conversaciones](#tabla-de-conversaciones)")
    st.sidebar.markdown("[Tópicos más frecuentes](#topicos-mas-frecuentes)")
    st.sidebar.markdown("[Consultas en el tiempo](#consultas-en-el-tiempo)")
    st.sidebar.markdown("[Frecuencia por hora del día](#frecuencia-por-hora-del-dia)")
    st.sidebar.markdown("[Análisis de respuestas del asistente](#anlisis-de-respuestas-del-asistente)")

    def preprocess(corpus):
        """Preprocesses the corpus by tokenizing, lemmatizing (español) y removiendo stopwords."""
        processed_corpus = []
        for text in corpus:
            if isinstance(text, str):
                doc = nlp(text.lower())
                tokens = [
                    token.lemma_
                    for token in doc
                    if not token.is_stop and token.is_alpha
                ]
                processed_corpus.append(' '.join(tokens))
            else:
                processed_corpus.append('')
        return processed_corpus
    
    def get_top_topics(corpus, n=1):
        try:
            if not corpus:
                return []
            non_empty_corpus = [doc for doc in corpus if isinstance(doc, str) and doc.strip()]
            if not non_empty_corpus:
                return []

            vectorizer = CountVectorizer(ngram_range=(n,n),
                                         max_features=1000).fit(non_empty_corpus)
            bow = vectorizer.transform(non_empty_corpus)
            sum_words = bow.sum(axis=0)
            words_freq = [(word, sum_words[0, idx]) for word, idx in vectorizer.vocabulary_.items()]
            return sorted(words_freq, key=lambda x: x[1], reverse=True)[:12]
        except Exception as e:
            st.error(f"Error al obtener los tópicos: {e}")
            return []

    # --- INICIO DE LA SECCIÓN DE LA TABLA CON EL NUEVO FILTRO ---
    st.header("Tabla de Conversaciones")

    # Filtra solo preguntas no vacías
    df_conversations = df[df['question'].notna() & df['question'].str.strip().astype(bool)].copy()

    # Campo de texto para búsqueda
    search_term = st.text_input("Filtrar por palabra clave en la pregunta (vacío para mostrar todo)")

    # Slider para umbral de similitud
    threshold = 90

    if search_term:
        # Aplica búsqueda difusa
        df_filtered = df_conversations[
            df_conversations['question'].apply(
                lambda x: fuzz.partial_ratio(search_term.lower(), str(x).lower()) >= threshold
            )
        ].copy()
    else:
        df_filtered = df_conversations.copy()

    if not df_filtered.empty:
        df_display = df_filtered[['full_date', 'question']].copy()
        df_display.rename(columns={'full_date': 'Fecha y Hora', 'question': 'Pregunta del Usuario'}, inplace=True)
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No hay conversaciones para mostrar con los filtros seleccionados.")

    # --- FIN DE LA SECCIÓN DE LA TABLA CON EL NUEVO FILTRO ---

    st.header("Tópicos más frecuentes")
    
    df_human_questions = df[df['question'].notna() & df['question'].str.strip().astype(bool)].copy()
    
    if not df_human_questions.empty:
        corpus = preprocess(df_human_questions['question'].tolist())
        for n in [1, 2]:
            top = get_top_topics(corpus, n)
            if top:
                label = f"{n}-grama" if n == 1 else f"{n}-gramas"
                df_top = pd.DataFrame(top, columns=[label, 'Frecuencia'])
    
                fig = px.bar(df_top, x = 'Frecuencia', y = label, 
                                orientation='h', 
                                color='Frecuencia',
                                color_continuous_scale= ["#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"],
                                title=f"{'Búsquedas más frecuentes del mes' if time_filter_mode == 'Análisis por mes' else 'Búsquedas más frecuentes del año'}")
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
    
    
        st.header("Consultas en el tiempo")
        consultas_mean = df_human_questions.shape[0] / df_human_questions['session_id'].nunique()
        col1, col2 = st.columns(2)
        with col1:
            st.metric(f"Consultas totales en el {'mes' if time_filter_mode == 'Análisis por mes' else 'año'}",
                      df_human_questions.shape[0])
        with col2:
            st.metric(f"Promedio de consultas por usuario único en el {'mes' if time_filter_mode == 'Análisis por mes' else 'año'}", round(consultas_mean, 2))
    
        if time_filter_mode == 'Análisis por mes':
            df_time = (
                df_human_questions
                .groupby(df_human_questions['full_date'].dt.date)
                .size()
                .reset_index(name='count')
                .rename(columns={'full_date': 'date'})
            )
            df_time['date'] = pd.to_datetime(df_time['date'])
            date_format = "%Y-%m-%d"
            title_suffix = f"a lo largo del mes"
        else:
            df_time = (
                df_human_questions
                .groupby(df_human_questions['full_date'].dt.to_period('M'))
                .size()
                .reset_index(name='count')
                .rename(columns={'full_date': 'date'})
            )
            df_time['date'] = df_time['date'].dt.to_timestamp()
            date_format = "%Y-%m"
            title_suffix = f"a lo largo del año"
    
        if not df_time.empty:
            mean = df_time['count'].mean()
            std = df_time['count'].std()
    
            # Decide si usar media móvil
            usar_media_movil = time_filter_mode == "Análisis por mes" and len(df_time) >= 14
    
            fig = go.Figure()
    
            # Línea principal: cantidad de consultas
            fig.add_trace(go.Scatter(
                x=df_time['date'],
                y=df_time['count'],
                mode='lines+markers',
                name='Consultas',
                line=dict(color='#1f77b4')
            ))
    
            if usar_media_movil:
                rolling_mean = df_time['count'].rolling(window=7, min_periods=1).mean()
    
                fig.add_trace(go.Scatter(
                    x=df_time['date'],
                    y=rolling_mean - std,
                    mode='lines',
                    name='Media Móvil - STD',
                    line=dict(width=0),
                    showlegend=False
                ))
    
                fig.add_trace(go.Scatter(
                    x=df_time['date'],
                    y=rolling_mean + std,
                    mode='lines',
                    name='Media Móvil + STD',
                    fill='tonexty',
                    fillcolor='rgba(31, 119, 180, 0.1)',  # sombra azul
                    line=dict(width=0),
                    showlegend=False
                ))
            elif len(df_time) > 1 and std > 0:
                # Sombra alrededor del promedio global
                fig.add_trace(go.Scatter(
                    x=df_time['date'],
                    y=df_time['count'] + std,
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False
                ))
    
                fig.add_trace(go.Scatter(
                    x=df_time['date'],
                    y=df_time['count'] - std,
                    mode='lines',
                    fill='tonexty',
                    fillcolor='rgba(0,0,255,0.1)',
                    line=dict(width=0),
                    showlegend=False
                ))
    
            if mean is not None and not np.isnan(mean):
                fig.add_trace(go.Scatter(
                    x=df_time['date'],
                    y=[mean] * len(df_time),
                    mode='lines',
                    name='Media diaria',
                    line=dict(dash='dash', color='red')
                ))
    
            fig.update_layout(
                title=f"Consultas {title_suffix}",
                xaxis_title="Fecha",
                yaxis_title="Cantidad de Consultas",
                xaxis=dict(
                    tickformat=date_format,
                    tickangle=0
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
    
            st.plotly_chart(fig, use_container_width=True)
    
        st.header("Frecuencia por hora del día")
        df_hourly = (
            df_human_questions
            .groupby(df_human_questions['full_date'].dt.hour)
            .size()
            .reset_index(name='count')
            .rename(columns={'full_date': 'hour'})
        )
    
        if not df_hourly.empty:
            all_hours = list(range(24))
            df_hourly = df_hourly.set_index('hour').reindex(all_hours, fill_value=0).reset_index()
    
            mean = df_hourly['count'].mean()
            std = df_hourly['count'].std()
    
            fig = go.Figure()
    
            fig.add_trace(go.Scatter(
                x=df_hourly['hour'],
                y=df_hourly['count'],
                mode='lines+markers',
                name='Consultas',
                line=dict(color='#1f77b4')
            ))
    
            if std > 0:
                fig.add_trace(go.Scatter(
                    x=df_hourly['hour'],
                    y=df_hourly['count'] + std,
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False
                ))
    
                fig.add_trace(go.Scatter(
                    x=df_hourly['hour'],
                    y=df_hourly['count'] - std,
                    mode='lines',
                    fill='tonexty',
                    fillcolor='rgba(31, 119, 180, 0.1)',  # sombra azul
                    line=dict(width=0),
                    showlegend=False
                ))
            if mean is not None and not np.isnan(mean):
                fig.add_trace(go.Scatter
                    (x=df_hourly['hour'],
                     y=[mean] * len(df_hourly),
                     mode='lines',
                     name='Media',
                     line=dict(dash='dash', color='red')))
            fig.update_layout(
                title = f"Consultas por hora {'todo el día' if time_filter_mode == 'Análisis por mes' else 'del año'}",
                xaxis_title = "Hora del día",
                yaxis_title = "Cantidad de Consultas",
                xaxis = dict(
                    tickmode = 'linear',
                    tickvals = df_hourly['hour'],
                    dtick = 1
                ),
                legend = dict(
                    orientation = "h",
                    yanchor = "bottom",
                    y = 1.02,
                    xanchor = "right",
                    x = 1
                )
            )
            st.plotly_chart(fig, use_container_width=True)
    
        st.header("Análisis de respuestas del asistente")
    
        df_bot_answers = df[df['answer'].notna() & df['answer'].str.strip().astype(bool)].copy()
    
    
        if not df_bot_answers.empty:
            if df_bot_answers['word_count_answer'].sum() > 0:
                fig = px.histogram(
                    df_bot_answers,
                    x='word_count_answer',
                    nbins=30,
                    title="Distribución de la cantidad de palabras en las respuestas del asistente",
                    labels={'word_count_answer': 'Cantidad de Palabras'},
                    color_discrete_sequence=["#6BAED6"]
                )
                fig.update_layout(
                    xaxis_title="Cantidad de Palabras",
                    yaxis_title="Frecuencia",
                    bargap=0.2
                )
                fig.update_traces(marker= dict(opacity=0.7))
    
                avg_words = df_bot_answers['word_count_answer'].mean()
    
                fig.add_vline(
                    x=avg_words,
                    line_width=2,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Promedio: {avg_words:.2f} palabras",
                    annotation_position="top left"
                )
                st.plotly_chart(fig, use_container_width=True)
    
                min_words = df_bot_answers['word_count_answer'].min()
                max_words = df_bot_answers['word_count_answer'].max()
    
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Longitud promedio", f"{round(avg_words):,.0f}")
                with col2:
                    st.metric("Longitud mínima", f"{min_words}")
                with col3:
                    st.metric("Longitud máxima", f"{max_words}")
    
            if 'total_tokens' in df_bot_answers.columns and df_bot_answers['total_tokens'].sum() > 0:
                st.subheader("Tokens y costos")
    
                total_tokens = df_bot_answers['total_tokens'].sum()
    
                st.metric(f"Tokens totales en el {'mes' if time_filter_mode == 'Análisis por mes' else 'año'}", f"{round(total_tokens):,.0f}")
    
                if time_filter_mode == 'Análisis por mes':
                    df_tokens = (
                        df_bot_answers
                        .groupby(df_bot_answers['full_date'].dt.date)
                        .agg({
                            'total_tokens': 'sum',
                            'cost': 'sum'
                        })
                        .reset_index()
                        .rename(columns= {'full_date' : 'date'})
                    )
                    df_tokens['date'] = pd.to_datetime(df_tokens['date'])
                    tokens_date_format = "%Y-%m-%d"
                    tokens_cost_suffix = f"por día en el mes"
                    token_label = "Mensual"
                else:
                    df_bot_answers['year_month'] = df_bot_answers['full_date'].dt.strftime('%Y-%m')
    
                    df_tokens = (
                        df_bot_answers
                        .groupby('year_month')
                        .agg({
                            'total_tokens' : 'sum',
                            'cost' : 'sum'
                        }).reset_index()
                    )
                    
                    df_tokens['date'] = pd.to_datetime(df_tokens['year_month'] + '-01')
                    tokens_date_format = '%Y-%m'
                    tokens_cost_suffix = f'en el año'
                    token_label = 'Mensual'
    
                if not df_tokens.empty:
    
                    avg_tokens = df_tokens['total_tokens'].mean()
                    std_tokens = df_tokens['total_tokens'].std()
    
                    fig1 = go.Figure()
    
                    fig1.add_trace(go.Scatter(
                        x = df_tokens['date'],
                        y = df_tokens['total_tokens'],
                        mode = 'lines+markers',
                        line=dict(color='#1f77b4'),
                        name='Tokens'
                        ))
    
                    if std_tokens > 0:
                        fig1.add_trace(go.Scatter(
                            x=df_tokens['date'],
                            y=df_tokens['total_tokens'] + std_tokens,
                            mode = 'lines',
                            line= dict(width=0),
                            showlegend=False
                        ))
    
                        fig1.add_trace(go.Scatter(
                            x=df_tokens['date'],
                            y=df_tokens['total_tokens'] - std_tokens,
                            mode='lines',
                            fill='tonexty',
                            fillcolor='rgba(31, 119, 180, 0.1)',
                            line=dict(width=0),
                            showlegend=False
                        ))
    
                    if avg_tokens is not None and not np.isnan(avg_tokens):
                        fig1.add_trace(go.Scatter(
                            x=df_tokens['date'],
                            y=[avg_tokens] * len(df_tokens),
                            mode='lines',
                            name='Media',
                            line=dict(dash='dash', color='red')
                        ))
                    
                    fig1.update_layout(
                        title= f'Tokens de respuestas {tokens_cost_suffix}',
                        xaxis_title='Fecha',
                        yaxis_title='Cantidad de Tokens',
                        xaxis=dict(
                            tickformat=tokens_date_format,
                            tickangle=0
                        ),
                        legend=dict(
                            orientation='h',
                            yanchor='bottom',
                            y=1.02,
                            xanchor='right',
                            x=1
                        )
                    )
    
                    st.plotly_chart(fig1, use_container_width=True)
                    
                    min_tokens = df_tokens['total_tokens'].min()
                    max_tokens = df_tokens['total_tokens'].max()
    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(f"Promedio de tokens", f"{round(avg_tokens):,.0f}")
                    with col2:
                        st.metric(f"Mínimo de tokens", f"{min_tokens:,.0f}")
                    with col3:
                        st.metric(f"Máximo de tokens", f"{max_tokens:,.0f}")
    
            if 'cost' in df_bot_answers.columns and df_bot_answers['cost'].sum() > 0:
                
                avg_cost = df_tokens['cost'].mean()
                std_cost = df_tokens['cost'].std()
    
                fig2 = go.Figure()
    
                fig2.add_trace(go.Scatter(
                    x=df_tokens['date'],
                    y=df_tokens['cost'],
                    mode='lines+markers',
                    line=dict(color='#1f77b4'),
                    name='Costos'
                ))
    
                if std_cost > 0:
                    fig2.add_trace(go.Scatter(
                    x = df_tokens['date'],
                    y = df_tokens['cost'] + std_cost,
                    mode='lines',
                    line= dict(width=0),
                    showlegend=False
                    ))
    
                    fig2.add_trace(go.Scatter(
                        x=df_tokens['date'],
                        y=df_tokens['cost'] - std_cost,
                        mode='lines',
                        fill='tonexty',
                        fillcolor='rgba(31, 119, 180, 0.1)',
                        line= dict(width=0),
                        showlegend=False
                    ))
                    
                if avg_cost is not None and not np.isnan(avg_cost):
                    fig2.add_trace(go.Scatter(
                        x = df_tokens['date'],
                        y = [avg_cost] * len(df_tokens),
                        mode='lines',
                        name='Media',
                        line=dict(dash='dash', color='red')
                    ))
    
                fig2.update_layout(
                    title= f'Costos de respuesta {tokens_cost_suffix}',
                    xaxis_title='Fecha',
                    yaxis_title='Costo apróximado ($USD)',
                    xaxis=dict(
                        tickformat=tokens_date_format,
                        tickangle=0
                    ),
                    legend=dict(
                        orientation='h',
                        yanchor='bottom',
                        y=1.02,
                        xanchor='right',
                        x=1
                    )
                )
    
                st.plotly_chart(fig2, use_container_width=True)
    
                max_cost = df_tokens['cost'].max()
                total_cost= df_tokens['cost'].sum()
    
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"Costo total en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"${total_cost:.4f}")
                with col2:
                    st.metric(f"Costo promedio", f"${avg_cost:.4f}")
                with col3:
                    st.metric(f"Costo máximo", f"${max_cost:.4f}")
    
                cost_by_conversation = df_bot_answers.groupby('session_id')['cost'].sum().reset_index()
    
                if not cost_by_conversation.empty:
                    avg_cost_conv = cost_by_conversation['cost'].mean()
    
                    fig = go.Figure()
    
                    fig.add_trace(go.Histogram(
                        x=cost_by_conversation['cost'],
                        nbinsx=30,
                        name='Frecuencia',
                        marker=dict(color='#1f77b4', opacity= 0.7)
                    ))
    
                    hist_counts, hist_bins = np.histogram(cost_by_conversation['cost'].dropna(), bins=30)
                    max_hist_count= hist_counts.max() if len(hist_counts) > 0 else 0
    
                    if avg_cost_conv is not None and not np.isnan(avg_cost_conv):
                        fig.add_vline(x=avg_cost_conv, line_dash='dash', line_color='red',
                                      annotation_text=f"Promedio: ${avg_cost_conv:.4f}", annotation_position="top right")
                    
                    fig.update_layout(
                        title=f'Distribución de costos por usuario',
                        xaxis_title='Costo ($USD)',
                        yaxis_title='Número de usuarios',
                        bargap=0.1,
                        legend=dict(
                            orientation='h',
                            yanchor='bottom',
                            y=1.02,
                            xanchor='right',
                            x=1
                        )
                    )
    
                    st.plotly_chart(fig, use_container_width=True)
    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(f"Usuarios totales en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"{cost_by_conversation.shape[0]}")
                    with col2: 
                        st.metric("Costo promedio por usuario", f"${avg_cost_conv:.4f}")
                    with col3:
                        st.metric("Costo máximo", f"${cost_by_conversation['cost'].max():.4f}")
    
            if 'response_time' in df_bot_answers: 
                st.subheader('Tiempo de respuesta')
    
                df_bot_answers['response_time'] = pd.to_numeric(df_bot_answers['response_time'], errors='coerce').fillna(0)
                df_positive_time = df_bot_answers[df_bot_answers['response_time'] > 0].copy()
    
                if not df_positive_time.empty:
                    fig = px.histogram(
                        df_positive_time,
                        x='response_time',
                        nbins=50,
                        title=f'Distribución de tiempos de respuesta',
                        color_discrete_sequence=['royalblue']
                    )
                    fig.update_layout(xaxis_title="Tiempo (segundos)", yaxis_title="Frecuencia")
                    fig.update_traces(marker=dict(opacity=0.6))
    
                    avg_response_time = df_positive_time['response_time'].mean()
                    if avg_response_time is not None and not np.isnan(avg_response_time):
                        fig.add_vline(
                            x=avg_response_time, line_dash="dash", 
                            line_color="red", annotation_text=f"Promedio: {avg_response_time:.2f}s",
                            annotation_position="top right"
                        )
    
                        st.plotly_chart(fig)
