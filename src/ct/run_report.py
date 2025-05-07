import streamlit as st
import os
import json
import pandas as pd
import pytz
import nltk
import spacy
import plotly.express as px
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
custom_stopwords = {"mx", "https", "dame", "hola", "quiero", "puedes", "gustaría"}
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
        st.success(f"Archivo cargado: {default_json_path}")
    except Exception as e:
        st.error(f"No se pudo cargar {default_json_path}: {e}")

uploaded_file = st.file_uploader("O sube un archivo JSON", type="json")

if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        st.success("Archivo subido correctamente.")
    except Exception as e:
        st.error(f"Error al leer el archivo JSON: {e}")

if data:
    @st.cache_data
    def process_json(raw_data):
        rows = []
        for _, msgs in raw_data.items():
            for i in msgs:
                if isinstance(i, dict) and all(k in i for k in ['type', 'content', 'timestamp']):
                    rows.append({
                        'type': i['type'],
                        'content': i['content'],
                        'date': i['timestamp']
                    })
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'], utc=True, errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        tz = pytz.timezone("America/Hermosillo")
        df['date'] = df['date'].dt.tz_convert(tz)
        df['day'] = df['date'].dt.date
        df['hour'] = df['date'].dt.hour
        return df

    df = process_json(data)

    if df.empty:
        st.warning("No se encontraron datos válidos.")
    else:
        st.dataframe(df.head())

        def preprocess(corpus):
            lemmatizer = WordNetLemmatizer()
            result = []
            for text in corpus:
                tokens = word_tokenize(text.lower())
                filtered = [lemmatizer.lemmatize(w) for w in tokens if w not in combined_stopwords and len(w) > 2]
                result.append(' '.join(filtered))
            return result

        def top_ngrams(corpus, n=1):
            try:
                vec = CountVectorizer(ngram_range=(n, n)).fit(corpus)
                bow = vec.transform(corpus)
                sum_words = bow.sum(axis=0)
                freqs = [(word, sum_words[0, idx]) for word, idx in vec.vocabulary_.items()]
                return sorted(freqs, key=lambda x: x[1], reverse=True)[:10]
            except:
                return []

        st.header("N-gramas de Preguntas Humanas")
        df_human = df[df['type'] == 'human'].copy()
        if not df_human.empty and df_human['content'].notna().any():
            corpus = preprocess(df_human['content'].fillna(''))
            for n in [1, 2]:
                top = top_ngrams(corpus, n)
                if top:
                    label = f"{n}-grama" if n == 1 else f"{n}-gramas"
                    df_top = pd.DataFrame(top, columns=[label, "Frecuencia"])
                    st.subheader(f"Top {label}")
                    st.dataframe(df_top)
                    fig = px.bar(df_top, x="Frecuencia", y=label, orientation="h", title=f"Top {label}")
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig)
        else:
            st.info("No hay preguntas humanas válidas.")

        # Evolución temporal
        st.header("Preguntas en el Tiempo")
        df_time = df_human.groupby('day').size().reset_index(name='count')
        if not df_time.empty:
            fig = px.line(df_time, x='day', y='count', markers=True, title="Preguntas por día")
            st.plotly_chart(fig)

        # Frecuencia por hora
        st.header("Frecuencia por Hora del Día")
        df_hour = df_human.groupby('hour').size().reset_index(name='count')
        if not df_hour.empty:
            fig = px.line(df_hour, x='hour', y='count', markers=True, title="Preguntas por hora")
            fig.update_layout(xaxis=dict(dtick=1))
            st.plotly_chart(fig)
else:
    st.info("Por favor, sube un archivo JSON o asegúrate de tener `history_backup.json` disponible.")


