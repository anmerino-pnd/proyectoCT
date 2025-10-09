import pandas as pd
from pydantic import BaseModel, Field
from ct.settings.config import DATA_DIR
from ct.settings.clients import openai_api_key

from langchain.agents.agent_types import AgentType
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent


class SucursalesInput(BaseModel):
    query: str = Field(description="Consulta del usuario para encontrar información sobre sucursales")

df = pd.read_csv(f"{DATA_DIR}/sucursales.csv")
agent = create_pandas_dataframe_agent(
    ChatOpenAI(
        temperature=0, 
        model="gpt-4.1", 
        api_key=openai_api_key,
        cache=True,
        max_tokens=None,
        timeout=None,
        max_retries=2),
    df,
    verbose=True,
    agent_type=AgentType.OPENAI_FUNCTIONS,
    allow_dangerous_code=True
)

def get_sucursales_info(query: str) -> str:
    return agent.invoke(
        f"""
Utiliza la tabla para buscar información y contestar la consulta del usuario.
Las sucursales siempre mencionalas tal y como aparecen en la tabla.

columnas: {df.columns}
consulta: {query}
"""       
        )['output']
