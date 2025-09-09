import re
import os 
import fitz
from ct.settings.config import BASE_DIR


def process_pdfs_to_images(base_knowledge_path, output_base_path=f"{BASE_DIR}/datos", force_reprocess=False):
    """
    Procesa archivos PDF de un directorio y los convierte en imágenes JPEG.

    Args:
        base_knowledge_path (str): La ruta del directorio que contiene los archivos PDF.
        output_base_path (str): La ruta base donde se crearán las carpetas de salida.
        force_reprocess (bool): Si es True, procesa los PDFs incluso si la carpeta de destino
                                 ya existe y tiene contenido. Si es False, omite los
                                 documentos ya procesados.
    """
    if not os.path.exists(base_knowledge_path):
        print(f"Error: La ruta de conocimiento base no existe: {base_knowledge_path}")
        return

    for filename in os.listdir(base_knowledge_path):
        if not filename.endswith('.pdf'):
            continue
        
        # Elimina la extensión .pdf para el nombre de la carpeta
        folder_name = re.sub(r'\.pdf$', '', filename)
        folder_path = os.path.join(output_base_path, folder_name)

        # Verifica si la carpeta ya existe y si tiene contenido
        if os.path.exists(folder_path) and len(os.listdir(folder_path)) > 0 and not force_reprocess:
            print(f"Skipping '{filename}': Directory '{folder_path}' already exists and contains files.")
            continue
        
        # Crea la carpeta si no existe
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Created directory: {folder_path}")
        
        pdf_path = os.path.join(base_knowledge_path, filename)
        try:
            pdf_documents = fitz.open(pdf_path)
            
            image_paths = []
            for page_num in range(len(pdf_documents)):
                page = pdf_documents.load_page(page_num)
                pix = page.get_pixmap(dpi=780)

                image_path = os.path.join(folder_path, f"{page_num + 1}.jpg")
                pix.save(image_path)
                image_paths.append(image_path)
            
            pdf_documents.close()
            print(f"Successfully processed '{filename}'.")
            
        except Exception as e:
            print(f"Error processing '{filename}': {e}")

# Ejemplo de uso
# Nota: Tendrías que definir BASE_KNOWLEDGE y otros paths en tu entorno
# from ct.settings.config import BASE_KNOWLEDGE
# process_pdfs_to_images(BASE_KNOWLEDGE, force_reprocess=True)
