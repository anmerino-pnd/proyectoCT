import os
import json
import pytz
import nltk
import spacy
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from pymongo import MongoClient
import plotly.graph_objects as go
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords as nltk_stopwords
from sklearn.feature_extraction.text import CountVectorizer
from datetime import datetime, date
import calendar # For getting month names and number of days in month

# Assuming ct.clients correctly imports mongo_uri, mongo_db, mongo_collection_message_backup
from ct.clients import mongo_uri, mongo_db, mongo_collection_message_backup


# Download NLTK resources if not present
nltk_needed = ['wordnet', 'punkt', 'stopwords']
for resource in nltk_needed:
    try:
        nltk.data.find(f"corpora/{resource}")
    except LookupError:
        nltk.download(resource)
    except Exception as e:
        st.error(f"Error al descargar recurso de NLTK '{resource}': {e}")


# Load Spacy model
@st.cache_resource
def load_spacy_model():
    """
    Loads the Spanish Spacy model, trying 'es_core_news_lg' first, then 'es_core_news_md'.
    Displays an error message if neither is found.
    """
    try:
        return spacy.load("es_core_news_lg")
    except:
         try:
            return spacy.load("es_core_news_md")
         except:
            st.error("Modelos de Spacy 'es_core_news_lg' o 'es_core_news_md' no encontrados. Por favor, instálalos: `python -m spacy download es_core_news_lg`")
            return None

nlp = load_spacy_model()

# Combine stopwords from NLTK, Spacy and custom list
combined_stopwords = set()
if nlp:
    stop_words_spacy = nlp.Defaults.stop_words
    combined_stopwords.update(stop_words_spacy)

stop_words_nltk = set(nltk_stopwords.words('spanish'))
combined_stopwords.update(stop_words_nltk)

custom_stopwords = {"mx", "https", "dame", "hola", "quiero", "puedes", "gustaría",
                    "interesan", "opción", "opciones", "opcion", "favor", "sirve",
                    "diste", "fijar", "debería", "viene", "palabra"}
combined_stopwords.update(custom_stopwords)

# Mark stopwords in Spacy's vocabulary
if nlp:
    for word in combined_stopwords:
        nlp.vocab[word].is_stop = True

st.title("Análisis de Historial de Conversaciones")

# --- MongoDB Connection and Data Fetching Logic (Optimized) ---

@st.cache_resource
def get_mongo_collection():
    """Establishes MongoDB connection and returns the collection."""
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    return db[mongo_collection_message_backup]

coleccion = get_mongo_collection()

@st.cache_data
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

@st.cache_data
def get_available_months_for_year_from_db(_coleccion, year):
    """Fetches distinct months for a given year from MongoDB using aggregation.
       Assumes 'timestamp' field is an ISODate object in MongoDB."""
    try:
        # Define Hermosillo timezone for accurate date range calculation
        hermosillo_tz = pytz.timezone("America/Hermosillo")
        
        # Calculate start and end of the year in Hermosillo time, then convert to UTC
        start_of_year_hermosillo = hermosillo_tz.localize(datetime(year, 1, 1, 0, 0, 0, 0))
        end_of_year_hermosillo = hermosillo_tz.localize(datetime(year + 1, 1, 1, 0, 0, 0, 0))
        
        start_date_utc = start_of_year_hermosillo.astimezone(pytz.utc)
        end_date_utc = end_of_year_hermosillo.astimezone(pytz.utc)

        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date_utc, "$lt": end_date_utc}}},
            {"$project": {"month": {"$month": "$timestamp"}}},
            {"$group": {"_id": "$month"}},
            {"$sort": {"_id": 1}}
        ]
        months = [doc['_id'] for doc in _coleccion.aggregate(pipeline)]
        return sorted(list(set(months))) # Ensure unique and sorted
    except Exception as e:
        st.error(f"Error al obtener meses disponibles para el año {year} de la base de datos: {e}")
        return []

# --- Global Time Filter in the sidebar ---
st.sidebar.header("Filtro de Tiempo Global")
time_filter_mode = st.sidebar.radio(
    "Selecciona la granularidad de los datos:",
    ["Análisis por año", "Análisis por mes"]
)

available_years = get_available_years_from_db(coleccion)

# Set default selected year to the latest year if available, otherwise fallback to current year
if available_years:
    default_year_index = available_years.index(max(available_years)) if max(available_years) in available_years else 0
    selected_year = st.sidebar.selectbox("Selecciona el Año", available_years, index=default_year_index)
else:
    st.warning("No se encontraron años disponibles en la base de datos. Usando el año actual como predeterminado.")
    selected_year = datetime.now().year # Fallback to current year
    available_years = [selected_year] # To ensure year is in the list for initial display

# Initialize query filter and month variables
query_filter = {}
selected_month = None
selected_month_name = None

# Define Hermosillo timezone
hermosillo_tz = pytz.timezone("America/Hermosillo")

if time_filter_mode == "Análisis por mes":
    if selected_year:
        available_months_nums = get_available_months_for_year_from_db(coleccion, selected_year)
        month_names_map = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        
        if available_months_nums:
            available_months_names = [month_names_map[m] for m in available_months_nums]
            
            # Set default selected month to the latest month if available, otherwise current month
            latest_month_num = max(available_months_nums) if available_months_nums else datetime.now().month
            try:
                default_month_index = available_months_nums.index(latest_month_num)
            except ValueError:
                default_month_index = 0
            
            selected_month_name = st.sidebar.selectbox(
                "Selecciona el Mes",
                available_months_names,
                index=default_month_index
            )
            selected_month = {v: k for k, v in month_names_map.items()}.get(selected_month_name)
        else:
            st.warning(f"No hay meses disponibles para el año {selected_year} en la base de datos. Usando el mes actual como predeterminado.")
            selected_month = datetime.now().month # Fallback to current month if no months found for selected year
            selected_month_name = month_names_map.get(selected_month)
    else: # This block handles the case where selected_year is None, which shouldn't happen with the current logic
        selected_month = datetime.now().month
        selected_month_name = calendar.month_name[selected_month]


# Construct MongoDB query filter based on selections
start_date_dt = None
end_date_dt = None

if selected_year:
    if time_filter_mode == "Análisis por año":
        # Start of the year in Hermosillo time
        start_date_naive = datetime(selected_year, 1, 1, 0, 0, 0, 0)
        start_date_hermosillo = hermosillo_tz.localize(start_date_naive)
        start_date_utc = start_date_hermosillo.astimezone(pytz.utc)

        # Start of the next year in Hermosillo time
        end_date_naive = datetime(selected_year + 1, 1, 1, 0, 0, 0, 0)
        end_date_hermosillo = hermosillo_tz.localize(end_date_naive)
        end_date_utc = end_date_hermosillo.astimezone(pytz.utc)
        
        start_date_dt = start_date_utc
        end_date_dt = end_date_utc

    elif time_filter_mode == "Análisis por mes" and selected_month:
        # Start of the month in Hermosillo time
        start_date_naive = datetime(selected_year, selected_month, 1, 0, 0, 0, 0)
        start_date_hermosillo = hermosillo_tz.localize(start_date_naive)
        start_date_utc = start_date_hermosillo.astimezone(pytz.utc)

        # Start of the next month in Hermosillo time
        if selected_month == 12:
            end_date_naive = datetime(selected_year + 1, 1, 1, 0, 0, 0, 0)
        else:
            end_date_naive = datetime(selected_year, selected_month + 1, 1, 0, 0, 0, 0)
        
        end_date_hermosillo = hermosillo_tz.localize(end_date_naive)
        end_date_utc = end_date_hermosillo.astimezone(pytz.utc)

        start_date_dt = start_date_utc
        end_date_dt = end_date_utc
    else:
        st.error("No se pudo construir un filtro de fecha válido. Seleccione un año y/o mes.")
        st.stop() # Stop execution if date filter is invalid

    query_filter = {
        'timestamp': {
            '$gte': start_date_dt,
            '$lt': end_date_dt
        }
    }
else:
    st.error("No se ha seleccionado un año válido. Deteniendo la ejecución.")
    st.stop()


# Fetch data from MongoDB using the constructed query filter
@st.cache_data(ttl=3600) # Cache data for 1 hour
def fetch_data_from_db(_coleccion, _query_filter, _start_date_utc, _end_date_utc):
    """Fetches data from MongoDB based on the query filter."""
    try:
        return list(_coleccion.find(_query_filter))
    except Exception as e:
        st.error(f"Error al cargar datos de MongoDB: {e}")
        return []

data = fetch_data_from_db(coleccion, query_filter, start_date_dt, end_date_dt)


if data:
    @st.cache_data
    def process_many_docs(_docs):
        """
        Processes a list of raw documents (from MongoDB) into a pandas DataFrame.
        Extracts relevant fields and performs datetime conversions and word counting.
        """
        rows = []
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
            rows.append(row_data)

        df = pd.DataFrame(rows)
        # Convert timestamp to datetime objects and set to UTC
        # The timestamp from MongoDB will be ISODate, which pandas handles well
        df['full_date'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')

        # Convert to America/Hermosillo timezone, fallback to UTC if error
        try:
            tz = pytz.timezone("America/Hermosillo")
            df['full_date'] = df['full_date'].dt.tz_convert(tz)
        except Exception as e:
            st.warning(f"No se pudo convertir a la zona horaria 'America/Hermosillo', usando UTC. Error: {e}")
            df['full_date'] = df['full_date'].dt.tz_convert('UTC')

        # Extract date, year, month, day, hour for easier filtering and grouping
        df['date'] = df['full_date'].dt.date
        df['year'] = df['full_date'].dt.year
        df['month'] = df['full_date'].dt.month
        df['day'] = df['full_date'].dt.day
        df['hour'] = df['full_date'].dt.hour
        
        # Calculate word count for questions, filling NaN with 0
        df['word_count_question'] = df['question'].astype(str).str.split().str.len().fillna(0).astype(int)
        # Calculate word count for answers, filling NaN with 0
        df['word_count_answer'] = df['answer'].astype(str).str.split().str.len().fillna(0).astype(int)

        return df

    
    df = process_many_docs(data)
    # Display the raw processed DataFrame for debugging or inspection (can be removed in production)
    # st.write(df)

    if df.empty:
        st.warning("No se encontraron datos válidos para analizar después del procesamiento con los filtros seleccionados.")
        st.stop()

    # The df_filtered is no longer needed as the main df is already filtered by the MongoDB query
    # based on the selected year/month.
    # We still need to filter based on the 'selected_year' and 'selected_month'
    # if the 'process_many_docs' is still returning all data.
    # But since I'm changing the find() call, df will *be* df_filtered.

    # Make sure df_filtered is correctly assigned (it's now just `df` after fetching)
    # The subsequent code uses df_filtered, so I'll just rename df to df_filtered for consistency
    df_filtered = df


    st.sidebar.header("Tabla de Contenidos")
    st.sidebar.markdown("[Tópicos más frecuentes](#topicos-mas-frecuentes)")
    st.sidebar.markdown("[Consultas en el tiempo](#consultas-en-el-tiempo)")
    st.sidebar.markdown("[Frecuencia por hora del día](#frecuencia-por-hora-del-dia)")
    st.sidebar.markdown("[Análisis de respuestas del asistente](#analisis-de-respuestas-del-asistente)")

    def preprocess(corpus):
        """
        Preprocesses a corpus of text: tokenizes, lowercases, lemmatizes,
        and removes stopwords and non-alphabetic tokens.
        """
        lemmatizer = WordNetLemmatizer()
        result = []
        for text in corpus.fillna(''): # Fill NaN with empty string to avoid errors
            if isinstance(text, str):
                tokens = word_tokenize(text.lower())
                filtered = [lemmatizer.lemmatize(w) for w in tokens if w not in combined_stopwords and w.isalpha()]
                result.append(' '.join(filtered))
            else:
                result.append('')
        return result


    # Function to find most frequent n-grams
    def top_ngrams(corpus, n=1):
        """
        Calculates and returns the top N most frequent n-grams from a corpus.
        Handles empty or all-empty corpus gracefully.
        """
        try:
            if not corpus or all(text == '' for text in corpus):
                return []
            non_empty_corpus = [text for text in corpus if text != '' and pd.notna(text)] # Added pd.notna(text)
            if not non_empty_corpus:
                 return []

            vec = CountVectorizer(ngram_range=(n, n)).fit(non_empty_corpus)
            bow = vec.transform(non_empty_corpus)
            sum_words = bow.sum(axis=0)
            freqs = [(word, sum_words[0, idx]) for word, idx in vec.vocabulary_.items()]
            return sorted(freqs, key=lambda x: x[1], reverse=True)[:12]
        except Exception as e:
            st.error(f"Error al calcular n-gramas: {e}")
            return []


    st.header("Tópicos más frecuentes")
    # Filter for human questions (where 'question' column is not null and not empty)
    df_human_filtered = df_filtered[df_filtered['question'].notna() & (df_filtered['question'] != '')].copy()

    # Show most frequent topics
    if not df_human_filtered.empty and df_human_filtered['question'].notna().any():
        corpus = preprocess(df_human_filtered['question']) # Use 'question' column for human content
        if corpus and any(c != '' for c in corpus):
            for n in [1, 2]:
                top = top_ngrams(corpus, n)
                if top:
                    label = f"{n}-grama" if n == 1 else f"{n}-gramas"
                    df_top = pd.DataFrame(top, columns=[label, "Frecuencia"])

                    fig = px.bar(df_top, x="Frecuencia", y=label,
                                orientation="h",
                                color="Frecuencia",
                                color_continuous_scale=["#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"],
                                title=f"{'Búsquedas más frecuentes del mes' if time_filter_mode == 'Análisis por mes' else 'Búsquedas más frecuentes del año'}")
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig)
                else:
                     st.info(f"No se encontraron {n}-gramas frecuentes para el período seleccionado.")
        else:
             st.info("No hay contenido de preguntas humanas válido en el período seleccionado para analizar tópicos.")
    else:
        st.info("No hay preguntas humanas válidas en el período seleccionado para analizar tópicos.")


    st.header("Consultas en el tiempo")

    # Show query and conversation metrics
    # Use 'session_id' for unique conversations
    promedio_consultas = df_human_filtered.shape[0] / df_human_filtered['session_id'].nunique() if df_human_filtered['session_id'].nunique() > 0 else 0
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"Total de consultas en el {'mes' if time_filter_mode == 'Análisis por mes' else 'Año'}", df_human_filtered.shape[0])
    with col2:
        st.metric(f"Promedio de consultas por usuario en el {'mes' if time_filter_mode == 'Análisis por mes' else 'Año'}", round(promedio_consultas, 2)) # Round to 2 decimal places

    # Prepare data for time series plot based on selected granularity
    if time_filter_mode == "Análisis por mes":
        df_time = (
            df_human_filtered
            .groupby(df_human_filtered['full_date'].dt.date)
            .size()
            .reset_index(name='count')
            .rename(columns={'full_date': 'date'})
        )
        df_time['date'] = pd.to_datetime(df_time['date'])
        date_format = "%Y-%m-%d"
        title_suffix = f"a lo largo del mes"
    else: # time_filter_mode == "Análisis por año" (Ver por Meses en un Año)
        df_time = (
            df_human_filtered
            .groupby(df_human_filtered['full_date'].dt.to_period('M'))
            .size()
            .reset_index(name='count')
            .rename(columns={'full_date': 'date'})
        )
        df_time['date'] = df_time['date'].dt.to_timestamp()
        date_format = "%Y-%m"
        title_suffix = f"a lo largo del año"

    # Show time series plot of queries
    if not df_time.empty:
        mean = df_time['count'].mean()
        std = df_time['count'].std()

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df_time['date'], y=df_time['count'],
            mode='lines+markers',
            line=dict(color='blue'),
            name='Consultas'
        ))

        if len(df_time) > 1 and std > 0:
            fig.add_trace(go.Scatter(
                x=df_time['date'], y=df_time['count'] + std,
                mode='lines',
                line=dict(width=0),
                showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=df_time['date'], y=df_time['count'] - std,
                mode='lines',
                fill='tonexty',
                line=dict(width=0),
                fillcolor='rgba(0,0,255,0.1)',
                showlegend=False
            ))

        if mean is not None and not np.isnan(mean):
             fig.add_trace(go.Scatter(
                 x=df_time['date'],
                 y=[mean] * len(df_time),
                 mode='lines',
                 line=dict(color='red', dash='dash'),
                 name=f'Promedio: {mean:,.2f}'
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

        st.plotly_chart(fig)
    else:
         st.info("No hay datos de consultas humanas para mostrar en el tiempo para el período seleccionado.")


    st.header("Frecuencia por hora del día")
    # Prepare data for hourly frequency plot (using human questions)
    df_hour = df_filtered[df_filtered['question'].notna() & (df_filtered['question'] != '')].groupby('hour').size().reset_index(name='count')

    # Show hourly frequency plot
    if not df_hour.empty:
        all_hours = pd.DataFrame({'hour': range(24)})
        df_hour = pd.merge(all_hours, df_hour, on='hour', how='left').fillna(0)

        mean = df_hour['count'].mean()
        std = df_hour['count'].std()


        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df_hour['hour'], y=df_hour['count'],
            mode='lines+markers',
            line=dict(color='blue'),
            name='Consultas'
        ))

        if std > 0:
            fig.add_trace(go.Scatter(
                x=df_hour['hour'], y=df_hour['count'] + std,
                mode='lines',
                line=dict(width=0),
                showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=df_hour['hour'], y=df_hour['count'] - std,
                mode='lines',
                fill='tonexty',
                fillcolor='rgba(0,0,255,0.1)',
                line=dict(width=0),
                showlegend=False
            ))

        if mean is not None and not np.isnan(mean):
            fig.add_trace(go.Scatter(
                x=df_hour['hour'],
                y=[mean] * len(df_hour),
                mode='lines',
                line=dict(color='red', dash='dash'),
                name=f'Promedio: {mean:,.2f}'
            ))

        fig.update_layout(title=f"Consultas por hora {'en el mes' if time_filter_mode == 'Análisis por mes' else 'en el año'}",
                        xaxis_title="Hora del Día",
                        yaxis_title="Cantidad de Consultas",
                        xaxis=dict(tickangle=0, tickmode='linear', tick0=0, dtick=1),
                         legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                        )

        st.plotly_chart(fig)
    else:
         st.info("No hay datos de consultas humanas por hora para el período seleccionado.")


    st.header("Análisis de Respuestas del Asistente")
    # Filter for assistant answers (where 'answer' column is not null and not empty)
    df_bot_filtered = df_filtered[df_filtered['answer'].notna() & (df_filtered['answer'] != '')].copy()


    if not df_bot_filtered.empty:
        st.subheader("Longitud de respuestas")

        # Use 'word_count_answer' for assistant response length
        df_bot_filtered['word_count_answer'] = pd.to_numeric(df_bot_filtered['word_count_answer'], errors='coerce').fillna(0)

        # Show histogram of response length
        if df_bot_filtered['word_count_answer'].sum() > 0:
            fig = px.histogram(df_bot_filtered, x='word_count_answer', nbins=30,
                                title=f"Distribución de longitud de respuestas {'en el mes' if time_filter_mode == 'Análisis por mes' else 'en el año'}",
                                color_discrete_sequence=['royalblue'])
            fig.update_layout(xaxis_title="Número de Palabras", yaxis_title="Frecuencia")
            fig.update_traces(marker=dict(opacity=0.7))

            avg_length = df_bot_filtered['word_count_answer'].mean()
            if avg_length is not None and not np.isnan(avg_length):
                 fig.add_vline(x=avg_length, line_dash="dash", line_color="red", annotation_text=f"Promedio: {avg_length:.2f}", annotation_position="top right")

            st.plotly_chart(fig)

            # Show response length metrics
            avg_length = df_bot_filtered['word_count_answer'].mean()
            min_length = df_bot_filtered['word_count_answer'].min()
            max_length = df_bot_filtered['word_count_answer'].max()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Longitud promedio", f"{round(avg_length)}")
            with col2:
                st.metric("Longitud mínima", f"{min_length}")
            with col3:
                st.metric("Longitud máxima", f"{max_length}")
        else:
             st.info("No hay datos de longitud de respuestas para mostrar en el período seleccionado.")


        # Analysis of Tokens and Costs
        if 'total_tokens' in df_bot_filtered.columns and df_bot_filtered['total_tokens'].notna().any() and df_bot_filtered['total_tokens'].sum() > 0:
            st.subheader("Tokens y costos")

            total_tokens = df_bot_filtered['total_tokens'].sum()
            st.metric(f"Tokens totales en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"{round(total_tokens):,.0f}")

            # Determine granularity based on the global time filter
            if time_filter_mode == "Análisis por mes":
                df_token_cost_time = (
                    df_bot_filtered
                    .groupby(df_bot_filtered['full_date'].dt.date)
                    .agg({
                        'total_tokens': 'sum',
                        'cost': 'sum' if 'cost' in df_bot_filtered.columns else 0
                    })
                    .reset_index()
                    .rename(columns={'full_date': 'date'})
                )
                df_token_cost_time['date'] = pd.to_datetime(df_token_cost_time['date'])
                token_cost_date_format = "%Y-%m-%d"
                token_cost_title_suffix = f"por día en el mes de {selected_month_name}"
                token_cost_granularity_label = "Diario"

            else: # time_filter_mode == "Análisis por año"
                df_bot_filtered['year_month'] = df_bot_filtered['full_date'].dt.strftime('%Y-%m')

                df_token_cost_time = (
                    df_bot_filtered
                    .groupby('year_month')
                        .agg({
                        'total_tokens': 'sum',
                        'cost': 'sum' if 'cost' in df_bot_filtered.columns else 0
                    })
                    .reset_index()
                )
                df_token_cost_time['date'] = pd.to_datetime(df_token_cost_time['year_month'] + '-01')
                token_cost_date_format = "%Y-%m"
                token_cost_title_suffix = f"en el año"
                token_cost_granularity_label = "Mensual"


            # Show Tokens over time plot
            if not df_token_cost_time.empty and df_token_cost_time['total_tokens'].sum() > 0:
                mean_tokens = df_token_cost_time['total_tokens'].mean()
                std_tokens = df_token_cost_time['total_tokens'].std()

                fig1 = go.Figure()

                fig1.add_trace(go.Scatter(
                    x=df_token_cost_time['date'],
                    y=df_token_cost_time['total_tokens'],
                    mode='lines+markers',
                    line=dict(color='blue'),
                    name='Tokens'
                ))

                if std_tokens > 0 and len(df_token_cost_time) > 1:
                    fig1.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=df_token_cost_time['total_tokens'] + std_tokens,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False
                    ))

                    fig1.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=df_token_cost_time['total_tokens'] - std_tokens,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(0,0,255,0.1)',
                        showlegend=False
                    ))

                if mean_tokens is not None and not np.isnan(mean_tokens):
                    fig1.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=[mean_tokens] * len(df_token_cost_time),
                        mode='lines',
                        line=dict(color='red', dash='dash'),
                        name=f'Promedio: {mean_tokens:,.0f}'
                    ))

                fig1.update_layout(
                    title=f"Tokens de respuestas {token_cost_title_suffix}",
                    xaxis_title="Fecha",
                    yaxis_title="Cantidad de Tokens",
                    xaxis=dict(
                        tickformat=token_cost_date_format,
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

                st.plotly_chart(fig1, use_container_width=True)

                # Show Token metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"Promedio de tokens", f"{round(mean_tokens):,.0f}")
                with col2:
                    st.metric(f"Mínimo de tokens", f"{df_token_cost_time['total_tokens'].min():,.0f}")
                with col3:
                    st.metric(f"Máximo de tokens", f"{df_token_cost_time['total_tokens'].max():,.0f}")
            else:
                 st.info(f"No hay suficientes datos de tokens para mostrar en el período seleccionado con granularidad '{token_cost_granularity_label}'.")


            # Show Cost over time plot
            if 'cost' in df_bot_filtered.columns and df_bot_filtered['cost'].notna().any() and df_bot_filtered['cost'].sum() > 0:
                mean_cost = df_token_cost_time['cost'].mean()
                std_cost = df_token_cost_time['cost'].std()

                fig2 = go.Figure()

                fig2.add_trace(go.Scatter(
                    x=df_token_cost_time['date'],
                    y=df_token_cost_time['cost'],
                    mode='lines+markers',
                    line=dict(color='green'),
                    name='Costo'
                ))

                if std_cost > 0 and len(df_token_cost_time) > 1:
                    fig2.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=df_token_cost_time['cost'] + std_cost,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False
                    ))

                    fig2.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=df_token_cost_time['cost'] - std_cost,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(0,128,0,0.1)',
                        showlegend=False
                    ))

                if mean_cost is not None and not np.isnan(mean_cost):
                    fig2.add_trace(go.Scatter(
                        x=df_token_cost_time['date'],
                        y=[mean_cost] * len(df_token_cost_time),
                        mode='lines',
                        line=dict(color='red', dash='dash'),
                        name=f'Promedio: ${mean_cost:.4f}'
                    ))

                fig2.update_layout(
                    title=f"Costo de respuestas {token_cost_title_suffix}",
                    xaxis_title="Fecha",
                    yaxis_title="Costo ($USD)",
                    xaxis=dict(
                        tickformat=token_cost_date_format,
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

                st.plotly_chart(fig2, use_container_width=True)

                # Show Cost metrics
                total_cost = df_bot_filtered['cost'].sum()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"Costo total en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"${total_cost:.4f}")
                with col2:
                    st.metric(f"Costo promedio", f"${mean_cost:.4f}")
                with col3:
                    st.metric(f"Costo máximo", f"${df_token_cost_time['cost'].max():.4f}")

                # Show cost distribution by conversation
                # Use 'session_id' for grouping by user/session
                cost_by_conversation = df_bot_filtered.groupby('session_id')['cost'].sum().reset_index()

                if not cost_by_conversation.empty and cost_by_conversation['cost'].sum() > 0:
                     mean_cost_conv = cost_by_conversation['cost'].mean()

                     fig = go.Figure()

                     fig.add_trace(go.Histogram(
                         x=cost_by_conversation['cost'],
                         nbinsx=30,
                         name='Frecuencia',
                         marker=dict(color='royalblue', opacity=0.7)
                     ))

                     try:
                         hist_counts, hist_bins = np.histogram(cost_by_conversation['cost'].dropna(), bins=30)
                         max_hist_count = hist_counts.max() if len(hist_counts) > 0 else 0
                     except ValueError:
                         max_hist_count = 0


                     if mean_cost_conv is not None and not np.isnan(mean_cost_conv):
                         fig.add_vline(x=mean_cost_conv, line_dash="dash", line_color="red", annotation_text=f"Promedio: ${mean_cost_conv:.4f}", annotation_position="top right")


                     fig.update_layout(
                         title=f"Distribución de costos por usuario",
                         xaxis_title="Costo ($USD)",
                         yaxis_title="Número de Usuarios",
                         bargap=0.1,
                         legend=dict(
                             orientation="h",
                             yanchor="bottom",
                             y=1.02,
                             xanchor="right",
                             x=1
                         )
                     )

                     st.plotly_chart(fig, use_container_width=True)

                     # Show cost by conversation metrics
                     col1, col2, col3 = st.columns(3)
                     with col1:
                         st.metric(f"Usuarios totales en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"{cost_by_conversation.shape[0]}")
                     with col2:
                         st.metric("Costo promedio por usuario", f"${mean_cost_conv:.4f}")
                     with col3:
                         st.metric("Costo máximo", f"${cost_by_conversation['cost'].max():.4f}")
                else:
                     st.info("No hay datos de costo por conversación para mostrar en el período seleccionado.")


            else:
                st.info("Datos de costo no disponibles o cero para el período seleccionado.")


        # Response Time Analysis
        if 'response_time' in df_bot_filtered.columns and df_bot_filtered['response_time'].notna().any() and df_bot_filtered['response_time'].sum() > 0:
            st.subheader("Tiempo de respuesta")

            df_bot_filtered['response_time'] = pd.to_numeric(df_bot_filtered['response_time'], errors='coerce').fillna(0)
            df_response_time_positive = df_bot_filtered[df_bot_filtered['response_time'] > 0].copy()

            # Show response time histogram
            if not df_response_time_positive.empty:

                fig = px.histogram(df_response_time_positive, x='response_time', nbins=50,
                                    title=f"Distribución de tiempos de respuesta",
                                    color_discrete_sequence=['royalblue'])
                fig.update_layout(xaxis_title="Tiempo (segundos)", yaxis_title="Frecuencia")
                fig.update_traces(marker=dict(opacity=0.7))

                avg_response_time = df_response_time_positive['response_time'].mean()
                if avg_response_time is not None and not np.isnan(avg_response_time):
                    fig.add_vline(x=avg_response_time, line_dash="dash", line_color="red", annotation_text=f"Promedio: {avg_response_time:.2f}s", annotation_position="top right")

                st.plotly_chart(fig)


            else:
                st.info("No hay tiempos de respuesta positivos para mostrar en el período seleccionado.")

        else:
            st.info("Datos de tiempo de respuesta no disponibles, cero o inválidos para el período seleccionado.")

    else:
        st.info("No hay datos de respuestas del asistente para el período seleccionado.")
