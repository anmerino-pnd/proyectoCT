
let userId = null;
let userKey = null;
let API_BASE = null;
let ctaiAbort = null; // AbortController de la respuesta en curso (para el botón detener)

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
function ctaiScrollDown() {
    const c = document.getElementById("ctai-messages-container");
    if (c) c.scrollTop = c.scrollHeight;
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

function ctaiFormatPrice(precio, moneda) {
    const n = Number(precio);
    if (!isFinite(n) || n <= 0) return "";
    const cur = (moneda || "MXN").toString().toUpperCase();
    return "$" + n.toLocaleString("es-MX", { maximumFractionDigits: 2 }) + " " + cur;
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

// Construye el elemento DOM de una tarjeta de producto.
function ctaiBuildProductCard(p) {
    const url = ctaiSafeUrl(p.url);
    const img = ctaiSafeUrl(p.imagen_url);
    const card = document.createElement(url ? "a" : "div");
    card.className = "ctai-product-card";
    if (url) { card.href = url; card.target = "_blank"; card.rel = "noopener noreferrer"; }

    const title = ctaiEscape(p.clave || p.modelo || "Producto");           // título = Clave CT
    const subtitle = ctaiEscape([p.marca, p.modelo].filter(Boolean).join(" ").trim());
    const price = ctaiFormatPrice(p.precio, p.moneda);

    const availParts = [];
    if (typeof p.en_su_sucursal === "number" && p.en_su_sucursal > 0)
        availParts.push(p.en_su_sucursal + " en tu sucursal");
    if (typeof p.en_otras_sucursales === "number" && p.en_otras_sucursales > 0)
        availParts.push(p.en_otras_sucursales + " en otras sucursales");
    const avail = availParts.length ? availParts.join(" / ") : "Sobre pedido";

    const promo = (p.en_promocion === true || p.en_promocion === "Sí" || p.en_promocion === "si")
        ? '<span class="ctai-badge promo">En promoción</span>' : '';

    card.innerHTML =
        '<div class="ctai-card-img' + (img ? '' : ' is-empty') + '">' +
            (img ? '<img src="' + ctaiEscape(img) + '" alt="' + title + '" loading="lazy">' : '') +
        '</div>' +
        '<div class="ctai-card-body">' +
            '<div class="ctai-card-title">' + title + '</div>' +
            (subtitle ? '<div class="ctai-card-sub">' + subtitle + '</div>' : '') +
            '<div class="ctai-card-priceline">' +
                (price ? '<span class="ctai-card-price">' + price + '</span>' : '') + promo +
            '</div>' +
            '<div class="ctai-card-avail">' + avail + '</div>' +
        '</div>';
    return card;
}

// Render INCREMENTAL: agrega solo las tarjetas nuevas (1 a 1) sin reconstruir las ya mostradas.
function ctaiRenderProducts(el, products) {
    if (!el) return;
    products = products || [];
    const rendered = parseInt(el.dataset.count || "0", 10);
    if (products.length <= rendered) return;               // nada nuevo
    if (products.length > 0) el.className = "bot-products ctai-products";
    for (let idx = rendered; idx < products.length; idx++) {
        const card = ctaiBuildProductCard(products[idx]);
        card.style.animationDelay = ((idx - rendered) * 0.07) + "s";   // cascada suave
        el.appendChild(card);
    }
    el.dataset.count = String(products.length);
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
        if (typeof marked !== "undefined") {
            try { textEl.innerHTML = marked.parse(parsed.text); }
            catch (e) { textEl.textContent = parsed.text; }
        } else {
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
            appendMessage("bot", "¡Hola! Soy tu asistente de CT. ¿En qué puedo ayudarte hoy?");
            ctaiRenderStarters();
            return;
        }

        history.forEach(msg => {
            if (msg && msg.role && msg.content) {
                appendMessage(msg.role === "user" ? "user" : "bot", msg.content);
            } else {
            }
        });
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

    // Quitar las opciones iniciales una vez que el usuario interactúa
    const starters = document.querySelector(".ctai-starters");
    if (starters) starters.remove();

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
            const chatMessages = document.getElementById("ctai-chat-messages");
            if (chatMessages) {
                chatMessages.innerHTML = "";
                appendMessage("bot", "¡Hola! Soy tu asistente de CT. ¿En qué puedo ayudarte hoy?");
                ctaiRenderStarters();
            } else {}
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
    loadHistory();
};