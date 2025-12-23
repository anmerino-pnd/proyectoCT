import io
import os
import cv2
import base64
import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
import matplotlib.patches as patches
from ct.settings.config import PARTNER_CT

# def image_segmentator(
#         image: Image.Image, 
#         eps: int, 
#         min_samples: int, 
#         threshold: int = 240):
    
#     gray = np.array(image.convert('L'))
#     mask_content = gray < threshold

#     coords = np.column_stack(np.where(mask_content))

#     dbscan = DBSCAN(
#         eps=eps,
#         min_samples=min_samples,
#         n_jobs=-1
#     )

#     labels = dbscan.fit_predict(coords)
#     bboxes = []

#     for cluster_id in set(labels):
#         if cluster_id == -1:  # Ignorar ruido
#             continue
        
#         # Coordenadas de todos los píxeles en este cluster
#         cluster_coords = coords[labels == cluster_id]
        
#         # Bounding box: min/max de y (filas) y x (columnas)
#         y_min, x_min = cluster_coords.min(axis=0)
#         y_max, x_max = cluster_coords.max(axis=0)
        
#         # Agregar un pequeño padding
#         padding = 10
#         x_min = max(0, x_min - padding)
#         y_min = max(0, y_min - padding)
#         x_max = min(image.width, x_max + padding)
#         y_max = min(image.height, y_max + padding)
        
#         bboxes.append({
#             'bbox': (x_min, y_min, x_max, y_max),
#             'cluster_id': cluster_id,
#             'num_pixels': len(cluster_coords)
#         })

#     # Ordenar por posición vertical (top to bottom)
#     bboxes.sort(key=lambda b: b['bbox'][1])
    
#     return bboxes

def image_segmentator(
        image: Image.Image, 
        kernel_size: tuple = (25, 10), # (ancho, alto) de la dilatación
        min_area: int = 100): # Área mínima para considerar un bloque
    
    # 1. Convertir PIL a OpenCV (numpy array)
    img_np = np.array(image)
    
    # Manejar canales (asegurar escala de grises)
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np

    # 2. Binarización Adaptativa (Mucho mejor que threshold fijo)
    # Invierte los colores (Texto blanco, fondo negro) para los contornos
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # 3. Operaciones Morfológicas (El truco clave)
    # "Dilatamos" lo blanco. Hacemos que las letras engorden hasta tocarse
    # y formar bloques sólidos.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    dilated = cv2.dilate(binary, kernel, iterations=1)

    # 4. Encontrar Contornos (Mucho más rápido que DBSCAN)
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    bboxes = []
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Filtrar ruido por área mínima
        if w * h < min_area:
            continue
            
        # Padding opcional
        padding = 10
        height_img, width_img = gray.shape
        
        x_min = max(0, x - padding)
        y_min = max(0, y - padding)
        x_max = min(width_img, x + w + padding)
        y_max = min(height_img, y + h + padding)

        bboxes.append({
            'bbox': (x_min, y_min, x_max, y_max),
            'cluster_id': 0, # Ya no aplica DBSCAN ID, pero mantenemos estructura
            'num_pixels': w * h
        })

    # 5. Ordenar de arriba a abajo
    bboxes.sort(key=lambda b: b['bbox'][1])

    return bboxes

def visualizer(image: Image.Image, bboxes: list):
    fig, ax = plt.subplots(1, figsize=(12,16))
    ax.imshow(image)

    colors = plt.cm.tab20(np.linspace(0, 1, len(bboxes)))

    for i, bbox_info in enumerate(bboxes):
        x1, y1, x2, y2, = bbox_info['bbox']
        width = x2 - x1
        height = y2 - y1

        rect = patches.Rectangle(
            (x1, y1), width, height,
            linewidth = 2,
            edgecolor = colors[i],
            facecolor = 'none'
        )
        ax.add_patch(rect)

        ax.text(
            x1, y1 - 5,
            f"Sección {i+1}",
            color = colors[i],
            fontsize = 10,
            fontweight = 'bold',
            bbox = dict(boxstyle = 'round, pad=0.3', facecolor='white', alpha=0.7)
        )

    ax.axis('off')
    plt.tight_layout()
    plt.show()

def image_cropper(
        image: Image.Image, 
        bboxes: list, 
        output_dir: Path = PARTNER_CT):
    
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, bbox_info in enumerate(bboxes):
        x1, y1, x2, y2 = bbox_info['bbox']

        cut = image.crop((x1, y1, x2, y2))

        output_path = os.path.join(output_dir, f"{i}.png")
        cut.save(output_path)