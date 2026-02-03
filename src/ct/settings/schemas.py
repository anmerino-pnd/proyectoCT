from dataclasses import dataclass

@dataclass
class UserContext:
    session_id: str
    lista_precio: int