import io
import os
import base64
import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
import matplotlib.patches as patches
from ct.settings.config import PARTNER_CT

def image_segmentator(
        image: Image.Image, 
        eps: int, 
        min_samples: int, 
        threshold: int = 240):
    
    gray = np.array(image.convert('L'))
    mask_content = gray < threshold

    coords = np.column_stack(np.where(mask_content))

    dbscan = DBSCAN(
        eps=eps,
        min_samples=min_samples,
        n_jobs=-1
    )

    labels = dbscan.fit_predict(coords)
    bboxes = []

    for cluster_id in set(labels):
        if cluster_id == -1:  # Ignorar ruido
            continue
        
        # Coordenadas de todos los píxeles en este cluster
        cluster_coords = coords[labels == cluster_id]
        
        # Bounding box: min/max de y (filas) y x (columnas)
        y_min, x_min = cluster_coords.min(axis=0)
        y_max, x_max = cluster_coords.max(axis=0)
        
        # Agregar un pequeño padding
        padding = 10
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(image.width, x_max + padding)
        y_max = min(image.height, y_max + padding)
        
        bboxes.append({
            'bbox': (x_min, y_min, x_max, y_max),
            'cluster_id': cluster_id,
            'num_pixels': len(cluster_coords)
        })

    # Ordenar por posición vertical (top to bottom)
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
    
    for i, bbox_info in enumerate(bboxes):
        x1, y1, x2, y2 = bbox_info['bbox']

        cut = image.crop((x1, y1, x2, y2))

        output_path = os.path.join(output_dir, f"{i}.png")
        cut.save(output_path)