# utils.py

import json
import re


# Fuente de verdad: las tools registradas viven en
# src/ct/langchain/tool_agent.py (self.tools, ~líneas 90-98).
# Mantener esta lista en sync con ese conjunto. Hoy son 7 tools.
def format_available_tools() -> str:
    return """
- algolia_search_tool: busca productos por nombre, devuelve precio, stock y si están en promoción. Uso: algolia_search_tool(producto='...', lowest_price=True|False)
- sales_rules_tool: consulta reglas/promoción de varios productos EN UNA SOLA llamada, pasando la lista de claves. Usar SOLO si algolia indica que hay promoción. Uso: sales_rules_tool(claves=['CLAVE_1','CLAVE_2','CLAVE_3'])
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


# Vallas de código que el chatbot emite en la respuesta para que la interfaz
# renderice tarjetas de producto y botones de sugerencia. El texto factual
# (precio, existencias, promoción, clave) vive DENTRO de ```ct-products```;
# ver src/ct/settings/prompt.py -> reglas_generales.tarjetas_de_producto.
_CT_BLOCK_RE = re.compile(
    r"```ct-(products|suggestions)\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def split_answer_blocks(answer: str) -> tuple[str, list[dict], list[str]]:
    """
    Separa la respuesta del chatbot en sus tres componentes:

    - prose:       el texto en lenguaje natural (lo que el usuario lee como
                   conversación), SIN los bloques estructurados.
    - products:    lista de dicts parseados del bloque ```ct-products```
                   (tarjetas de producto). [] si no hay o el JSON es inválido.
    - suggestions: lista de strings del bloque ```ct-suggestions```.
                   [] si no hay o el JSON es inválido.

    Es tolerante a JSON malformado: nunca lanza, cae a lista vacía.
    """
    if not answer:
        return "", [], []

    products: list[dict] = []
    suggestions: list[str] = []

    for match in _CT_BLOCK_RE.finditer(answer):
        kind = match.group(1).lower()
        payload = match.group(2).strip()
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            continue

        if kind == "products" and isinstance(parsed, list):
            products.extend(p for p in parsed if isinstance(p, dict))
        elif kind == "suggestions" and isinstance(parsed, list):
            suggestions.extend(str(s) for s in parsed)

    # Quitar los bloques del texto para obtener la prosa limpia.
    prose = _CT_BLOCK_RE.sub("", answer).strip()

    return prose, products, suggestions


# Campos factuales de una tarjeta que deben coincidir con el output de las tools.
_CARD_FIELDS = [
    ("clave", "Clave CT"),
    ("marca", "Marca"),
    ("modelo", "Modelo"),
    ("precio", "Precio"),
    ("moneda", "Moneda"),
    ("en_su_sucursal", "Existencia en su sucursal"),
    ("en_otras_sucursales", "Existencia en otras sucursales"),
    ("en_promocion", "En promoción"),
]


def format_product_cards(products: list[dict]) -> str:
    """
    Renderiza las tarjetas de producto como una sección legible de
    afirmaciones factuales, para que faithfulness las contraste campo por
    campo contra los tool outputs (🛠️) del verbose_log.

    Devuelve "" si no hay tarjetas.
    """
    if not products:
        return ""

    lines = []
    for i, card in enumerate(products, start=1):
        lines.append(f"Tarjeta {i}:")
        for key, label in _CARD_FIELDS:
            if key in card:
                lines.append(f"  - {label}: {card[key]}")
    return "\n".join(lines)
