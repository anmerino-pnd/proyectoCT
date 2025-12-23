import os
import ollama

def _get_paragraphs(text: str, n_chars: int):
    """
    Obtiene los últimos párrafos completos para el contexto.
    Estrategia robusta para mantener coherencia semántica.
    """
    if not text: 
        return ""
    
    # Separamos por doble salto para identificar bloques lógicos
    paragraphs = text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    result = []
    char_count = 0

    # Vamos de atrás hacia adelante llenando el buffer
    for paragraph in reversed(paragraphs):
        # Insertamos al inicio para mantener el orden original de lectura
        result.insert(0, paragraph)
        char_count += len(paragraph)
        if char_count >= n_chars:
            break
    
    return '\n\n'.join(result)

def guide_creation(folder_path: str, model: str = "gemma2:27b", context_size: int = 1000):
    # 1. Validación robusta de imágenes
    valid_exts = (".jpg", ".jpeg", ".png")
    image_paths = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(valid_exts)
    ]

    # Ordenamiento seguro (Intenta numérico, si falla usa alfabético)
    try:
        image_paths.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))
    except ValueError:
        print("⚠️ Advertencia: Se detectaron nombres no numéricos. Ordenando alfabéticamente.")
        image_paths.sort()

    full_answer = ''
    total_batches = (len(image_paths) + 2) // 3
    
    print(f"🚀 Iniciando generación de guía con {len(image_paths)} imágenes.")

    for batch_num, i in enumerate(range(0, len(image_paths), 3), start=1):
        print(f"📸 Procesando Lote {batch_num}/{total_batches}...")

        # Obtener contexto
        if full_answer:
            prev_fragment = _get_paragraphs(full_answer, n_chars=context_size)
            # Pequeño log visual para saber qué está "leyendo" el modelo
            print(f"   📝 Contexto inyectado: {len(prev_fragment)} caracteres finales.")
        else:
            prev_fragment = "Inicio del tutorial."

        current_group = image_paths[i:i+3]

        # 2. Prompt Optimizado para Estructura
        system_instructions = f"""
Eres un redactor técnico experto creando documentación para CT Internacional.
Tu objetivo es escribir una guía basada en las capturas de pantalla, solamente de lo que ves de ellas, no agregas información adicional ni inventas o usas conocimiento fundamental.

INSTRUCCIONES:
1. Analiza las imágenes del Lote {batch_num} y describe las acciones técnicas.
2. Continúa la redacción fluidamente desde el contexto previo.
3. Usa formato Markdown: Negritas para botones/menús (ej: **Guardar**) y listas numéricas para pasos.
4. NO repitas la última frase del contexto.
5. NO menciones "lotes" ni "imágenes", escribe directo para el usuario final.

CONTEXTO PREVIO (fragmento de lo llevas escrito):
"{prev_fragment}"
"""

        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_instructions}, 
                    {"role": "user",
                     "content": "Haz una guía en base a las imágenes",
                     "images": current_group}
                ],
                options={"temperature": 0.1}, # Temperatura baja para precisión técnica
            )

            new_content = response['message']['content']

            # 3. Concatenación Segura (Evita que el texto se pegue feo)
            if full_answer:
                full_answer += "\n\n" + new_content
            else:
                full_answer = new_content

        except Exception as e:
            print(f"❌ Error en lote {batch_num}: {e}")
            # Opcional: break o continue dependiendo de qué tan crítico sea fallar un lote

    return full_answer