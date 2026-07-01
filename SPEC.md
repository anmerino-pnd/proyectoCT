# SPEC.md — Rediseño del chatbot "CT Ayuda"

## Propósito

Rediseñar el asistente conversacional de CT Internacional para que se sienta como una **herramienta de trabajo** (copiloto de compras/procurement) y no como un buscador de tienda. El usuario típico es un revendedor o comprador de TI que necesita tomar decisiones de compra rápido: qué hay en existencia, a qué precio, y cuál conviene.

Este documento describe **solo cambios de interfaz (frontend)**. El motor del chatbot (el agente con herramientas descrito en `prompt.py`) no cambia. La UI ya recibe del agente dos bloques estructurados que debemos aprovechar:

- ` ```ct-products ` → arreglo JSON de productos (se renderiza como tarjetas)
- ` ```ct-suggestions ` → arreglo JSON de strings (se renderiza como chips tocables)

**Regla de oro:** ningún cambio debe agregar latencia ni nuevas llamadas de datos al flujo. Todo lo aquí descrito se construye con datos que la UI ya tiene.

---

## 1. Color e identidad

CT usa **azul y rojo**. En esta interfaz **el azul lidera** (transmite confianza y calma, ideal para una herramienta de trabajo).

- **Azul** (`#185FA5` fuerte, `#378ADD` medio, `#E6F1FB` fondo claro): color principal de precios, botones de acción, encabezado, foco.
- **Rojo**: reservado **únicamente** para (a) el logotipo/marca en el encabezado y (b) acciones destructivas (confirmación de "eliminar historial", que ya usa rojo y se queda igual). No usar rojo en ningún otro elemento de la interfaz.
- El ícono rojo genérico del encabezado actual debe alinearse a la identidad; mantener la marca pero que no haga sentir el asistente como un producto aparte.

### Paleta de estados (existencias)

| Estado | Uso | Fondo | Texto |
|---|---|---|---|
| En tu sucursal | disponible ya (mejor caso) | `#EAF3DE` | `#27500A` |
| En otras sucursales | disponible por traslado | `#E6F1FB` | `#0C447C` |
| Sobre pedido | hay que esperar | `#FAEEDA` | `#633806` |
| Promoción | badge de promo | `#FAECE7` | `#712B13` (coral, NO rojo de marca) |

Radio de esquinas: `12px` en tarjetas, `8px` en controles/pills interactivas, `999px` en pills de estado. Bordes finos (0.5px). Sin gradientes ni sombras pesadas. Debe verse consistente con el portal (aireado, con buen espaciado).

---

## 2. Tarjeta de producto (rediseño)

Es el elemento más importante. Debe ser una **herramienta de decisión**, no un mosaico de catálogo.

Datos de entrada (del bloque `ct-products`, ya existente):
`clave`, `marca`, `modelo`, `imagen_url`, `url`, `precio` (número), `moneda`, `en_su_sucursal` (número), `en_otras_sucursales` (número), `en_promocion` (bool).

### Contenido y jerarquía de cada tarjeta

1. **Miniatura** del producto (usar `imagen_url`; si viene vacío, mostrar un placeholder con ícono, no romper el layout).
2. **Título = `clave`** (Clave CT) en peso medio. Es el título visible obligatorio.
3. **Subtítulo** = `marca` · `modelo` (o el identificador que venga), en texto secundario.
4. **Badge de promoción** (solo si `en_promocion === true`): pill coral con ícono de etiqueta y texto "Promoción".
5. **Pill de existencias** — una sola pill, con color según la mejor disponibilidad:
   - si `en_su_sucursal > 0` → verde, texto "N en tu sucursal"
   - si no, y `en_otras_sucursales > 0` → azul, texto "N en otras sucursales"
   - si ambos son 0 → ámbar, texto "Sobre pedido"
   - Nunca usar la palabra "red". Usar "tu sucursal" / "otras sucursales".
6. **Precio**: `$X.XX {moneda}` grande, en azul (`#185FA5`). Debajo, en texto tenue, el **equivalente aproximado en MXN** cuando la moneda sea USD: "≈ $XXX.XX MXN". Este cálculo usa el tipo de cambio que la UI ya conoce/recibe (mismo dato del portal, ej. "USD 1.00 = 17.34 MXN"). Si la moneda ya es MXN, no mostrar segunda línea.
7. **Acciones** (pie de tarjeta):
   - Botón **"Comparar"** (con ícono de comparación) → agrega/quita la tarjeta de la selección de comparación (ver sección 3).
   - Botón **"Abrir"** (con ícono de enlace externo) → abre `url` del producto en nueva pestaña.
   - Toda la tarjeta puede ser clickeable hacia `url` también, pero los botones tienen prioridad de clic.

### Leyenda de colores
Mostrar una pequeña leyenda de los tres estados (verde / azul / ámbar) una sola vez por grupo de resultados, no en cada tarjeta.

---

## 3. Vista de comparación (función estrella)

Permite comparar 2–3 (máximo 4) productos lado a lado. Es lo que el portal no hace bien y lo que un comprador hace todo el día.

### Cómo se activa
- **Ruta principal (tocar):** el usuario pulsa "Comparar" en las tarjetas. Al haber ≥2 seleccionadas, aparece una **barra flotante inferior** dentro del panel con: "Comparar (N)" y un botón para limpiar la selección. Al pulsar "Comparar (N)" se abre la vista.
- **Ruta secundaria (escribir):** si el usuario escribe algo como "compara las dos primeras", el agente devuelve el bloque de productos correspondiente y la UI puede mostrarlos directamente en la vista de comparación. Soportar ambas rutas.

### Layout
- Tarjetas en columnas (grid `repeat(auto-fit, minmax(0,1fr))`), una por producto.
- Cada columna muestra: `clave`, `marca`, precio USD + equivalente MXN, pill(s) de existencias, y estado de promoción (badge coral "En promoción" o texto tenue "Sin promoción").
- **Resaltar la mejor opción**: la tarjeta recomendada lleva `border: 2px solid #185FA5` (única excepción al borde de 0.5px) y una etiqueta "Recomendado" en pill azul. Criterio de recomendación por defecto: **más barata que esté en existencia** (en tu sucursal u otras); si empatan, la que esté en promoción. Este criterio se puede ajustar, pero debe favorecer disponibilidad real sobre solo precio.
- La vista de comparación vive preferentemente en el **modo expandido** (ver sección 4), donde hay ancho para 3 columnas cómodas.
- Debajo de la comparación, mostrar chips de seguimiento relevantes (sección 5), por ejemplo: "La más barata en existencia", "Precio total en MXN", "¿Cuál conviene para N nodos?".

---

## 4. Panel vs. modo expandido ("work mode")

Hoy el widget es una barra lateral que se abre sobre la página, con un botón de expandir. Mantener eso y darle propósito real:

- **Panel (por defecto, angosto ~380px):** conversación cómoda. Las tarjetas se apilan verticalmente. Ideal para preguntar y ojear resultados.
- **Expandido (ancho):** "modo trabajo". Aquí las tarjetas pueden acomodarse en grid y la **vista de comparación** se despliega en 2–3 columnas. El botón de expandir ya existe; asegurar que el layout de tarjetas y comparación sea responsivo entre ambos anchos.

---

## 5. Chips de sugerencia (seguimiento)

Vienen del bloque `ct-suggestions` (ya existente). Son el "volante" de la conversación: cada chip mapea a algo que el agente sí puede responder.

- Estilizarlos como **botones de primera clase** (no como tags grises): pill con borde fino, texto en azul, esquinas redondeadas, hover sutil. Consistentes con el estilo "Acciones rápidas" del portal.
- Mantenerlos siempre visibles al final de las respuestas con productos o info útil.
- Al tocar un chip, se envía ese texto como mensaje del usuario (comportamiento actual).

---

## 6. Estado de bienvenida

Mensaje **general y cálido, sin personalización** (no requiere nombre ni sucursal, cero llamadas extra ni latencia):

> ¡Hola! 👋 Soy tu asistente de CT. Puedo buscar productos con precio y existencias, comparar opciones, revisar el estatus de tu pedido y más. ¿Con qué te ayudo hoy?

Debajo, los **cuatro botones de inicio** actuales (se conservan, cada uno mapea a una herramienta del agente):
- Laptops en promoción
- Cotizar una impresora
- Estatus de mi pedido
- Nuestras sucursales

Estilizar estos cuatro con la misma cara de tarjeta/acción del resto (íconos suaves, esquinas 12px, consistente con el portal).

> Nota: la personalización real (nombre/sucursal) NO se hace en el saludo. El contexto de sucursal aparece donde importa: en las pills "en tu sucursal" de las tarjetas, con datos que la UI ya tiene.

---

## 7. Encabezado y acción de eliminar

- Encabezado: título "CT Ayuda" + indicador "Asistente en línea". Marca alineada a la identidad (azul liderando; rojo solo en el logo).
- La papelera (eliminar historial) hoy está a un toque del cierre; es una acción pesada e irreversible. **Moverla a un pequeño menú** (ícono de tres puntos u overflow).
- En su lugar, exponer **"Nueva conversación"** como la acción cotidiana y amable (visible/accesible directamente).
- La confirmación de borrado (modal "¿Estás seguro…?") se conserva tal cual, con su botón rojo "Sí, Eliminar". Ese es el único lugar de la interfaz, junto con el logo, donde el rojo es correcto.

---

## 8. Percepción de velocidad

El agente responde rápido; la UI debe **hacer sentir** esa velocidad.

- Mostrar un estado de carga ligero mientras el agente trabaja, p. ej. "Buscando productos…" con un indicador sutil.
- Hacer streaming de la respuesta de texto conforme llega (si el backend ya lo permite).
- Objetivo: que nunca parezca que "no pasa nada". El estado de carga debe verse vivo pero discreto.

---

## 9. Footer (obligatorio)

Conservar el descargo legal actual, sin cambios de texto:

> Este chatbot puede cometer errores. Compruebe la información importante con un asesor.

Solo asegurar que sea legible en el nuevo esquema de color (texto tenue sobre fondo claro) y que no lo tape la barra flotante de comparación.

---

## Resumen de entregables

1. Tarjeta de producto rediseñada (miniatura, clave como título, badge de promo, pill de existencias con color, precio USD + MXN, botones Comparar/Abrir).
2. Selección para comparar + barra flotante "Comparar (N)".
3. Vista de comparación lado a lado con opción recomendada resaltada.
4. Layout responsivo panel ↔ expandido (comparación en modo expandido).
5. Chips de sugerencia estilizados como botones de primera clase.
6. Estado de bienvenida general + 4 starters estilizados.
7. Encabezado con marca alineada; papelera movida a menú; "Nueva conversación" expuesta.
8. Estado de carga + streaming para percepción de velocidad.
9. Footer legal conservado y legible.

## Fuera de alcance
- Cambios al agente o a sus herramientas (`prompt.py`).
- Nuevas llamadas de datos o personalización que agregue latencia.
- Reservar/apartar productos, cotizaciones por correo/WhatsApp, agendar, hablar con humano: el agente no las soporta, la UI no debe ofrecerlas.
