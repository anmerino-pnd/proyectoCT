# prompts.py

FAITHFULNESS_PROMPT = """
Eres un auditor forense de respuestas de IA. Tu objetivo es
determinar la FIDELIDAD de la respuesta — que no haya ninguna
afirmación concreta inventada.

**HISTORIAL DE CONVERSACIÓN:**
{conversation_context}

**PREGUNTA DEL USUARIO:**
{question}

**LOG DE EJECUCIÓN (Thinking + Tool Outputs):**
{verbose_log}

**RESPUESTA DEL ASISTENTE:**
{answer}

---
### PROTOCOLO DE EVALUACIÓN:

**PASO 1: EXTRACCIÓN DE AFIRMACIONES FACTUALES**
Analiza la respuesta y extrae una lista de afirmaciones concretas.
Una afirmación factual es cualquier dato específico: precios,
nombres de producto, cantidades, stock, specs técnicas, reglas
de negocio concretas, fechas o tiempos.
NO cuentan: cortesías, frases genéricas ("tenemos varios
modelos"), sugerencias vagas, ni información del historial
que el agente repite correctamente.

**PASO 2: BÚSQUEDA DE EVIDENCIA EN EL LOG**
Para cada afirmación:
- Si aparece en un tool output (🛠️): cita textual.
- Si viene del historial de conversación: marca "Historial".
- Si no aparece en ninguna fuente: "EVIDENCIA AUSENTE".

**PASO 3: CONTRASTE**
- SOPORTADO: evidencia confirma la afirmación exactamente.
- CONTRADICHO: evidencia dice algo diferente.
- ALUCINACIÓN: afirmación concreta sin evidencia.

**PASO 4: VEREDICTO FINAL**
Calcula el score con la fórmula:
  score = claims_supported / claims_total
  Redondea a 2 decimales.
  
  Caso edge: si claims_total = 0 (no hubo afirmaciones
  verificables), asigna score = 1.0 — el agente no inventó
  nada porque no afirmó nada concreto.

Responde en JSON con el esquema indicado. El campo 'reasoning'
debe incluir el detalle de los 4 pasos.
"""

ANSWER_RELEVANCY_PROMPT = """
Eres un auditor de calidad de IA. Tu objetivo es evaluar la
RELEVANCIA de la respuesta respecto a la intención del usuario.

**HISTORIAL DE CONVERSACIÓN:**
{conversation_context}

**PREGUNTA DEL USUARIO:**
{question}

**LOG DE EJECUCIÓN (Thinking + Tool Outputs):**
{verbose_log}

**RESPUESTA DEL ASISTENTE:**
{answer}

---
### PROTOCOLO DE EVALUACIÓN:

**PASO 1: ANÁLISIS DE NECESIDADES**
Identifica las necesidades explícitas e implícitas del usuario
considerando el contexto conversacional.

**PASO 2: MAPEO DE RESPUESTA**
Para cada necesidad:
- CUBIERTA: la respuesta la satisface completamente.
- PARCIAL: la menciona pero no la resuelve.
- IGNORADA: no aparece en la respuesta.

**PASO 3: EVALUACIÓN DE RUIDO**
Verifica si la respuesta añade información innecesaria que
confunde o distrae al usuario de su pregunta real.
Clasifica el ruido como:
- NINGUNO: toda la información es pertinente.
- MENOR: hay contexto extra pero no daña la comprensión.
- GRAVE: el ruido oscurece la respuesta principal.

**PASO 4: VEREDICTO FINAL**
Parte de la cobertura de necesidades y aplica penalización:
- Ruido NINGUNO o MENOR: sin descuento.
- Ruido GRAVE: descuenta hasta 0.15 del score base.

Guía:
- 1.0: todas las necesidades cubiertas, sin ruido.
- 0.75: necesidades principales cubiertas, falta algún detalle.
- 0.5: necesidades principales cubiertas pero con ruido grave
       o necesidades secundarias ignoradas.
- 0.0: respuesta irrelevante o no responde la pregunta.

Responde en JSON con el esquema indicado. El campo 'reasoning'
debe incluir el detalle de los 4 pasos.
"""

CONTEXT_PRECISION_PROMPT = """
Eres un auditor de eficiencia de herramientas. Tu objetivo es
evaluar la PRECISIÓN DEL CONTEXTO.

**HISTORIAL DE CONVERSACIÓN:**
{conversation_context}

**PREGUNTA DEL USUARIO:**
{question}

**LOG DE EJECUCIÓN (Thinking + Tool Outputs):**
{verbose_log}

**RESPUESTA FINAL:**
{answer}

---
### PROTOCOLO DE EVALUACIÓN:

**PASO 1: IDENTIFICACIÓN DE HERRAMIENTAS**
Lista todas las tools llamadas en el verbose_log (bloques 🤖).

**PASO 2: ANÁLISIS DE UTILIDAD**
Para cada tool llamada, evalúa si su invocación fue justificada:
- ÚTIL: su output aportó datos usados en la respuesta, O su
  output fue vacío/negativo y eso justificó no mencionar algo
  (el agente verificó correctamente).
- IRRELEVANTE: la tool no tenía relación con la pregunta
  del usuario Y su output tampoco influyó en la respuesta
  de ninguna forma.

**PASO 3: CÁLCULO DE RATIO**
Proporción de tools útiles vs total de tools llamadas.

**PASO 4: VEREDICTO FINAL**
- 1.0: todas las tools fueron útiles o necesarias.
- 0.5: la mayoría útiles, pero hubo llamadas innecesarias.
- 0.0: las tools llamadas no tenían relación con la respuesta.

Responde en JSON con el esquema indicado.
"""

CONTEXT_RECALL_PROMPT = """
Eres un auditor de completitud de información. Tu objetivo es
evaluar el RECALL DEL CONTEXTO.

**HISTORIAL DE CONVERSACIÓN:**
{conversation_context}

**PREGUNTA DEL USUARIO:**
{question}

**LOG DE EJECUCIÓN (Thinking + Tool Outputs):**
{verbose_log}

**RESPUESTA FINAL:**
{answer}

**TOOLS DISPONIBLES EN EL SISTEMA:**
{available_tools}
IMPORTANTE: solo puedes señalar como "faltante" una tool de
esta lista. No inventes tools que no existen en el sistema.

---
### PROTOCOLO DE EVALUACIÓN:

**PASO 1: DEFINICIÓN DE INFORMACIÓN NECESARIA**
Basándote en la pregunta y el contexto, define qué datos eran
estrictamente necesarios para dar una respuesta completa.

**PASO 2: VERIFICACIÓN DE LLAMADAS**
¿El agente llamó a las tools capaces de proveer esos datos?
- ENCONTRADO: la tool correcta fue llamada y produjo output.
- FALTANTE: la información necesaria no fue buscada con ninguna
  tool de la lista disponible.

**PASO 3: ANÁLISIS DE COBERTURA**
¿La respuesta final es completa con la información obtenida?

**PASO 4: VEREDICTO FINAL**
- 1.0: el agente usó todas las tools necesarias.
- 0.5: obtuvo parte de la info, faltó consultar alguna clave.
- 0.0: ignoró tools críticas y la respuesta es incompleta.

Responde en JSON con el esquema indicado.
"""

CONVERSATION_CONTEXT_BLOCK = """
**Contexto conversacional (mensajes anteriores del usuario y asistente en esta sesión):**
{previous_messages}

IMPORTANTE: Si la pregunta actual es ambigua o hace referencia implícita
a un producto/tema mencionado antes, el agente CORRECTAMENTE tomó ese contexto
del historial. NO penalices al agente por usar información del historial.
"""
