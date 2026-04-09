# ct/evaluation/utils.py

AVAILABLE_TOOLS = [
    "algolia_search_tool",
    "sales_rules_tool",
    "dolar_convertion_tool",
    "status_tool",
    "get_support_info",
    "who_are_we",
    "get_sucursales_info"
]


def format_previous_messages(previous_messages: list[dict]) -> str:
    """Formatea el historial para incluir en prompts."""
    if not previous_messages:
        return ""
    return "\n".join([
        f"  - Usuario: {m['content']}"
        for m in previous_messages
    ])


def format_verbose_log(verbose_log: str) -> str:
    """
    Devuelve el verbose_log tal cual.
    El LLM evaluador entiende el formato directamente.
    No hay nada que parsear — ya está estructurado.
    """
    if not verbose_log:
        return "No se usaron herramientas."
    return verbose_log