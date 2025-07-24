from datetime import datetime
from pydantic import BaseModel

class SalesInput(BaseModel):
    precio: float
    descuento: float
    moneda: str
    precio_oferta: float
    EnCompraDe: float
    Unidades: float
    fecha_fin: str
    limitadoA: int

def sales_rules_tool(
                     precio: float,
                     descuento: float,
                     moneda: str,
                     precio_oferta: float,
                     EnCompraDe: float,
                     Unidades: float,
                     fecha_fin: str,
                     limitadoA: int
                     ) -> str:
    precio_final = precio
    mensaje = []

    if precio_oferta > 0:
        if precio_oferta > precio:
            return f"Cambio de precio base: ${precio_oferta} {moneda}, ya no se considera promoción"
        else:    
            precio_final = precio_oferta
            mensaje.append(f"${precio_final:.2f} {moneda}")
    elif descuento > 0:
        precio_final = round(precio * (1 - descuento / 100), 2)
        mensaje.append(f"~${precio:.2f} {moneda}~ ${precio_final:.2f} {moneda}")
        mensaje.append(f"{descuento:.0f}% de descuento.")
    elif EnCompraDe > 0 and Unidades > 0:
        mensaje.append(f"En compra de {EnCompraDe}, recibe {Unidades} gratis.")
    
    if limitadoA > 0:
        mensaje.append(f"Limitado a {limitadoA}")
    if fecha_fin:
        mensaje.append(f"Vigente hasta el {fecha_fin}.")

    return "\n".join(mensaje)
