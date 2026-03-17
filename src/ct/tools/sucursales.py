import sys
import json
import pandas as pd
from io import StringIO
from pydantic import BaseModel, Field
from ct.settings.config import DATA_DIR
from ct.settings.schemas import UserContext
from langchain.tools import ToolRuntime, tool
class SucursalesInput(BaseModel):
    code: str = Field(description="Código Python para analizar el DataFrame 'df' con información de las sucursales. Debe usar print() para mostrar resultados o asignar el resultado a la variable 'result'.")

# Cargar DataFrame
df = pd.read_csv(f"{DATA_DIR}/sucursales.csv")

if 'directorio' in df.columns:
    def safe_json_loads(x):
        """Intenta deserializar JSON, retorna lista vacía si falla"""
        if pd.isna(x) or x == '' or x == 'nan':
            return []
        try:
            return json.loads(x)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Si no es JSON válido, retornar como string
            return str(x)
    df['directorio'] = df['directorio'].apply(safe_json_loads)

@tool(args_schema=SucursalesInput)
def get_sucursales_info(code: str) -> str:
    """Información sobre la empresa"""
    localenv = {"df": df.copy(), "pd": pd, "json": json, "result": None}
    
    old_stdout = sys.stdout  # ✅ inicializar antes del try garantiza que siempre esté definida

    try:
        sys.stdout = captured_output = StringIO()
        
        exec(code, {"__builtins__": __builtins__, "pd": pd, "json": json}, localenv)
        
        sys.stdout = old_stdout
        
        printed_output = captured_output.getvalue()
        result_value = localenv.get("result")
        
        if result_value is not None:
            return str(result_value)
        elif printed_output:
            return printed_output.strip()
        else:
            return "Código ejecutado correctamente pero no retornó ningún resultado. Use print() o asigne a 'result'."
            
    except Exception as e:
        sys.stdout = old_stdout  # ✅ ahora siempre está definida
        return f"Error ejecutando código: {str(e)}"