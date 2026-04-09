# prompts.py

FAITHFULNESS_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la FIDELIDAD de una respuesta.

**Definición**: Mide si las afirmaciones FACTUALES CONCRETAS en la respuesta son 
consistentes con la información provista por las herramientas o el historial de conversación.

{conversation_context}

**Pregunta del usuario:**
{question}

**Log completo de ejecución del agente (thinking + tool outputs):**
{verbose_log}

**Respuesta del asistente:**
{answer}

**Instrucciones:**
1. Lee el log completo — contiene tanto las decisiones del agente (🤖) 
   como los outputs reales de cada herramienta (🛠️).

2. Identifica SOLO afirmaciones factuales verificables en la respuesta:
   - Precios, nombres de productos, stock, códigos, promociones, especificaciones técnicas

3. Para cada afirmación, verifica si puede inferirse de:
   a) Algún tool output en el log (🛠️), O
   b) El historial de conversación previo

4. IGNORA completamente:
   - Frases de cortesía ("con gusto", "espero haberte ayudado")
   - Recomendaciones subjetivas ("es ideal para...", "buena opción")
   - Conocimiento general del dominio (compatibilidad de sockets, tipos de RAM, etc.)

5. Si el agente tomó un dato del historial → ES VÁLIDO, no penalizar

6. Solo penaliza cuando el agente invente datos concretos que NO están 
   ni en los tool outputs NI en el historial

Responde en JSON con el schema indicado.
"""

ANSWER_RELEVANCY_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la RELEVANCIA de la respuesta.

{conversation_context}

**Pregunta del usuario:**
{question}

**Log completo de ejecución del agente:**
{verbose_log}

**Respuesta del asistente:**
{answer}

**Instrucciones:**
1. Evalúa si la respuesta responde directamente a lo preguntado.
2. Considerá el contexto conversacional si la pregunta es ambigua.
3. Penaliza respuestas que evaden la pregunta o son demasiado vagas.
4. Penaliza información excesivamente irrelevante.
5. Considera si la respuesta está completa o le falta información clave.

Responde en JSON con el schema indicado.
"""

CONTEXT_PRECISION_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la PRECISIÓN DEL CONTEXTO.

**Definición**: Mide qué proporción de las herramientas usadas eran realmente necesarias.

{conversation_context}

**Pregunta del usuario:**
{question}

**Herramientas disponibles en el sistema:**
{available_tools}

**Log completo de ejecución del agente:**
{verbose_log}

**Respuesta final:**
{answer}

**Instrucciones:**
1. Del log, identificá cada tool que se llamó (líneas 🤖).
2. Para cada tool llamada, evaluá si su output contribuyó a la respuesta final.
3. Una tool es relevante si su output aportó información usada en la respuesta.
4. Una tool es irrelevante si se llamó pero no aportó nada a la respuesta.
5. Si no se usaron tools y era apropiado → score 1.0.

Responde en JSON con el schema indicado.
"""

CONTEXT_RECALL_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar el RECALL DEL CONTEXTO.

**Definición**: Mide si el agente utilizó TODAS las herramientas necesarias 
para dar una respuesta completa.

{conversation_context}

**Pregunta del usuario:**
{question}

**Herramientas disponibles:**
{available_tools}

**Log completo de ejecución del agente:**
{verbose_log}

**Respuesta final:**
{answer}

**Instrucciones:**
1. Basándote en la pregunta y el contexto, determiná qué tools DEBERÍAN haberse usado.
2. Del log, identificá qué tools SÍ se usaron (líneas 🤖).
3. Si la pregunta no requería tools → score 1.0.
4. Si faltaron tools necesarias → score bajo + listá cuáles en missing_tools.

Descripción de cada tool disponible:
- algolia_search_tool: Búsqueda de productos en el catálogo
- sales_rules_tool: Reglas de ventas, descuentos, promociones
- dolar_convertion_tool: Conversión de moneda / precio en dólares
- status_tool: Estado de pedidos o envíos
- get_support_info: Información de soporte al cliente
- who_are_we: Información sobre la empresa
- get_sucursales_info: Información de sucursales físicas

Responde en JSON con el schema indicado.
"""

CONVERSATION_CONTEXT_BLOCK = """
**Contexto conversacional (mensajes anteriores del usuario en esta sesión):**
{previous_messages}

⚠️ IMPORTANTE: Si la pregunta actual es ambigua o hace referencia implícita 
a un producto/tema mencionado antes, el agente CORRECTAMENTE tomó ese contexto 
del historial. NO penalices al agente por usar información del historial.
"""