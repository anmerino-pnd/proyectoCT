FAITHFULNESS_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la FIDELIDAD de una respuesta.

**Definición**: Mide si las afirmaciones en la respuesta son consistentes con 
la información provista por las herramientas (tools). Detecta alucinaciones.

**Pregunta del usuario:**
{question}

**Outputs de las herramientas usadas (contexto):**
{tool_outputs}

**Respuesta del asistente:**
{answer}

**Instrucciones:**
1. Identifica SOLO afirmaciones factuales verificables:
   - Precios, nombres de productos, stock, horarios, datos concretos
   
2. IGNORA completamente:
   - Frases de cortesía ("con gusto", "espero haberte ayudado")
   - Opiniones o recomendaciones subjetivas ("es una excelente opción")
   - Frases introductorias o de cierre
   - Información de conocimiento general del dominio

3. Si NO se usaron tools:
   - La respuesta es conversacional → score: 1.0 automático
   - La respuesta contiene datos específicos → score: 0.0

4. Solo penalizá cuando el agente invente datos concretos
   (precio incorrecto, producto inexistente, etc.)

Responde en JSON con el schema indicado.
"""

ANSWER_RELEVANCY_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la RELEVANCIA de la respuesta.

**Definición**: Mide qué tan bien la respuesta aborda la pregunta del usuario 
(completitud y ausencia de información irrelevante).

**Pregunta del usuario:**
{question}

**Respuesta del asistente:**
{answer}

**Historial de herramientas usadas:**
{tool_names}

**Instrucciones:**
1. Evalúa si la respuesta responde directamente a lo preguntado.
2. Penaliza respuestas que evaden la pregunta o son demasiado vagas.
3. Penaliza respuestas que incluyen información excesivamente irrelevante.
4. Considera si la respuesta está completa o le falta información clave.

Responde en JSON con el schema indicado.
"""

CONTEXT_PRECISION_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar la PRECISIÓN DEL CONTEXTO.

**Definición**: Mide qué proporción de las herramientas usadas eran realmente 
necesarias para responder la pregunta.

**Pregunta del usuario:**
{question}

**Herramientas disponibles en el sistema:**
{available_tools}

**Herramientas efectivamente usadas:**
{tools_used_with_args}

**Respuesta final:**
{answer}

**Instrucciones:**
1. Analiza si cada tool usada era necesaria para responder la pregunta.
2. Una tool es relevante si su output contribuyó a la respuesta.
3. Una tool es irrelevante si se llamó innecesariamente (ruido).
4. Si no se usaron tools y era apropiado → score 1.0.
5. Si no se usaron tools pero eran necesarias → penaliza en Context Recall.

Responde en JSON con el schema indicado.
"""

CONTEXT_RECALL_PROMPT = """
Eres un evaluador experto de sistemas de IA. Tu tarea es evaluar el RECALL DEL CONTEXTO.

**Definición**: Mide si el sistema utilizó TODAS las herramientas necesarias 
para dar una respuesta completa y correcta.

**Pregunta del usuario:**
{question}

**Herramientas disponibles en el sistema:**
{available_tools}

**Herramientas que SÍ se usaron:**
{tools_used}

**Respuesta final:**
{answer}

**Instrucciones:**
1. Basándote en la pregunta, determina qué herramientas DEBERÍAN haberse usado.
2. Compara con las que realmente se usaron.
3. Si la pregunta no requería tools → score 1.0.
4. Si faltaron tools necesarias → score bajo.
5. Sé específico en "missing_tools" sobre qué tools hubieran sido útiles.

Herramientas disponibles con descripción:
- algolia_search_tool: Búsqueda de productos en el catálogo
- sales_rules_tool: Reglas de ventas, descuentos, promociones
- dolar_convertion_tool: Conversión de moneda / precio en dólares
- status_tool: Estado de pedidos o envíos
- get_support_info: Información de soporte al cliente
- who_are_we: Información sobre la empresa
- get_sucursales_info: Información de sucursales físicas

Responde en JSON con el schema indicado.
"""