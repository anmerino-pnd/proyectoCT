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
DATA_DIR = BASE_DIR / "datos" / "productos_promociones_CT"
ARCHIVOS_CLAVE_DIR = BASE_DIR / "archivos_clave"
HISTORY_FILE = DATA_DIR / "history.json"
CLIENTES_FILE = ARCHIVOS_CLAVE_DIR / "lista_clientes.json"
