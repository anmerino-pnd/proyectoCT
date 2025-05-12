import streamlit as st
import os
import json
import pandas as pd
import pytz
import nltk
import spacy
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords as nltk_stopwords
from sklearn.feature_extraction.text import CountVectorizer

# ==== Setup inicial con control ====
nltk_needed = ['wordnet', 'punkt', 'stopwords', 'punkt_tab']
for resource in nltk_needed:
    try:
        nltk.data.find(f"corpora/{resource}")
    except LookupError:
        nltk.download(resource)

@st.cache_resource
def load_spacy_model():
    return spacy.load("es_core_news_lg")

nlp = load_spacy_model()

# ==== Stopwords combinadas ====
stop_words_spacy = nlp.Defaults.stop_words
stop_words_nltk = set(nltk_stopwords.words('spanish'))
custom_stopwords = {"mx", "https", "dame", "hola", "quiero", "puedes", "gustaría", "interesan", "opción", "opciones", "opcion"}
combined_stopwords = stop_words_spacy.union(stop_words_nltk, custom_stopwords)

for word in combined_stopwords:
    nlp.vocab[word].is_stop = True

# ==== Cargar el JSON desde archivo o subir ====
st.title("Análisis de Historial de Conversaciones")

data = None
default_json_path = "history_backup.json"

if os.path.exists(default_json_path):
    try:
        with open(default_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"No se pudo cargar {default_json_path}: {e}")


if data:
    @st.cache_data
    def process_json(raw_data):
        rows = []
        for conversation_id, msgs in raw_data.items():
            for i in msgs:
                if isinstance(i, dict) and all(k in i for k in ['type', 'content', 'timestamp']):
                    row_data = {
                        'conversation_id': conversation_id,
                        'type': i['type'],
                        'content': i['content'],
                        'date': i['timestamp']
                    }
                    
                    # Extraer información de metadatos si está disponible
                    if i.get('metadata'):
                        metadata = i.get('metadata')
                        if metadata.get('tokens'):
                            row_data['input_tokens'] = metadata.get('tokens').get('input', 0)
                            row_data['output_tokens'] = metadata.get('tokens').get('output', 0)
                            row_data['total_tokens'] = metadata.get('tokens').get('total', 0)
                            row_data['cost'] = metadata.get('tokens').get('estimated_cost', 0)
                        
                        if metadata.get('duration'):
                            row_data['response_time'] = metadata.get('duration').get('seconds', 0)
                            row_data['tokens_per_second'] = metadata.get('duration').get('tokens_per_second', 0)
                        
                        if metadata.get('cost_model'):
                            row_data['model'] = metadata.get('cost_model')
                    
                    rows.append(row_data)
                    
        df = pd.DataFrame(rows)
        df['full_date'] = pd.to_datetime(df['date'], utc=True, errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        tz = pytz.timezone("America/Hermosillo")
        df['full_date'] = df['full_date'].dt.tz_convert(tz)
        df['date'] = df['full_date'].dt.date
        df['year'] = df['full_date'].dt.year
        df['month'] = df['full_date'].dt.month
        df['day'] = df['full_date'].dt.day
        df['hour'] = df['full_date'].dt.hour
        
        # Calcular longitud de contenido
        df['word_count'] = df['content'].str.split().str.len()
        
        return df

    df = process_json(data)

    if df.empty:
        st.warning("No se encontraron datos válidos.")
    else:
        def preprocess(corpus):
            lemmatizer = WordNetLemmatizer()
            result = []
            for text in corpus:
                tokens = word_tokenize(text.lower())
                filtered = [lemmatizer.lemmatize(w) for w in tokens if w not in combined_stopwords and w.isalpha()]
                result.append(' '.join(filtered))
            return result

        def top_ngrams(corpus, n=1):
            try:
                vec = CountVectorizer(ngram_range=(n, n)).fit(corpus)
                bow = vec.transform(corpus)
                sum_words = bow.sum(axis=0)
                freqs = [(word, sum_words[0, idx]) for word, idx in vec.vocabulary_.items()]
                return sorted(freqs, key=lambda x: x[1], reverse=True)[:12]
            except:
                return []

        st.header("Tópicos más frecuentes")
        df_human = df[df['type'] == 'human'].copy()

        if not df_human.empty and df_human['content'].notna().any():
            corpus = preprocess(df_human['content'].fillna(''))
            for n in [1, 2]:
                top = top_ngrams(corpus, n)
                if top:
                    label = f"{n}-grama" if n == 1 else f"{n}-gramas"
                    df_top = pd.DataFrame(top, columns=[label, "Frecuencia"])
                    
                    fig = px.bar(df_top, x="Frecuencia", y=label,
                                orientation="h", 
                                color="Frecuencia", 
                                color_continuous_scale=["#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"])
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig)
        else:
            st.info("No hay preguntas humanas válidas.")

        # Evolución temporal
        st.header("Consultas en el Tiempo")

        # Total preguntas en el año
        st.metric("Total de Consultas en el Año", df_human.shape[0])
        st.metric("Total de Conversaciones en el Año", df_human['conversation_id'].nunique())

        # Seleccionar un mes para analizar
        month = st.selectbox("Selecciona un mes para analizar", df_human['month'].unique(), index=0,
                             key="time_month_selector")
        df_metric = df_human[df_human['month'] == month].copy()

        st.metric("Total de Consultas en el Mes", df_metric.shape[0])
        st.metric("Total de Conversaciones en el Mes", df_metric['conversation_id'].nunique()) 

        df_time = (
            df_human
            .groupby(df_human['full_date'].dt.date)
            .size()
            .reset_index(name='count')
            .rename(columns={'full_date': 'date'})
        )
        df_time['date'] = pd.to_datetime(df_time['date'])  # necesario para que Plotly lo interprete bien

    if not df_time.empty:
        mean = df_time['count'].mean()
        std = df_time['count'].std()

        fig = go.Figure()

        # Línea principal
        fig.add_trace(go.Scatter(
            x=df_time['date'], y=df_time['count'],
            mode='lines+markers',
            line=dict(color='blue'),
            showlegend=False
        ))

        # Banda superior
        fig.add_trace(go.Scatter(
            x=df_time['date'], y=df_time['count'] + std,
            mode='lines',
            line=dict(width=0),
            showlegend=False
        ))

        # Banda inferior
        fig.add_trace(go.Scatter(
            x=df_time['date'], y=df_time['count'] - std,
            mode='lines',
            fill='tonexty',
            line=dict(width=0),
            fillcolor='rgba(0,0,255,0.1)',
            showlegend=False
        ))

        fig.update_layout(
            title="Consultas por fecha",
            xaxis_title="Fecha",
            yaxis_title="Cantidad de Consultas",
            xaxis=dict(
                tickformat="%Y-%m-%d",  # Formato de fecha
                tickangle=0  # Opcional: inclina las etiquetas para mejor lectura
            )
        )

        st.plotly_chart(fig)

        # Frecuencia por hora
        st.header("Frecuencia por Hora del Día")
        df_hour = df_human.groupby('hour').size().reset_index(name='count')
        if not df_hour.empty:
            mean = df_hour['count'].mean()
            std = df_hour['count'].std()

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df_hour['hour'], y=df_hour['count'],
                mode='lines+markers',
                line=dict(color='blue'),
                showlegend=False
            ))

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

            fig.update_layout(title="Consultas por hora",
                            xaxis_title="Hora del Día",
                            yaxis_title="Cantidad de Consultas",
                            xaxis=dict(tickangle=0))

            st.plotly_chart(fig)
        
        # Análisis de respuestas del bot
        st.header("Análisis de Respuestas del Asistente")
        df_bot = df[df['type'] == 'assistant'].copy()

        if not df_bot.empty:
            # Distribución de longitud de respuestas (conteo de palabras)
            st.subheader("Longitud de Respuestas")
            
            fig = px.histogram(df_bot, x='word_count', nbins=30,
                                title="Distribución de Longitud de Respuestas",
                                color_discrete_sequence=['royalblue'])
            fig.update_layout(xaxis_title="Número de Palabras", yaxis_title="Frecuencia")
            st.plotly_chart(fig)
            
            # Estadísticas básicas de longitud
            avg_length = df_bot['word_count'].mean()
            min_length = df_bot['word_count'].min()
            max_length = df_bot['word_count'].max()
            st.metric("Longitud Promedio de Respuestas", f"{avg_length:.2f} palabras")
            st.metric("Longitud Mínima de Respuestas", f"{min_length} palabras")
            st.metric("Longitud Máxima de Respuestas", f"{max_length} palabras")
            
            # Análisis de tokens y costos (si hay datos disponibles)
            if 'total_tokens' in df_bot.columns and df_bot['total_tokens'].notna().any():
                st.subheader("Análisis de Tokens y Costos")
                
                # Tokens totales en el año
                total_tokens = df_bot['total_tokens'].sum()
                st.metric("Tokens Totales", f"{total_tokens:,.0f} tokens")
                
                # Selección de intervalo de tiempo
                time_granularity = st.radio(
                    "Granularidad del tiempo:",
                    ["Diario", "Mensual"],
                    horizontal=True
                )
                
                # Preparar datos según la granularidad seleccionada
                if time_granularity == "Diario":
                    # Agrupar por fecha completa (día)
                    df_time = (
                        df_bot
                        .groupby(df_bot['full_date'].dt.date)
                        .agg({
                            'total_tokens': 'sum',
                            'cost': 'sum' if 'cost' in df_bot.columns else 'count'  # Si no hay costo, usamos count
                        })
                        .reset_index()
                        .rename(columns={'full_date': 'date'})
                    )
                    df_time['date'] = pd.to_datetime(df_time['date'])
                    date_format = "%Y-%m-%d"
                    title_suffix = "por Día"
                    
                else:  # Mensual
                    # Crear columna año-mes
                    df_bot['year_month'] = df_bot['full_date'].dt.strftime('%Y-%m')
                    
                    # Agrupar por año-mes
                    df_time = (
                        df_bot
                        .groupby('year_month')
                        .agg({
                            'total_tokens': 'sum',
                            'cost': 'sum' if 'cost' in df_bot.columns else 'count'
                        })
                        .reset_index()
                    )
                    # Convertir año-mes a fecha (primer día del mes)
                    df_time['date'] = pd.to_datetime(df_time['year_month'] + '-01')
                    date_format = "%Y-%m"
                    title_suffix = "por Mes"
                
                # 1. Gráfico de tokens con banda de desviación estándar
                if not df_time.empty:
                    mean_tokens = df_time['total_tokens'].mean()
                    std_tokens = df_time['total_tokens'].std()
                    
                    fig1 = go.Figure()
                    
                    # Línea principal
                    fig1.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['total_tokens'],
                        mode='lines+markers',
                        line=dict(color='blue'),
                        name='Tokens'
                    ))
                    
                    # Banda superior
                    fig1.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['total_tokens'] + std_tokens,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False
                    ))
                    
                    # Banda inferior
                    fig1.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['total_tokens'] - std_tokens,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(0,0,255,0.1)',
                        showlegend=False
                    ))
                    
                    # Línea de promedio
                    fig1.add_trace(go.Scatter(
                        x=df_time['date'],
                        y=[mean_tokens] * len(df_time),
                        mode='lines',
                        line=dict(color='red', dash='dash'),
                        name=f'Promedio: {mean_tokens:,.0f}'
                    ))
                    
                    fig1.update_layout(
                        title=f"Tokens {title_suffix}",
                        xaxis_title="Fecha",
                        yaxis_title="Cantidad de Tokens",
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
                    
                    st.plotly_chart(fig1, use_container_width=True)
                    
                    # Métricas adicionales
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Promedio de Tokens", f"{mean_tokens:,.0f}")
                    with col2:
                        st.metric("Desviación Estándar", f"{std_tokens:,.0f}")
                    with col3:
                        st.metric("Máximo de Tokens", f"{df_time['total_tokens'].max():,.0f}")
                
                # 2. Gráfico de costos si están disponibles
                if 'cost' in df_bot.columns and df_bot['cost'].notna().any():
                    mean_cost = df_time['cost'].mean()
                    std_cost = df_time['cost'].std()
                    
                    fig2 = go.Figure()
                    
                    # Línea principal
                    fig2.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['cost'],
                        mode='lines+markers',
                        line=dict(color='green'),
                        name='Costo'
                    ))
                    
                    # Banda superior
                    fig2.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['cost'] + std_cost,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False
                    ))
                    
                    # Banda inferior
                    fig2.add_trace(go.Scatter(
                        x=df_time['date'], 
                        y=df_time['cost'] - std_cost,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(0,128,0,0.1)',
                        showlegend=False
                    ))
                    
                    # Línea de promedio
                    fig2.add_trace(go.Scatter(
                        x=df_time['date'],
                        y=[mean_cost] * len(df_time),
                        mode='lines',
                        line=dict(color='red', dash='dash'),
                        name=f'Promedio: ${mean_cost:.4f}'
                    ))
                    
                    fig2.update_layout(
                        title=f"Costo {title_suffix}",
                        xaxis_title="Fecha",
                        yaxis_title="Costo ($USD)",
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
                    
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # Métricas de costo
                    total_cost = df_bot['cost'].sum()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Costo Total", f"${total_cost:.4f}")
                    with col2:
                        st.metric("Promedio de Costo", f"${mean_cost:.4f}")
                    with col3:
                        st.metric("Costo Máximo", f"${df_time['cost'].max():.4f}")
                
                    # Tabla detallada (opcional, expandible)
                    with st.expander("Ver datos detallados"):
                        st.dataframe(
                            df_time[['date', 'total_tokens'] + (['cost'] if 'cost' in df_time.columns else [])],
                            use_container_width=True
                        )
                    
                    # Costo por conversación
                    cost_by_conversation = df_bot.groupby('conversation_id')['cost'].sum().reset_index()
                    mean_cost = cost_by_conversation['cost'].mean()
                    std_cost = cost_by_conversation['cost'].std()

                    # Crear un histograma con línea de densidad superpuesta
                    fig = go.Figure()

                    # Histograma
                    fig.add_trace(go.Histogram(
                        x=cost_by_conversation['cost'],
                        nbinsx=30,
                        name='Frecuencia',
                        marker=dict(color='royalblue', opacity=0.7)
                    ))

                    # Línea de promedio
                    fig.add_trace(go.Scatter(
                        x=[mean_cost, mean_cost],
                        y=[0, cost_by_conversation.shape[0] * 0.25],  # Ajustar altura según datos
                        mode='lines',
                        line=dict(color='red', dash='dash', width=2),
                        name=f'Promedio: ${mean_cost:.4f}'
                    ))

                    fig.update_layout(
                        title="Distribución de Costos por Conversación",
                        xaxis_title="Costo ($USD)",
                        yaxis_title="Número de Conversaciones",
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

                    # Mostrar estadísticas adicionales
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Conversaciones Totales", f"{cost_by_conversation.shape[0]}")
                    with col2:
                        st.metric("Costo Promedio por Conversación", f"${mean_cost:.4f}")
                    with col3:
                        st.metric("Costo Máximo por Conversación", f"${cost_by_conversation['cost'].max():.4f}")
                                
            # Análisis de tiempo de respuesta (si hay datos disponibles)
            if 'response_time' in df_bot.columns and df_bot['response_time'].notna().any():
                st.subheader("Tiempo de Respuesta")
                
                # Gráfico de distribución de tiempos de respuesta
                fig = px.histogram(df_bot, x='response_time', nbins=50,
                                    title="Distribución de Tiempos de Respuesta",
                                    color_discrete_sequence=['royalblue'])
                fig.update_layout(xaxis_title="Tiempo (segundos)", yaxis_title="Frecuencia")
                fig.update_traces(marker=dict(opacity=0.7))
                st.plotly_chart(fig)
                
                # Tiempo medio de respuesta
                avg_response_time = df_bot['response_time'].mean()
                st.metric("Tiempo Medio de Respuesta (segundos)", f"{avg_response_time:.2f}")
                
                st.write(df_bot)
                # Relación entre longitud y tiempo de respuesta
                fig = px.histogram(df_bot, x='response_time', y='total_tokens',
                                    title="Relación entre los tokens de respuesta y Tiempo de Respuesta",
                                    color_discrete_sequence=['royalblue'])
                fig.update_traces(marker=dict(opacity=0.7))
                fig.update_layout(xaxis_title="Tiempo de Respuesta (segundos)", yaxis_title="Longitud de Respuesta (palabras)")
                st.plotly_chart(fig)
                
else:
    st.info("Por favor, sube un archivo JSON o asegúrate de tener `history_backup.json` disponible.")