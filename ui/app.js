
let userId = null;
let userKey = null;
let API_BASE = null;
let ctaiAbort = null; // AbortController de la respuesta en curso (para el botón detener)
let CTAI_FX = null;   // tipo de cambio USD→MXN (del portal); null si no se conoce
let ctaiLastUserMsg = ""; // último mensaje del usuario (heurística "compara…")

// Mensaje de bienvenida general y cálido (sin personalización, cero llamadas extra).
const CTAI_WELCOME =
    "¡Hola! 👋 Soy tu asistente de CT. Puedo buscar productos con precio y existencias, " +
    "comparar opciones, revisar el estatus de tu pedido y más. ¿Con qué te ayudo hoy?";

const CTAI_MAX_COMPARE = 4; // tope de productos comparables
// Selección de comparación: clave -> objeto producto.
const ctaiCompare = new Map();

// Opciones iniciales (tiles tipo "Acciones rápidas") que se muestran al abrir el chat.
// icon = SVG inline (stroke currentColor); tone = clase de color pastel; query = consulta enviada.
const CTAI_STARTERS = [
    {
        label: "Laptops en promoción",
        query: "¿Qué laptops tienen en promoción?",
        tone: "blue",
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M2 20h20"></path></svg>'
    },
    {
        label: "Cotizar una impresora",
        query: "Quiero cotizar una impresora",
        tone: "purple",
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V2h12v7"></path><path d="M6 18H4a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8" rx="1"></rect></svg>'
    },
    {
        label: "Estatus de mi pedido",
        query: "¿Cómo va el estatus de mi pedido?",
        tone: "amber",
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path><path d="m3.3 7 8.7 5 8.7-5"></path><path d="M12 22V12"></path></svg>'
    },
    {
        label: "Nuestras sucursales",
        query: "¿Dónde están sus sucursales?",
        tone: "green",
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"></path><circle cx="12" cy="10" r="3"></circle></svg>'
    }
];

// Alterna el botón de enviar entre "enviar" y "detener"
function ctaiSetSending(isSending) {
    const btn = document.getElementById("ctai-send-button");
    if (!btn) return;
    btn.classList.toggle("is-stop", isSending);
    btn.setAttribute("aria-label", isSending ? "Detener respuesta" : "Enviar mensaje");
}

// Aborta la respuesta en curso
function stopGeneration() {
    if (ctaiAbort) {
        ctaiAbort.abort();
        ctaiAbort = null;
    }
}

// Íconos del botón expandir/contraer
const CTAI_ICON_EXPAND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"></path><path d="M9 21H3v-6"></path><path d="M21 3l-7 7"></path><path d="M3 21l7-7"></path></svg>';
const CTAI_ICON_COLLAPSE =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 14h6v6"></path><path d="M20 10h-6V4"></path><path d="M14 10l7-7"></path><path d="M3 21l7-7"></path></svg>';

// Telemetría de UI (fire-and-forget). Nunca debe romper la UX.
function ctaiTrack(event, meta) {
    try {
        if (!API_BASE || !userId) return;
        fetch(`${API_BASE}/ui-event`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event: event, user_id: userId, meta: meta || {} }),
            keepalive: true
        }).catch(() => {});
    } catch (e) {}
}
window.ctaiTrack = ctaiTrack;

function setupAutoResizeTextarea() {
    const textarea = document.getElementById('ctai-user-input');
    if (!textarea) return;
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    textarea.style.paddingRight = "40px";
}

// ---------- Utilidades de render ----------
// "Pegado al fondo": solo auto-desplazamos si el usuario está cerca del final.
// Si subió a leer, no lo regresamos a la fuerza y mostramos el botón de bajar.
let ctaiStick = true;
let ctaiAdjusting = false; // true mientras re-anclamos por expandir/contraer
const CTAI_STICK_THRESHOLD = 120;

function ctaiNearBottom(c) {
    return (c.scrollHeight - c.scrollTop - c.clientHeight) <= CTAI_STICK_THRESHOLD;
}

function ctaiUpdateScrollBtn() {
    const c = document.getElementById("ctai-messages-container");
    const btn = document.getElementById("ctai-scroll-bottom");
    if (!c || !btn) return;
    btn.classList.toggle("is-visible", !ctaiNearBottom(c));
}

function ctaiScrollDown() {
    const c = document.getElementById("ctai-messages-container");
    if (!c) return;
    if (ctaiStick) c.scrollTop = c.scrollHeight;  // respeta si el usuario subió
    ctaiUpdateScrollBtn();
}

// Fuerza el scroll al final (p. ej. al abrir el chat). Doble rAF para esperar a que
// el layout del markdown/historial termine de asentar antes de medir scrollHeight.
function ctaiForceBottom() {
    const c = document.getElementById("ctai-messages-container");
    if (!c) return;
    ctaiStick = true;
    requestAnimationFrame(() => {
        c.scrollTop = c.scrollHeight;
        requestAnimationFrame(() => {
            c.scrollTop = c.scrollHeight;
            ctaiUpdateScrollBtn();
        });
    });
}

function ctaiEscape(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function ctaiSafeUrl(u) {
    const s = String(u || "").trim();
    return /^https?:\/\//i.test(s) ? s : "";
}

function ctaiMoneyStr(n) {
    return "$" + Number(n).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ctaiFormatPrice(precio, moneda) {
    const n = Number(precio);
    if (!isFinite(n) || n <= 0) return "";
    const cur = (moneda || "MXN").toString().toUpperCase();
    return ctaiMoneyStr(n) + " " + cur;
}

// Devuelve { main, mxn } para el precio de un producto.
//  - main: "$X.XX {moneda}"
//  - mxn : "≈ $Y.YY MXN" cuando la moneda es USD y conocemos el tipo de cambio; "" si no aplica.
function ctaiPriceParts(precio, moneda) {
    const n = Number(precio);
    if (!isFinite(n) || n <= 0) return { main: "", mxn: "" };
    const cur = (moneda || "MXN").toString().toUpperCase();
    const main = ctaiMoneyStr(n) + " " + cur;
    let mxn = "";
    if (cur === "USD" && CTAI_FX) mxn = "≈ " + ctaiMoneyStr(n * CTAI_FX) + " MXN";
    return { main, mxn };
}

function ctaiNum(v) {
    const n = Number(v);
    return isFinite(n) ? n : 0;
}

function ctaiIsPromo(p) {
    return p && (p.en_promocion === true || p.en_promocion === "Sí" || p.en_promocion === "si" || p.en_promocion === "Si");
}

// Precio normalizado a MXN para comparar de forma justa (usa FX si la moneda es USD).
function ctaiPriceMXN(p) {
    const n = Number(p && p.precio);
    if (!isFinite(n) || n <= 0) return Infinity;
    const cur = (p.moneda || "MXN").toString().toUpperCase();
    return (cur === "USD" && CTAI_FX) ? n * CTAI_FX : n;
}

// ---------- Parser in-band INCREMENTAL ----------
// Extrae los bloques ```ct-products / ```ct-suggestions tolerando que aún estén
// llegando por el stream: devuelve TODOS los elementos ya completos (objetos/strings
// cerrados) aunque el arreglo o la valla de cierre todavía no hayan llegado.

// Escanea un cuerpo que empieza en '[' y devuelve los elementos top-level YA completos.
function ctaiScanArray(body) {
    const items = [];
    const n = body.length;
    let i = 0;
    if (body[i] === "[") i++;
    while (i < n) {
        while (i < n && /[\s,]/.test(body[i])) i++;       // saltar espacios y comas
        if (i >= n || body[i] === "]") break;
        const start = i;
        const ch = body[i];
        if (ch === "{") {                                  // objeto (producto)
            let depth = 0, inStr = false, esc = false, done = false;
            for (; i < n; i++) {
                const c = body[i];
                if (inStr) {
                    if (esc) esc = false;
                    else if (c === "\\") esc = true;
                    else if (c === '"') inStr = false;
                } else if (c === '"') inStr = true;
                else if (c === "{") depth++;
                else if (c === "}") { depth--; if (depth === 0) { i++; done = true; break; } }
            }
            if (!done) break;                              // objeto incompleto: esperar más
            try { items.push(JSON.parse(body.slice(start, i))); } catch (e) { /* omitir */ }
        } else if (ch === '"') {                            // string (sugerencia)
            let esc = false, done = false;
            for (i++; i < n; i++) {
                const c = body[i];
                if (esc) esc = false;
                else if (c === "\\") esc = true;
                else if (c === '"') { i++; done = true; break; }
            }
            if (!done) break;                              // string incompleto
            try { items.push(JSON.parse(body.slice(start, i))); } catch (e) { /* omitir */ }
        } else {
            break;                                         // token inesperado
        }
    }
    return items;
}

// Elementos completos del bloque `kind` ("products" | "suggestions").
function ctaiExtractItems(raw, kind) {
    const fence = "```ct-" + kind;
    const at = raw.indexOf(fence);
    if (at === -1) return [];
    const rest = raw.slice(at + fence.length);
    const open = rest.indexOf("[");
    if (open === -1) return [];
    const closeFence = rest.indexOf("```", open);
    const end = closeFence === -1 ? rest.length : closeFence;
    return ctaiScanArray(rest.slice(open, end));
}

// Quita del texto visible las regiones de los bloques (completas o en curso).
function ctaiStripBlocks(text) {
    return text
        .replace(/```ct-(?:products|suggestions)[\s\S]*?```/g, "")
        .replace(/```ct-(?:products|suggestions)[\s\S]*$/, "");
}

function ctaiParseStructured(raw) {
    const r = String(raw || "");
    return {
        text: ctaiStripBlocks(r).trim(),
        products: ctaiExtractItems(r, "products"),
        suggestions: ctaiExtractItems(r, "suggestions")
    };
}

// ---------- Íconos SVG (stroke currentColor) ----------
const CTAI_SVG_PIN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"></path><circle cx="12" cy="10" r="3"></circle></svg>';
const CTAI_SVG_BOX =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path><path d="m3.3 7 8.7 5 8.7-5"></path><path d="M12 22V12"></path></svg>';
const CTAI_SVG_CLOCK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>';
const CTAI_SVG_TAG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.5 2H20a2 2 0 0 1 2 2v7.5a2 2 0 0 1-.6 1.4l-8.5 8.5a2 2 0 0 1-2.8 0l-6.5-6.5a2 2 0 0 1 0-2.8l8.5-8.5A2 2 0 0 1 12.5 2Z"></path><circle cx="17" cy="7" r="1.2"></circle></svg>';
const CTAI_SVG_COMPARE =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h4"></path><path d="M3 12h9"></path><path d="M3 18h14"></path><path d="M18 4v6"></path><path d="m15 7 3-3 3 3"></path></svg>';
const CTAI_SVG_EXTERNAL =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path></svg>';

// Devuelve la mejor disponibilidad como { cls, icon, text } para una sola pill.
function ctaiStockPill(p) {
    if (ctaiNum(p.en_su_sucursal) > 0)
        return { cls: "sucursal", icon: CTAI_SVG_PIN, text: ctaiNum(p.en_su_sucursal) + " en tu sucursal" };
    if (ctaiNum(p.en_otras_sucursales) > 0)
        return { cls: "otras", icon: CTAI_SVG_BOX, text: ctaiNum(p.en_otras_sucursales) + " en otras sucursales" };
    return { cls: "pedido", icon: CTAI_SVG_CLOCK, text: "Sobre pedido" };
}

function ctaiPillHTML(pill) {
    return '<span class="ctai-pill ' + pill.cls + '">' + pill.icon + ctaiEscape(pill.text) + '</span>';
}

// Construye el elemento DOM de una tarjeta de producto (herramienta de decisión).
function ctaiBuildProductCard(p) {
    const url = ctaiSafeUrl(p.url);
    const img = ctaiSafeUrl(p.imagen_url);
    const clave = p.clave || p.modelo || "Producto";

    const card = document.createElement("div");
    card.className = "ctai-product-card";
    if (clave) card.dataset.clave = clave;
    if (url) card.dataset.url = url;
    if (ctaiCompare.has(clave)) card.classList.add("is-selected");

    const title = ctaiEscape(clave);                                        // título = Clave CT
    const subtitle = ctaiEscape([p.marca, p.modelo].filter(Boolean).join(" · ").trim());
    const price = ctaiPriceParts(p.precio, p.moneda);
    const pill = ctaiStockPill(p);
    const promo = ctaiIsPromo(p)
        ? '<span class="ctai-pill promo">' + CTAI_SVG_TAG + 'Promoción</span>' : '';
    const compareOn = ctaiCompare.has(clave);

    card.innerHTML =
        '<div class="ctai-card-top">' +
            '<div class="ctai-card-img' + (img ? '' : ' is-empty') + '">' +
                (img ? '<img src="' + ctaiEscape(img) + '" alt="' + title + '" loading="lazy">' : '') +
            '</div>' +
            '<div class="ctai-card-body">' +
                (promo ? '<div class="ctai-card-badges">' + promo + '</div>' : '') +
                '<div class="ctai-card-title">' + title + '</div>' +
                (subtitle ? '<div class="ctai-card-sub">' + subtitle + '</div>' : '') +
                '<div class="ctai-card-stock">' + ctaiPillHTML(pill) + '</div>' +
                (price.main
                    ? '<div class="ctai-card-priceblock">' +
                        '<span class="ctai-card-price">' + ctaiEscape(price.main) + '</span>' +
                        (price.mxn ? '<span class="ctai-card-mxn">' + ctaiEscape(price.mxn) + '</span>' : '') +
                      '</div>'
                    : '') +
            '</div>' +
        '</div>' +
        '<div class="ctai-card-actions">' +
            '<button type="button" class="ctai-card-btn compare' + (compareOn ? ' is-on' : '') + '">' +
                CTAI_SVG_COMPARE + '<span>' + (compareOn ? 'Quitar' : 'Comparar') + '</span>' +
            '</button>' +
            (url
                ? '<a class="ctai-card-btn open" href="' + ctaiEscape(url) + '" target="_blank" rel="noopener noreferrer">' +
                    CTAI_SVG_EXTERNAL + '<span>Abrir</span></a>'
                : '') +
        '</div>';

    // "Comparar" tiene prioridad de clic: no abre la url.
    const compareBtn = card.querySelector(".ctai-card-btn.compare");
    if (compareBtn) {
        compareBtn.addEventListener("click", function(ev) {
            ev.stopPropagation();
            ev.preventDefault();
            ctaiToggleCompare(p);
        });
    }
    // "Abrir" (los botones tienen prioridad; no propagamos al click de la tarjeta).
    const openBtn = card.querySelector(".ctai-card-btn.open");
    if (openBtn) {
        openBtn.addEventListener("click", function(ev) {
            ev.stopPropagation();
            ctaiTrack("product_click", { clave: clave, url: url || "" });
        });
    }
    // Toda la tarjeta es clickeable hacia la url (los botones tienen prioridad).
    if (url) {
        card.addEventListener("click", function() {
            ctaiTrack("product_click", { clave: clave, url: url });
            window.open(url, "_blank", "noopener,noreferrer");
        });
    }
    return card;
}

// Render INCREMENTAL: agrega solo las tarjetas nuevas (1 a 1) sin reconstruir las ya mostradas.
function ctaiRenderProducts(el, products) {
    if (!el) return;
    products = products || [];
    const rendered = parseInt(el.dataset.count || "0", 10);
    if (products.length <= rendered) return;               // nada nuevo
    if (products.length > 0) el.className = "bot-products ctai-products ctai-products--cards";
    for (let idx = rendered; idx < products.length; idx++) {
        const card = ctaiBuildProductCard(products[idx]);
        card.style.animationDelay = ((idx - rendered) * 0.07) + "s";   // cascada suave
        el.appendChild(card);
    }
    el.dataset.count = String(products.length);
    ctaiUpdateCompareBar();
}

// Render INCREMENTAL de chips de sugerencia (también 1 a 1).
function ctaiRenderChips(el, list) {
    if (!el) return;
    const arr = (list || []).map(q => String(q || "").trim()).filter(Boolean).slice(0, 4);
    const rendered = parseInt(el.dataset.count || "0", 10);
    if (arr.length <= rendered) return;
    for (let idx = rendered; idx < arr.length; idx++) {
        const text = arr[idx];
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "ctai-chip";
        chip.textContent = text;
        chip.style.animationDelay = ((idx - rendered) * 0.07) + "s";
        chip.addEventListener("click", () => sendMessage(text));
        el.appendChild(chip);
    }
    el.dataset.count = String(arr.length);
}

// ---------- Comparación de productos ----------

// Refleja el estado de selección en TODAS las tarjetas que compartan la misma clave.
function ctaiSyncCardsForClave(clave) {
    const on = ctaiCompare.has(clave);
    const cards = document.querySelectorAll('.ctai-product-card[data-clave="' + (window.CSS && CSS.escape ? CSS.escape(clave) : clave) + '"]');
    cards.forEach(card => {
        card.classList.toggle("is-selected", on);
        const btn = card.querySelector(".ctai-card-btn.compare");
        if (btn) {
            btn.classList.toggle("is-on", on);
            const label = btn.querySelector("span");
            if (label) label.textContent = on ? "Quitar" : "Comparar";
        }
    });
}

// Agrega/quita un producto de la selección de comparación.
function ctaiToggleCompare(p) {
    const clave = p.clave || p.modelo || "";
    if (!clave) return;
    if (ctaiCompare.has(clave)) {
        ctaiCompare.delete(clave);
    } else {
        if (ctaiCompare.size >= CTAI_MAX_COMPARE) {
            // Tope alcanzado: no agregamos más (se comparan hasta 4).
            ctaiUpdateCompareBar();
            return;
        }
        ctaiCompare.set(clave, p);
        ctaiTrack("compare_add", { clave: clave });
    }
    ctaiSyncCardsForClave(clave);
    ctaiUpdateCompareBar();
}

// Muestra/oculta y actualiza la barra flotante "Comparar (N)".
function ctaiUpdateCompareBar() {
    const bar = document.getElementById("ctai-compare-bar");
    if (!bar) return;
    const n = ctaiCompare.size;
    const label = document.getElementById("ctai-compare-bar-label");
    const openLabel = document.getElementById("ctai-compare-open-label");
    const openBtn = document.getElementById("ctai-compare-open");
    if (label) label.textContent = n === 1 ? "1 seleccionado" : n + " seleccionados";
    if (openLabel) openLabel.textContent = "Comparar (" + n + ")";
    if (openBtn) openBtn.disabled = n < 2;
    // La barra aparece con ≥2 seleccionados (con 1 aún no hay qué comparar).
    bar.classList.toggle("is-visible", n >= 2);
}

function ctaiClearCompare() {
    const claves = Array.from(ctaiCompare.keys());
    ctaiCompare.clear();
    claves.forEach(ctaiSyncCardsForClave);
    ctaiUpdateCompareBar();
}

// Índice del producto recomendado: el más barato que esté en existencia; empate → el que esté en promoción.
function ctaiRecommendIndex(products) {
    let best = -1, bestPrice = Infinity, bestPromo = false;
    products.forEach((p, i) => {
        const inStock = ctaiNum(p.en_su_sucursal) > 0 || ctaiNum(p.en_otras_sucursales) > 0;
        if (!inStock) return;
        const price = ctaiPriceMXN(p);
        if (!isFinite(price)) return;
        const promo = ctaiIsPromo(p);
        if (price < bestPrice - 0.001 || (Math.abs(price - bestPrice) < 0.001 && promo && !bestPromo)) {
            best = i; bestPrice = price; bestPromo = promo;
        }
    });
    // Si ninguno está en existencia, favorecemos el más barato disponible por pedido.
    if (best === -1) {
        products.forEach((p, i) => {
            const price = ctaiPriceMXN(p);
            if (isFinite(price) && price < bestPrice - 0.001) { best = i; bestPrice = price; }
        });
    }
    return best;
}

// Construye una columna de la vista de comparación.
function ctaiBuildCompareColumn(p, recommended) {
    const col = document.createElement("div");
    col.className = "ctai-compare-col" + (recommended ? " is-recommended" : "");
    const img = ctaiSafeUrl(p.imagen_url);
    const clave = ctaiEscape(p.clave || p.modelo || "Producto");
    const sub = ctaiEscape([p.marca, p.modelo].filter(Boolean).join(" · ").trim());
    const price = ctaiPriceParts(p.precio, p.moneda);
    const pill = ctaiStockPill(p);
    const promo = ctaiIsPromo(p)
        ? '<span class="ctai-pill promo">' + CTAI_SVG_TAG + 'En promoción</span>'
        : '<span class="ctai-compare-col-promo-off">Sin promoción</span>';

    col.innerHTML =
        (recommended ? '<span class="ctai-compare-reco">Recomendado</span>' : '') +
        '<div class="ctai-compare-col-img' + (img ? '' : ' is-empty') + '">' +
            (img ? '<img src="' + ctaiEscape(img) + '" alt="' + clave + '" loading="lazy">' : '') +
        '</div>' +
        '<div class="ctai-compare-col-clave">' + clave + '</div>' +
        (sub ? '<div class="ctai-compare-col-sub">' + sub + '</div>' : '') +
        (price.main
            ? '<div class="ctai-compare-col-price">' + ctaiEscape(price.main) + '</div>' +
              (price.mxn ? '<div class="ctai-compare-col-mxn">' + ctaiEscape(price.mxn) + '</div>' : '')
            : '') +
        '<div>' + ctaiPillHTML(pill) + '</div>' +
        '<div>' + promo + '</div>';
    return col;
}

// Chips de seguimiento bajo la comparación (mapean a algo que el agente sí responde).
const CTAI_COMPARE_FOLLOWUPS = [
    "¿Cuál es la más barata en existencia?",
    "Muéstrame el precio total en MXN",
    "¿Cuál me conviene?"
];

// Abre la vista de comparación con una lista de productos (o con la selección actual).
function ctaiOpenCompare(products) {
    const list = (products && products.length)
        ? products.slice(0, CTAI_MAX_COMPARE)
        : Array.from(ctaiCompare.values()).slice(0, CTAI_MAX_COMPARE);
    if (list.length < 2) return;

    const overlay = document.getElementById("ctai-compare-overlay");
    const grid = document.getElementById("ctai-compare-grid");
    const followWrap = document.getElementById("ctai-compare-followups");
    if (!overlay || !grid) return;

    // La comparación vive mejor en modo expandido (ancho para 3 columnas).
    const container = document.getElementById("ctai-chat-container");
    if (container && !container.classList.contains("ctai-expanded") && list.length >= 3) {
        const expandBtn = document.getElementById("ctai-expand-button");
        if (expandBtn) expandBtn.click();
    }

    grid.innerHTML = "";
    const reco = ctaiRecommendIndex(list);
    list.forEach((p, i) => grid.appendChild(ctaiBuildCompareColumn(p, i === reco)));

    if (followWrap) {
        followWrap.innerHTML = "";
        CTAI_COMPARE_FOLLOWUPS.forEach(text => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "ctai-chip";
            chip.textContent = text;
            chip.addEventListener("click", () => { ctaiCloseCompare(); sendMessage(text); });
            followWrap.appendChild(chip);
        });
    }

    overlay.classList.add("is-open");
    ctaiTrack("compare_open", { count: list.length });
}

function ctaiCloseCompare() {
    const overlay = document.getElementById("ctai-compare-overlay");
    if (overlay) overlay.classList.remove("is-open");
}

function ctaiCreateBotBubble() {
    const chatMessages = document.getElementById("ctai-chat-messages");
    const wrap = document.createElement("div");
    wrap.className = "bot-message";
    wrap.innerHTML =
        '<div class="bot-text"></div>' +
        '<div class="bot-products"></div>' +
        '<div class="ctai-suggestions"></div>';
    if (chatMessages) chatMessages.appendChild(wrap);
    return wrap;
}

// Renderiza un mensaje del bot dentro de su burbuja (texto markdown + tarjetas + sugerencias).
function ctaiRenderBot(wrap, raw) {
    const parsed = ctaiParseStructured(raw);
    const textEl = wrap.querySelector(".bot-text");
    // Solo re-parseamos el texto si cambió (evita parpadeo del texto mientras llegan productos).
    if (textEl && textEl.dataset.src !== parsed.text) {
        textEl.dataset.src = parsed.text;
        if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
            // Saneamos el HTML del Markdown del LLM antes de inyectarlo (anti-XSS).
            try { textEl.innerHTML = DOMPurify.sanitize(marked.parse(parsed.text)); }
            catch (e) { textEl.textContent = parsed.text; }
        } else {
            // Sin las libs (aún cargando o CDN caído): texto plano seguro, sin HTML.
            textEl.textContent = parsed.text;
        }
    }
    ctaiRenderProducts(wrap.querySelector(".bot-products"), parsed.products);
    ctaiRenderChips(wrap.querySelector(".ctai-suggestions"), parsed.suggestions);
}

function appendBotMessage(raw) {
    const wrap = ctaiCreateBotBubble();
    ctaiRenderBot(wrap, raw);
    requestAnimationFrame(ctaiScrollDown);
    return wrap;
}

// Estado de bienvenida: mensaje general y cálido + los 4 starters. Sin llamadas extra.
function ctaiShowWelcome() {
    ctaiCloseCompare();
    ctaiClearCompare();
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) return;
    chatMessages.innerHTML = "";
    const welcome = document.createElement("div");
    welcome.className = "ctai-welcome";
    welcome.textContent = CTAI_WELCOME;
    chatMessages.appendChild(welcome);
    ctaiRenderStarters();
    ctaiForceBottom();
}

function ctaiRenderStarters() {
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) return;
    const wrap = document.createElement("div");
    wrap.className = "ctai-starters";
    CTAI_STARTERS.forEach((s, idx) => {
        const tile = document.createElement("button");
        tile.type = "button";
        tile.className = "ctai-starter-tile tone-" + (s.tone || "blue");
        tile.style.animationDelay = (idx * 0.05) + "s";
        tile.innerHTML =
            '<span class="ctai-starter-icon">' + s.icon + '</span>' +
            '<span class="ctai-starter-label">' + ctaiEscape(s.label) + '</span>';
        tile.addEventListener("click", () => sendMessage(s.query));
        wrap.appendChild(tile);
    });
    chatMessages.appendChild(wrap);
    requestAnimationFrame(ctaiScrollDown);
}

function appendMessage(sender, message) {
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) return;
    if (sender === "bot") {
        appendBotMessage(message);
        return;
    }
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("user-message");
    msgDiv.textContent = message;
    chatMessages.appendChild(msgDiv);
    requestAnimationFrame(ctaiScrollDown);
}

function initializeChatbotData() {
    if (!window.CTAI_CONFIG) {
      const chatMessages = document.getElementById("ctai-chat-messages");
       if (chatMessages) {
           chatMessages.innerHTML = "<div class='bot-message'>Error crítico: Configuración faltante.</div>";
       }
      return false;
    }
    userId = window.CTAI_CONFIG.userId;
    userKey = window.CTAI_CONFIG.userKey;
    API_BASE = window.CTAI_CONFIG.apiBase;
    CTAI_FX = (typeof window.CTAI_CONFIG.tipoCambio === "number" && window.CTAI_CONFIG.tipoCambio > 0)
        ? window.CTAI_CONFIG.tipoCambio : null;
    if (!userId || !userKey) {
        const chatMessages = document.getElementById("ctai-chat-messages");
        if (chatMessages) {
            chatMessages.innerHTML = "<div class='bot-message'>Error crítico: userId o userKey faltantes en la configuración.</div>";
        }
        return false;
    }
    return true;
}

async function loadHistory() {
    ctaiStick = true; // al (re)cargar historial, mostramos el final
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (chatMessages) {
        chatMessages.innerHTML = "";
        appendMessage("bot", "Cargando historial...");
    } else {}
    try {
        const response = await fetch(`${API_BASE}/history/${encodeURIComponent(userId)}`);
        if (chatMessages) chatMessages.innerHTML = "";

        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage = errorText;
            try {
                const errorJson = JSON.parse(errorText);
                if (errorJson.detail) errorMessage = errorJson.detail;
            } catch (e) {}
            appendMessage("bot", `Error al cargar historial: ${errorMessage || 'Error desconocido'}`);
            throw new Error(`HTTP error! status: ${response.status}. ${errorMessage}`);
        }

        // El servidor devuelve un array plano: [{role, content}]
        const history = await response.json();
        if (!Array.isArray(history) || history.length === 0) {
            ctaiShowWelcome();
            return;
        }

        history.forEach(msg => {
            if (msg && msg.role && msg.content) {
                appendMessage(msg.role === "user" ? "user" : "bot", msg.content);
            } else {
            }
        });
        // Al abrir, siempre mostramos el final de la conversación.
        ctaiForceBottom();
    } catch (error) {
        const chatMessages = document.getElementById("ctai-chat-messages");
         if (chatMessages && chatMessages.innerHTML === "") {
             appendMessage("bot", "No se pudo cargar el historial de mensajes.");
         } else if (chatMessages && chatMessages.innerHTML.includes("Cargando historial")) {
             chatMessages.innerHTML = "";
              appendMessage("bot", "No se pudo cargar el historial de mensajes.");
         } else {}
    }
}

function showSpinner() {
    const chatMessages = document.getElementById('ctai-chat-messages');
    if (!chatMessages) return;
    const existingSpinner = chatMessages.querySelector('.typing-indicator');
    if (existingSpinner) return;
    const spinner = document.createElement('div');
    spinner.className = 'typing-indicator';
    spinner.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(spinner);
     requestAnimationFrame(() => {
         const container = document.getElementById("ctai-messages-container");
         if(container) container.scrollTop = container.scrollHeight;
     });
}

function hideSpinner() {
    const chatMessages = document.getElementById('ctai-chat-messages');
    if (!chatMessages) return;
    const spinner = chatMessages.querySelector('.typing-indicator');
    if (spinner) {
        spinner.remove();
    }
}

async function sendMessage(presetText) {
    const userInput = document.getElementById('ctai-user-input');
    let message;
    if (typeof presetText === "string") {
        message = presetText.trim();
    } else {
        if (!userInput) return;
        message = userInput.value.trim();
    }
    if (!message) return;
    if (ctaiAbort) return; // ya hay una respuesta en curso

    ctaiStick = true; // al enviar, seguimos el flujo hacia el final

    // Quitar las opciones iniciales una vez que el usuario interactúa
    const starters = document.querySelector(".ctai-starters");
    if (starters) starters.remove();

    ctaiLastUserMsg = message;
    appendMessage('user', message);
    if (userInput) { userInput.value = ''; userInput.style.height = 'auto'; }
    showSpinner();
    let spinnerVisible = true;
    ctaiAbort = new AbortController();
    ctaiSetSending(true);
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_query: message,
                user_id: userId,
                listaPrecio: userKey
            }),
            signal: ctaiAbort.signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage = errorText;
            try {
                const errorJson = JSON.parse(errorText);
                if (errorJson.detail) errorMessage = errorJson.detail;
                if (errorJson.mensaje) errorMessage = errorJson.mensaje;
            } catch (e) {
            }
            if (spinnerVisible) hideSpinner();
            spinnerVisible = false;
            appendMessage('bot', `Error al enviar mensaje (${response.status}): ${errorMessage || 'Error desconocido'}`);
            return;
        }

        // Respuesta en streaming: leemos el cuerpo por chunks y renderizamos incrementalmente.
        if (spinnerVisible) hideSpinner();
        spinnerVisible = false;

        const wrap = ctaiCreateBotBubble();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let botResponse = "";
        let lastRender = 0;
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            botResponse += decoder.decode(value, { stream: true });
            // Throttle: re-parseamos a lo más cada ~60ms para suavizar el reformateo del markdown
            const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
            if (now - lastRender > 50) {
                ctaiRenderBot(wrap, botResponse);
                requestAnimationFrame(ctaiScrollDown);
                lastRender = now;
            }
        }
        botResponse += decoder.decode(); // flush final del decoder
        ctaiRenderBot(wrap, botResponse); // render final (captura lo último que faltara)
        requestAnimationFrame(ctaiScrollDown);

        // Ruta secundaria (escribir): si el usuario pidió comparar y llegaron 2–4 productos,
        // abrimos directamente la vista de comparación con esos productos.
        if (/\bcompar/i.test(ctaiLastUserMsg)) {
            const prods = ctaiParseStructured(botResponse).products;
            if (prods.length >= 2 && prods.length <= CTAI_MAX_COMPARE) {
                requestAnimationFrame(() => ctaiOpenCompare(prods));
            }
        }

    } catch (error) {
        if (spinnerVisible) hideSpinner();
        // Si el usuario detuvo la respuesta, no mostramos error; la respuesta parcial se conserva.
        if (error && error.name !== 'AbortError') {
            appendMessage('bot', `Error al obtener respuesta: ${error.message || 'Error desconocido'}`);
        }
    } finally {
        if (spinnerVisible) hideSpinner();
        ctaiAbort = null;
        ctaiSetSending(false);
    }
}

async function deleteConversation() {
    try {
        const response = await fetch(`${API_BASE}/history/${encodeURIComponent(userId)}`, { method: 'DELETE' });
        if (response.status === 204 || response.status === 200 || response.estatus === 'success') {
            ctaiShowWelcome();
        } else if (response.status >= 400) {
             const errorDetail = await response.text();
             appendMessage("bot", `Error al intentar eliminar la conversación: ${errorDetail || 'Error desconocido'}`);
        } else {
             appendMessage("bot", "La solicitud de eliminación tuvo un resultado inesperado.");
        }
    } catch (error) {
        appendMessage("bot", `Error de conexión al intentar eliminar la conversación: ${error.message}`);
    }
}

// --- Funciones para el Modal de Confirmación ---
function showConfirmModal(message, onConfirm, onCancel) {
    if (document.querySelector('.modal-overlay')) return;
    const overlay = document.createElement('div');
    overlay.classList.add('modal-overlay');
    const modalBox = document.createElement('div');
    modalBox.classList.add('modal-box');
    const messagePara = document.createElement('p');
    messagePara.textContent = message;
    const buttonsDiv = document.createElement('div');
    buttonsDiv.classList.add('modal-buttons');
    const confirmButton = document.createElement('button');
    confirmButton.classList.add('confirm-button');
    confirmButton.textContent = 'Sí, Eliminar';
    const cancelButton = document.createElement('button');
    cancelButton.classList.add('cancel-button');
    cancelButton.textContent = 'Cancelar';
    buttonsDiv.appendChild(confirmButton);
    buttonsDiv.appendChild(cancelButton);
    modalBox.appendChild(messagePara);
    modalBox.appendChild(buttonsDiv);
    overlay.appendChild(modalBox);
    document.body.appendChild(overlay);
    overlay.offsetHeight; // Trigger reflow
    overlay.classList.add('visible');
    confirmButton.addEventListener('click', () => {
        onConfirm();
        hideConfirmModal();
    });
    cancelButton.addEventListener('click', () => {
        if(onCancel) onCancel();
        hideConfirmModal();
    });
    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            if(onCancel) onCancel();
            hideConfirmModal();
        }
    });
}

function hideConfirmModal() {
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) {
        overlay.classList.remove('visible');
        overlay.addEventListener('transitionend', () => {
            overlay.remove();
        }, { once: true });
    }
}


window.initCTAIChatApp = function() {
    if (!initializeChatbotData()) {
        return;
    }
    setupAutoResizeTextarea();
    const userInput = document.getElementById('ctai-user-input');
    const sendButton = document.getElementById("ctai-send-button");
    const deleteButton = document.getElementById("ctai-delete-history-button");
    if (userInput && sendButton) {
        userInput.addEventListener("keydown", function(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });
        sendButton.addEventListener("click", function() {
            if (sendButton.classList.contains("is-stop")) {
                stopGeneration();
            } else {
                sendMessage();
            }
        });
    } else {}
    if (deleteButton) {
        deleteButton.addEventListener("click", function() {
            showConfirmModal(
                "¿Estás seguro de que quieres eliminar todo el historial de conversación? Esta acción no se puede deshacer.",
                deleteConversation
            );
        });
    } else {}

    // Barra flotante de comparación + vista de comparación.
    const compareOpenBtn = document.getElementById("ctai-compare-open");
    const compareClearBtn = document.getElementById("ctai-compare-clear");
    const compareCloseBtn = document.getElementById("ctai-compare-close");
    if (compareOpenBtn) compareOpenBtn.addEventListener("click", () => ctaiOpenCompare());
    if (compareClearBtn) compareClearBtn.addEventListener("click", ctaiClearCompare);
    if (compareCloseBtn) compareCloseBtn.addEventListener("click", ctaiCloseCompare);

    // Botón "ir a los mensajes recientes": visible al subir; al hacer clic baja.
    const scrollContainer = document.getElementById("ctai-messages-container");
    const scrollBtn = document.getElementById("ctai-scroll-bottom");
    if (scrollContainer && scrollBtn) {
        scrollContainer.addEventListener("scroll", function() {
            if (ctaiAdjusting) return; // no recalcular mientras re-anclamos por expand
            ctaiStick = ctaiNearBottom(scrollContainer);
            ctaiUpdateScrollBtn();
        });
        scrollBtn.addEventListener("click", function() {
            ctaiStick = true;
            scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: "smooth" });
            scrollBtn.classList.remove("is-visible");
        });
    }

    // Botón expandir/contraer: alterna el ancho del panel y recuerda el estado.
    const expandButton = document.getElementById("ctai-expand-button");
    const container = document.getElementById("ctai-chat-container");
    if (expandButton && container) {
        const applyExpanded = (on) => {
            container.classList.toggle("ctai-expanded", on);
            expandButton.setAttribute("aria-label", on ? "Contraer panel" : "Expandir panel");
            expandButton.setAttribute("title", on ? "Contraer" : "Expandir");
            expandButton.innerHTML = on ? CTAI_ICON_COLLAPSE : CTAI_ICON_EXPAND;
        };
        let expanded = false;
        try { expanded = sessionStorage.getItem("ctai-expanded") === "1"; } catch (e) {}
        applyExpanded(expanded);
        expandButton.addEventListener("click", function() {
            const on = !container.classList.contains("ctai-expanded");
            // Cambiar el ancho re-acomoda el texto (cambian las alturas). Para respetar
            // dónde estaba el usuario usamos el ancla correcta para cada caso:
            //  - al final  -> anclar al fondo (se queda al final),
            //  - subido    -> anclar el primer mensaje visible arriba (queda en el mismo
            //                 punto del viewport, sin importar cómo cambien las alturas).
            const scroller = document.getElementById("ctai-messages-container");
            const list = document.getElementById("ctai-chat-messages");
            const stuck = scroller ? ctaiNearBottom(scroller) : true;

            let anchorEl = null;
            let anchorDelta = 0;
            if (scroller && list && !stuck) {
                const cTop = scroller.getBoundingClientRect().top;
                for (let i = 0; i < list.children.length; i++) {
                    const r = list.children[i].getBoundingClientRect();
                    if (r.bottom > cTop + 1) {        // primer hijo que cruza el borde superior
                        anchorEl = list.children[i];
                        anchorDelta = r.top - cTop;   // su offset respecto al tope del viewport
                        break;
                    }
                }
            }

            applyExpanded(on);
            try { sessionStorage.setItem("ctai-expanded", on ? "1" : "0"); } catch (e) {}
            ctaiTrack(on ? "expand" : "collapse");

            if (scroller) {
                // El ancho se anima (~250ms) => las alturas cambian frame a frame.
                // Re-anclamos en CADA frame durante la animación (sin depender de
                // transitionend, que puede no dispararse).
                ctaiAdjusting = true;
                const startT = (typeof performance !== "undefined" ? performance.now() : Date.now());
                const DURATION = 360;
                const reanchor = () => {
                    if (stuck || !anchorEl) {
                        scroller.scrollTop = scroller.scrollHeight;             // al fondo
                    } else {
                        const cur = anchorEl.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
                        scroller.scrollTop += (cur - anchorDelta);             // devuelve el ancla a su sitio
                    }
                };
                const glue = (now) => {
                    reanchor();
                    if (now - startT < DURATION) {
                        requestAnimationFrame(glue);
                    } else {
                        reanchor();
                        ctaiAdjusting = false;
                        ctaiStick = ctaiNearBottom(scroller);
                        ctaiUpdateScrollBtn();
                    }
                };
                requestAnimationFrame(glue);
            }
        });
    }

    loadHistory();
};