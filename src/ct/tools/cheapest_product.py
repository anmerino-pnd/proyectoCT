from ct.settings.config import CATEGORIES_VECTOR_PATH, BASE_KNOWLEDGE
from ct.settings.clients import ip, port, user, pwd, database
from ct.settings.clients import openai_api_key as api_key
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field, SecretStr
from langchain_openai import OpenAIEmbeddings
from string import Template
from toon import encode
import mysql.connector
import pymysql
pymysql.install_as_MySQLdb()
import json
import os

embeddings = OpenAIEmbeddings(api_key=SecretStr(api_key))
vectorstore = FAISS.load_local(
    str(CATEGORIES_VECTOR_PATH),
    embeddings
)
retriever = vectorstore.as_retriever()

with open(os.path.join(BASE_KNOWLEDGE, "types_dict.json"), "r", encoding="utf-8") as f:
    types_dict = json.load(f)

class RelevantCategories(BaseModel):
    query : str = Field(description="Interpreta la búsqueda o necesidad del usuario y utiliza este buscador para saber la categoría Padre del producto deseado")

class CheapestInput(BaseModel):
    types: tuple = Field(description="Clave del producto")
    listaPrecio: int = Field(description="Lista de precio al que pertenece el usuario")


def get_relevant_categories(query: str):
    categories_list = []
    relevant_categories = retriever.invoke(query)
    for category in relevant_categories:
        categories_list.append(category.page_content)
    return categories_list

def get_relevant_types(category: str):
    pass

def cheapest_product_tool(types: tuple, listaPrecio: int):
    pass