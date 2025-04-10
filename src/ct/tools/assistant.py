from ct.types import CallMetadata, Text, Chunks, Question
from abc import ABC, abstractmethod
from typing import Tuple

class Assistant(ABC):
    @abstractmethod
    def answer(self, q : Question) -> Tuple[Text, CallMetadata]:
        pass

    def history_system(self) -> str:
        return (
            "Dada una historia de chat y la última pregunta del usuario "
            "que podría hacer referencia al contexto en la historia de chat, "
            "formula una pregunta independiente que pueda ser entendida "
            "sin la historia de chat. NO respondas la pregunta, "
            "solo reformúlala si es necesario y, en caso contrario, devuélvela tal como está." 
        )
    
    def answer_template(self) -> str:
        tpl = (
        """
        Basate solo en los siguientes fragmentos de contexto para responder la consulta del usuario.  

        El usuario pertenece a la listaPrecio {listaPrecio}, así que usa exclusivamente los precios de esta lista. 
        No menciones la lista de precios en la respuesta, solo proporciona el precio final en formato de precio (por ejemplo, $1,000.00).  

        Si hay productos en oferta, menciónalos primero. 
        Si no hay promociones, ofrece los productos normales con su precio correcto.  
        Si el usuario pregunta por un producto específico, verifica si está en promoción y notifícalo.  

        Para que un producto se considere en promoción debe tener las variables de precio_oferta, descuento, EnCompraDE y Unidades.
        Luego, estas deben cumplir las siguientes condiciones:

        1. Si el producto tiene un precio_oferta mayor a 0.0:  
            - Usa este valor como el precio final y ofrécelo al usuario. 

        2. Si el precio_oferta es 0, pero el descuento es mayor a 0.0%:  
            - Aplica el descuento al precio que se encuentra en lista_precios y toma el precio correspondiente a la listaPrecio {listaPrecio}.  
            - Muestra ese precio tachado y el nuevo precio con el descuento aplicado.  

        3. Si el precio_oferta y el descuento son 0.0, pero la variable EnCompraDE es mayor a 0 y Unidades es mayor a 0:  
            - Menciona que hay una promoción especial al comprar cierta cantidad.  
            - Usa un tono sutil, por ejemplo: "En compra de 'X' productos, recibirás 'Y' unidades gratis."  

        Revisa también:  
            - La variable limitadoA para indicar si la disponibilidad es limitada.  
            - La variable fecha_fin para aclarar la vigencia de la promoción.  

        Formato de respuesta, SIEMPRE:  
        - Para cada producto que ofrezcas:
            * Toma la 'clave' del producto
            * Resalta el nombre poniendo su hipervinculo https://ctonline.mx/buscar/productos?b=clave
        - Presenta la información de manera clara
        - Los detalles y precios puntualizados y estructurados 
        - Espacios entre productos.         
        - Evita explicaciones largas o innecesarias.  

        Siempre aclara al final que la disponibilidad y los precios pueden cambiar.  

        Contexto: {context}  
        """
            )
    
        return tpl

