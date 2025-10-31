import os
import json
import ollama
from ct.settings.config import BASE_KNOWLEDGE

def guide_creation(folder_path: str, model: str = "gemma3:27b"):
    image_paths = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    image_paths.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

    full_answer = ''
    total_batches = (len(image_paths) + 2) // 3

    for batch_num, i in enumerate(range(0, len(image_paths), 3), start=1):
        print(f"Lote {batch_num} de {total_batches}")
        prev_fragment = full_answer[-1] if full_answer else "Ninguno (este es el inicio)"
        current_group = image_paths[i:i+3]

        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": f"""
    Eres un asistente que redacta tutoriales claros y completos para la empresa CT Internacional.

    - Explica de forma clara, como si cualquier persona sin experiencia pudiera entender.
    - No omitas información importante que se muestre en las imágenes.
    - No inventes ni agregues cosas que no estén en las imágenes.
    - No concluyas todavía el tutorial hasta recibir todas las imágenes.

    Fragmento anterior del tutorial:
    {prev_fragment}

    Ahora continúa el tutorial con el siguiente bloque de imágenes.
    Este es el lote {batch_num} de {total_batches}.

    NO menciones los lotes ni preguntas o concluyas al terminar un lote, solo espera internamente sin decirlo.
    """}, 
                {"role": "user",
                 "content": "Genera la siguiente parte del tutorial con base en estas imágenes:",
                 "images": current_group}
            ],
            options={"temperature": 0},
        )

        full_answer += response['message']['content']

    # Normalizar nombre del archivo
    nombre = os.path.basename(os.path.normpath(folder_path)).strip().replace(" ", "_")
    os.makedirs(BASE_KNOWLEDGE, exist_ok=True)

    with open(os.path.join(BASE_KNOWLEDGE, f"{nombre}.json"), "w", encoding="utf-8") as f:
        json.dump(full_answer, f, ensure_ascii=False, indent=2)

    return full_answer
