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
from ct.clients import mongo_uri, mongo_db, mongo_collection_backup


# Descargar recursos de NLTK si no están presentes
nltk_needed = ['wordnet', 'punkt', 'stopwords']
for resource in nltk_needed:
    try:
        nltk.data.find(f"corpora/{resource}")
    except LookupError:
        nltk.download(resource)
    except Exception as e:
        st.error(f"Error al descargar recurso de NLTK '{resource}': {e}")


# Cargar modelo de Spacy
@st.cache_resource
def load_spacy_model():
    try:
        return spacy.load("es_core_news_lg")
    except:
         try:
            return spacy.load("es_core_news_md")
         except:
            st.error("Modelos de Spacy 'es_core_news_lg' o 'es_core_news_md' no encontrados. Por favor, instálalos: `python -m spacy download es_core_news_lg`")
            return None

nlp = load_spacy_model()

# Combinar stopwords de NLTK, Spacy y personalizadas
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

# Marcar stopwords en el vocabulario de Spacy
if nlp:
    for word in combined_stopwords:
        nlp.vocab[word].is_stop = True

st.title("Análisis de Historial de Conversaciones")

cliente = MongoClient(mongo_uri)
db = cliente[mongo_db]
coleccion = db[mongo_collection_backup]

data = coleccion.find_one()


if data:
    data.pop('_id', None)  
    @st.cache_data
    def process_json(_raw_data):
        rows = []
        for conversation_id, msgs in _raw_data.items():
            for i in msgs:
                if isinstance(i, dict) and all(k in i for k in ['type', 'content', 'timestamp']) and isinstance(i['content'], str):
                    row_data = {
                        'conversation_id': conversation_id,
                        'type': i['type'],
                        'content': i['content'],
                        'timestamp': i['timestamp']
                    }

                    if i.get('metadata'):
                        metadata = i.get('metadata')
                        if metadata.get('tokens'):
                            row_data['input_tokens'] = metadata.get('tokens').get('input', 0)
                            row_data['output_tokens'] = metadata.get('tokens').get('output', 0)
                            row_data['total_tokens'] = metadata.get('tokens').get('total', 0)
                            row_data['cost'] = float(metadata.get('tokens').get('estimated_cost', 0) or 0)

                        if metadata.get('duration'):
                            row_data['response_time'] = float(metadata.get('duration').get('seconds', 0) or 0)
                            row_data['tokens_per_second'] = float(metadata.get('duration').get('tokens_per_second', 0) or 0)

                        if metadata.get('cost_model'):
                            row_data['model'] = metadata.get('cost_model')

                    rows.append(row_data)

        df = pd.DataFrame(rows)
        df['full_date'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
        df.dropna(subset=['full_date'], inplace=True)

        try:
            tz = pytz.timezone("America/Hermosillo")
            df['full_date'] = df['full_date'].dt.tz_convert(tz)
        except pytz.UnknownTimeZoneError:
            st.error("Error: Zona horaria 'America/Hermosillo' no reconocida.")
            df['full_date'] = df['full_date'].dt.tz_convert('UTC')
        except Exception as e:
            st.error(f"Error al convertir la zona horaria: {e}")
            df['full_date'] = df['full_date'].dt.tz_convert('UTC')

        df['date'] = df['full_date'].dt.date
        df['year'] = df['full_date'].dt.year
        df['month'] = df['full_date'].dt.month
        df['day'] = df['full_date'].dt.day
        df['hour'] = df['full_date'].dt.hour

        df['word_count'] = df['content'].str.split().str.len().fillna(0).astype(int)

        return df


    df = process_json(data)

    if df.empty:
        st.warning("No se encontraron datos válidos para analizar después del procesamiento.")
        st.stop()

    # Filtro de Tiempo Global en la barra lateral
    st.sidebar.header("Filtro de Tiempo Global")
    time_filter_mode = st.sidebar.radio(
        "Selecciona la granularidad de los datos:",
        ["Análisis por año", "Análisis por mes"]
    )

    # Selección de Año
    all_years = sorted(df['year'].unique())
    default_year_index = all_years.index(df['year'].max()) if df['year'].max() in all_years else 0
    selected_year = st.sidebar.selectbox("Selecciona el Año", all_years, index=default_year_index)

    df_year_filtered = df[df['year'] == selected_year].copy()

    selected_month = None
    selected_month_name = None
    # Selección de Mes si la granularidad es por Días
    if time_filter_mode == "Análisis por mes":
        if not df_year_filtered.empty:
            month_names = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            available_months_nums = sorted(df_year_filtered['month'].unique())
            available_months_names = [month_names[m] for m in available_months_nums]

            latest_month_num = df_year_filtered['month'].max() if not df_year_filtered['month'].empty else 1
            try:
                default_month_index = available_months_nums.index(latest_month_num)
            except ValueError:
                default_month_index = 0


            selected_month_name = st.sidebar.selectbox(
                "Selecciona el Mes",
                available_months_names,
                index=default_month_index
            )
            selected_month = {v: k for k, v in month_names.items()}.get(selected_month_name, 1)


            df_filtered = df_year_filtered[df_year_filtered['month'] == selected_month].copy()
        else:
             df_filtered = pd.DataFrame()
             st.warning("No hay datos para el año seleccionado para filtrar por mes.")
    else:
         df_filtered = df_year_filtered.copy()


    if df_filtered.empty:
        st.warning("No se encontraron datos para el período seleccionado con los filtros aplicados.")
        st.stop()


    st.sidebar.header("Tabla de Contenidos")
    st.sidebar.markdown("[Tópicos más frecuentes](#topicos-mas-frecuentes)")
    st.sidebar.markdown("[Consultas en el tiempo](#consultas-en-el-tiempo)")
    st.sidebar.markdown("[Frecuencia por hora del día](#frecuencia-por-hora-del-dia)")
    st.sidebar.markdown("[Análisis de respuestas del asistente](#analisis-de-respuestas-del-asistente)")

    def preprocess(corpus):
        lemmatizer = WordNetLemmatizer()
        result = []
        for text in corpus.fillna(''):
            if isinstance(text, str):
                tokens = word_tokenize(text.lower())
                filtered = [lemmatizer.lemmatize(w) for w in tokens if w not in combined_stopwords and w.isalpha()]
                result.append(' '.join(filtered))
            else:
                result.append('')
        return result


    # Función para encontrar n-gramas más frecuentes
    def top_ngrams(corpus, n=1):
        try:
            if not corpus or all(text == '' for text in corpus):
                return []
            non_empty_corpus = [text for text in corpus if text != '']
            if not non_empty_corpus:
                 return []

            vec = CountVectorizer(ngram_range=(n, n)).fit(non_empty_corpus)
            bow = vec.transform(non_empty_corpus)
            sum_words = bow.sum(axis=0)
            freqs = [(word, sum_words[0, idx]) for word, idx in vec.vocabulary_.items()]
            return sorted(freqs, key=lambda x: x[1], reverse=True)[:12]
        except Exception as e:
            return []


    st.header("Tópicos más frecuentes")
    df_human_filtered = df_filtered[df_filtered['type'] == 'human'].copy()

    # Mostrar tópicos más frecuentes
    if not df_human_filtered.empty and df_human_filtered['content'].notna().any():
        corpus = preprocess(df_human_filtered['content'])
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

    # Mostrar métricas de consultas y conversaciones
    promedio_consultas = df_human_filtered.shape[0] / df_human_filtered['conversation_id'].nunique()
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"Total de consultas en el {'mes' if time_filter_mode == 'Análisis por mes' else 'Año'}", df_human_filtered.shape[0])
    with col2:
        st.metric(f"Promedio de consultas por día en el {'mes' if time_filter_mode == 'Análisis por mes' else 'Año'}", round(promedio_consultas))

    # Preparar datos para el gráfico de consultas en el tiempo según la granularidad seleccionada
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
    else: # time_filter_mode == "Ver por Meses en un Año"
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

    # Mostrar gráfico de consultas en el tiempo
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
    # Preparar datos para el gráfico de frecuencia por hora
    df_hour = df_filtered[df_filtered['type'] == 'human'].groupby('hour').size().reset_index(name='count')

    # Mostrar gráfico de frecuencia por hora
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
    df_bot_filtered = df_filtered[df_filtered['type'] == 'assistant'].copy()


    if not df_bot_filtered.empty:
        st.subheader("Longitud de respuestas")

        df_bot_filtered['word_count'] = pd.to_numeric(df_bot_filtered['word_count'], errors='coerce').fillna(0)

        # Mostrar histograma de longitud de respuestas
        if df_bot_filtered['word_count'].sum() > 0:
            fig = px.histogram(df_bot_filtered, x='word_count', nbins=30,
                                title=f"Distribución de longitud de respuestas {'en el mes' if time_filter_mode == 'Análisis por mes' else 'en el año'}",
                                color_discrete_sequence=['royalblue'])
            fig.update_layout(xaxis_title="Número de Palabras", yaxis_title="Frecuencia")
            fig.update_traces(marker=dict(opacity=0.7))

            avg_length = df_bot_filtered['word_count'].mean()
            if avg_length is not None and not np.isnan(avg_length):
                 fig.add_vline(x=avg_length, line_dash="dash", line_color="red", annotation_text=f"Promedio: {avg_length:.2f}", annotation_position="top right")

            st.plotly_chart(fig)

            # Mostrar métricas de longitud de respuestas
            avg_length = df_bot_filtered['word_count'].mean()
            min_length = df_bot_filtered['word_count'].min()
            max_length = df_bot_filtered['word_count'].max()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Longitud promedio", f"{round(avg_length)}")
            with col2:
                st.metric("Longitud mínima", f"{min_length}")
            with col3:
                st.metric("Longitud máxima", f"{max_length}")
        else:
             st.info("No hay datos de longitud de respuestas para mostrar en el período seleccionado.")


        # Análisis de Tokens y Costos (sin selección de granularidad duplicada)
        if 'total_tokens' in df_bot_filtered.columns and df_bot_filtered['total_tokens'].notna().any() and df_bot_filtered['total_tokens'].sum() > 0:
            st.subheader("Tokens y costos")

            total_tokens = df_bot_filtered['total_tokens'].sum()
            st.metric(f"Tokens totales en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"{round(total_tokens):,.0f}")

            # Determinar granularidad basada en el filtro de tiempo global
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

            else: 
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


            # Mostrar gráfico de Tokens en el tiempo
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

                # Mostrar métricas de Tokens
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"Promedio de tokens", f"{round(mean_tokens):,.0f}")
                with col2:
                    st.metric(f"Mínimo de tokens", f"{df_token_cost_time['total_tokens'].min():,.0f}")
                with col3:
                    st.metric(f"Máximo de tokens", f"{df_token_cost_time['total_tokens'].max():,.0f}")
            else:
                 st.info(f"No hay suficientes datos de tokens para mostrar en el período seleccionado con granularidad '{token_cost_granularity_label}'.")


            # Mostrar gráfico de Costo en el tiempo
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

                # Mostrar métricas de Costo
                total_cost = df_bot_filtered['cost'].sum()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"Costo total en el {"mes" if time_filter_mode == "Análisis por mes" else "año"}", f"${total_cost:.4f}")
                with col2:
                    st.metric(f"Costo promedio", f"${mean_cost:.4f}")
                with col3:
                    st.metric(f"Costo máximo", f"${df_token_cost_time['cost'].max():.4f}")

                # Mostrar distribución de costos por conversación
                cost_by_conversation = df_bot_filtered.groupby('conversation_id')['cost'].sum().reset_index()

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

                     # Mostrar métricas de costo por conversación
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


        # Análisis de Tiempo de Respuesta
        if 'response_time' in df_bot_filtered.columns and df_bot_filtered['response_time'].notna().any() and df_bot_filtered['response_time'].sum() > 0:
            st.subheader("Tiempo de respuesta")

            df_bot_filtered['response_time'] = pd.to_numeric(df_bot_filtered['response_time'], errors='coerce').fillna(0)
            df_response_time_positive = df_bot_filtered[df_bot_filtered['response_time'] > 0].copy()

            # Mostrar histograma de tiempo de respuesta
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
