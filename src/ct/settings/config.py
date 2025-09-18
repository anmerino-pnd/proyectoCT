# config.py
from pathlib import Path

# Detecta la raíz del proyecto automáticamente (por ejemplo buscando "pyproject.toml")
def find_project_root(start_path: Path, marker_file: str = "pyproject.toml") -> Path:
    current = start_path.resolve()
    while not (current / marker_file).exists() and current != current.parent:
        current = current.parent
    return current

# Establece BASE_DIR en la raíz del proyecto
BASE_DIR = find_project_root(Path(__file__))

# Definición de rutas
VECTORS_DIR = BASE_DIR / "datos" / "vectorstores"
PRODUCTS_VECTOR_PATH = VECTORS_DIR / "products_vector_store"
SALES_PRODUCTS_VECTOR_PATH = VECTORS_DIR / "sales_products_vector_store"
SUPPORT_INFO_VECTOR_PATH = VECTORS_DIR / "guarantees_vector_store"

ID_SUCURSAL = BASE_DIR / "datos" / "idSucursal.json"
BASE_KNOWLEDGE = BASE_DIR / "datos" / "base_de_conocimientos"

# 🔥 Crear directorios automáticamente
for path in [VECTORS_DIR, PRODUCTS_VECTOR_PATH, SALES_PRODUCTS_VECTOR_PATH, BASE_KNOWLEDGE, SUPPORT_INFO_VECTOR_PATH]:
    path.mkdir(parents=True, exist_ok=True)
