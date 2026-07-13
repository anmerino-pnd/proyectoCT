import io
import base64
import numpy as np
from PIL import Image
from io import BytesIO
from ct.settings.config import DATA_DIR

def remove_whitespace(img_data : bytes, box : tuple, threshold : int):
    image_buffer = io.BytesIO(img_data)
    Image.MAX_IMAGE_PIXELS = None
    image = Image.open(image_buffer)

    numpy_array = np.array(image.crop(box)) # (0, 540, 1904, 2650)

    filas_no_blancas = np.any(numpy_array < threshold, axis = (1, 2)) # 240
    numpy_array = numpy_array[filas_no_blancas]

    columnas_no_blancas = np.any(numpy_array < threshold, axis = (0, 2))
    numpy_array = numpy_array[:, columnas_no_blancas]

    return Image.fromarray(numpy_array)