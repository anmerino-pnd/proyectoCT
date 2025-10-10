import sys
import json
import pandas as pd
from io import StringIO
from pydantic import BaseModel, Field
from ct.settings.config import DATA_DIR

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

def get_sucursales_info(code: str) -> str:
    localenv = {"df": df.copy(), "pd": pd, "json": json, "result": None}
    
    try:
        # Capturar prints
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Ejecutar código
        exec(code, {"__builtins__": __builtins__, "pd": pd, "json": json}, localenv)
        
        # Restaurar stdout
        sys.stdout = old_stdout
        
        # Obtener resultado
        printed_output = captured_output.getvalue()
        result_value = localenv.get("result")
        
        # Retornar lo que haya disponible
        if result_value is not None:
            return str(result_value)
        elif printed_output:
            return printed_output.strip()
        else:
            return "Código ejecutado correctamente pero no retornó ningún resultado. Use print() o asigne a 'result'."
            
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error ejecutando código: {str(e)}"