import os
import ollama

def _get_paragraphs(text: str, n_chars: int):
    """
    Obtiene los últimos párrafos hasta alcanzar aproximadamente target_chars.
    Siempre devuelve párrafos completos.
    """
    if not text: 
        return ""
    
    paragraphs = text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    result = []
    char_count = 0

    for paragraph in  reversed(paragraphs):
        result.insert(0, paragraph)
        char_count += len(paragraph)
        if char_count >= n_chars:
            break
    
    return '\n\n'.join(result)

def guide_creation(folder_path: str, model: str = "gemma3:27b", context_size: int = 500):
    """
    Genera tutorial con ventana deslizante de contexto.
    
    Args:
        context_size: Caracteres aproximados de contexto a incluir (default: 2000)
    """
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

        if full_answer:
            prev_fragment = _get_paragraphs(full_answer, n_chars=context_size)
            print(f"  📝 Contexto: {len(prev_fragment)} chars ({len(prev_fragment.split())} palabras)")
        else:
            prev_fragment =  "Ninguno (este es el inicio)"

        current_group = image_paths[i:i+3]

        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": f"""
Eres un asistente que redacta tutoriales claros y completos para la empresa CT Internacional.

INSTRUCCIONES:             
- Explica de forma clara para personas sin experiencia técnica.
- No omitas información importante visible en las imágenes.
- No inventes información que no aparezca en las imágenes.
- Continúa naturalmente desde donde quedó el fragmento anterior.
- NO menciones "lotes", "batches", ni fragmentos, ni imágenes.

FRAGMENTO ANTERIOR DEL TUTORIAL:
{prev_fragment}

Lote {batch_num}/{total_batches}
    """}, 
                {"role": "user",
                 "content": "Redacta un tutorial con las imágenes proporcionadas",
                 "images": current_group}
            ],
            options={"temperature": 0},
        )

        full_answer += response['message']['content']

    return full_answer
