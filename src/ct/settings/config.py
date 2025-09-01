# config.py
from pathlib import Path

# Detecta la raíz del proyecto automáticamente (por ejemplo buscando "requirements.txt")
def find_project_root(start_path: Path, marker_file: str = "pyproject.toml") -> Path:
    current = start_path.resolve()
    while not (current / marker_file).exists() and current != current.parent:
        current = current.parent
    return current

# Establece BASE_DIR en la raíz del proyecto
BASE_DIR = find_project_root(Path(__file__))
DATA_DIR = BASE_DIR / "datos" / "vectorstores" / "sales_products_vector_store"
VECTORS_DIR = BASE_DIR / "datos" / "vectorstores"
PRODUCTS_VECTOR_PATH = VECTORS_DIR / "products_vector_store"
SALES_PRODUCTS_VECTOR_PATH = VECTORS_DIR / "sales_products_vector_store"

ID_SUCURSAL = BASE_DIR / "datos" / "idSucursal.json"
BASE_KNOWLEDGE = BASE_DIR / "datos" / "base_de_conocimientos"