# utils.py

def format_available_tools() -> str:
    return """
- algolia_search_tool: busca productos por nombre, devuelve precio, stock y si están en promoción. Uso: algolia_search_tool(producto='...', lowest_price=True|False)
- sales_rules_tool: consulta las reglas/promoción de un producto específico por clave. Usar SOLO si algolia indica que hay promoción. Uso: sales_rules_tool(clave='...')
- dolar_convertion_tool: convierte precio USD a MXN para cálculos de presupuesto. Uso: dolar_convertion_tool(dolar='PRECIO')
- status_tool: consulta el estado de un pedido por número de factura. Uso: status_tool(factura='FOLIO')
- get_support_info: responde sobre garantías, políticas, PartnerCT, CT Cloud, Docusmart, CT Arrendamiento, procedimientos, directorios de PM, etc.
- who_are_we: información general sobre CT Internacional como empresa.
- get_sucursales_info: ubicación, dirección, horarios, teléfonos y directorio de sucursales físicas.
""".strip()

def format_previous_messages(previous_messages: list[dict]) -> str:
    """Formatea el historial para incluir en prompts."""
    if not previous_messages:
        return "No hay mensajes previos."

    formatted = []
    for m in previous_messages:
        role = "Usuario" if m.get("role") == "human" else "Asistente"
        content = m.get("content", "")
        formatted.append(f"  - {role}: {content}")

    return "\n".join(formatted)


def format_verbose_log(verbose_log: str) -> str:
    """
    Devuelve el verbose_log tal cual.
    El LLM evaluador entiende el formato directamente.
    No hay nada que parsear — ya está estructurado.
    """
    if not verbose_log:
        return "No se usaron herramientas."
    return verbose_log