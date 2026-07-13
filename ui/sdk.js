// Origen y carpeta del propio SDK, derivados del <script> que lo cargó.
// __CTAI_ASSET_BASE: carpeta donde viven sdk.js/app.js/styles.css (p.ej. https://<dominio>/sdk/)
// __CTAI_ORIGIN:     origen para las llamadas a la API (p.ej. https://<dominio>)
const __ctaiSdkScript = document.currentScript;
const __CTAI_ASSET_BASE = __ctaiSdkScript ? new URL(".", __ctaiSdkScript.src).href : "";
const __CTAI_ORIGIN = __ctaiSdkScript ? new URL(__ctaiSdkScript.src).origin : "";

class CTAIWidget {
    static init(config = {}) {
        const fx = parseFloat(config.tipoCambio);
        const settings = {
            apiBase: config.apiBase || __CTAI_ORIGIN,
            userId: config.userId,
            userKey: config.userKey,
            containerId: config.containerId || "ctai-widget-root",
            chatIconUrl: config.chatIconUrl || (__CTAI_ASSET_BASE + "chat.png"),
            // Tipo de cambio USD→MXN que el portal ya conoce (mismo dato del portal).
            // Opcional: si no viene, las tarjetas simplemente omiten la línea "≈ MXN".
            // No dispara ninguna llamada de datos ni añade latencia.
            tipoCambio: (isFinite(fx) && fx > 0) ? fx : null
        };
        if (!settings.userId || !settings.userKey) {
            const errorDiv = document.createElement("div");
            errorDiv.style.color = "red";
            errorDiv.textContent = "Error al inicializar el chat: Falta UserID o UserKey.";
            document.body.insertBefore(errorDiv, document.body.firstChild);
            return;
        }
        let container = document.getElementById(settings.containerId);
        if (!container) {
            container = document.createElement("div");
            container.id = settings.containerId;
            document.body.appendChild(container);
        } else {}
        container.innerHTML = `
            <div class="chat-bubble" onclick="window.CTAIChat.toggle()" aria-label="Abrir/Cerrar chat">
                <img src="${settings.chatIconUrl}" alt="Abrir chat" class="chat-icon">
            </div>
            <div class="chat-container" id="ctai-chat-container">
                <div class="chat-header">
                    <div class="ctai-header-info">
                        <div class="ctai-header-avatar"><img src="${settings.chatIconUrl}" alt=""></div>
                        <div class="ctai-header-titles">
                            <span class="ctai-header-title">CT Ayuda</span>
                            <span class="ctai-header-status">Asistente en línea</span>
                        </div>
                    </div>
                    <div class="buttons-container">
                        <button class="ctai-icon-btn" id="ctai-expand-button" title="Expandir" aria-label="Expandir panel">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M15 3h6v6"></path>
                                <path d="M9 21H3v-6"></path>
                                <path d="M21 3l-7 7"></path>
                                <path d="M3 21l7-7"></path>
                            </svg>
                        </button>
                        <button class="ctai-icon-btn" id="ctai-delete-history-button" title="Borrar conversación" aria-label="Borrar conversación">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M3 6h18"></path>
                                <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                                <path d="M10 11v6"></path>
                                <path d="M14 11v6"></path>
                            </svg>
                        </button>
                        <button class="ctai-icon-btn" onclick="window.CTAIChat.toggle()" title="Cerrar" aria-label="Cerrar chat">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M18 6 6 18"></path>
                                <path d="M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="chat-box" id="ctai-chat-box">
                    <div class="messages-container" id="ctai-messages-container">
                        <div class="chat-messages" id="ctai-chat-messages"></div>
                    </div>
                    <div class="chat-input" id="ctai-chat-input">
                        <button class="ctai-scroll-bottom" id="ctai-scroll-bottom" type="button" title="Ir a los mensajes recientes" aria-label="Ir a los mensajes recientes">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M12 5v14"></path>
                                <path d="m19 12-7 7-7-7"></path>
                            </svg>
                        </button>
                        <textarea class="message-input" id="ctai-user-input" placeholder="Escribe tu mensaje" rows="1"></textarea>
                        <button class="send-button" id="ctai-send-button" aria-label="Enviar mensaje"></button>
                    </div>
                    <div class="ctai-compare-bar" id="ctai-compare-bar">
                        <span class="ctai-compare-bar-label" id="ctai-compare-bar-label">0 seleccionados</span>
                        <div class="ctai-compare-bar-actions">
                            <button class="ctai-compare-clear" id="ctai-compare-clear" type="button">Limpiar</button>
                            <button class="ctai-compare-open" id="ctai-compare-open" type="button">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <path d="M3 6h4"></path><path d="M3 12h9"></path><path d="M3 18h14"></path>
                                    <path d="M18 4v6"></path><path d="m15 7 3-3 3 3"></path>
                                </svg>
                                <span id="ctai-compare-open-label">Comparar</span>
                            </button>
                        </div>
                    </div>
                    <div class="ctai-compare-overlay" id="ctai-compare-overlay">
                        <div class="ctai-compare-head">
                            <span class="ctai-compare-title">Comparar productos</span>
                            <button class="ctai-icon-btn" id="ctai-compare-close" type="button" title="Cerrar comparación" aria-label="Cerrar comparación">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <path d="M18 6 6 18"></path><path d="M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                        <div class="ctai-compare-body"><div class="ctai-compare-grid" id="ctai-compare-grid"></div></div>
                        <div class="ctai-compare-followups" id="ctai-compare-followups"></div>
                    </div>
                </div>
                <div class="chat-warning" style="padding: 1px 4px; font-size: 11px; text-align: center;">
                    Este chatbot puede cometer errores. Compruebe la información importante con un asesor.
                </div>
            </div>
        `;
        // marked (render de Markdown) y DOMPurify (saneado anti-XSS de la salida del
        // LLM) se cargan con versión FIJA + SRI para evitar drift/compromiso del CDN.
        if (typeof marked === "undefined") {
            const scriptMarked = document.createElement("script");
            scriptMarked.src = "https://cdnjs.cloudflare.com/ajax/libs/marked/16.3.0/marked.min.js";
            scriptMarked.integrity = "sha512-gxBP/mcwo9A5lJDFbVfXNb1hSLpOkHLLXAjld8HfCWjVIZnA3nlNnIqSTLvtwF4t55Dt4Rzh7phL3tJuKZ+teQ==";
            scriptMarked.crossOrigin = "anonymous";
            scriptMarked.referrerPolicy = "no-referrer";
            scriptMarked.onerror = () => {};
            document.head.appendChild(scriptMarked);
        }
        if (typeof DOMPurify === "undefined") {
            const scriptPurify = document.createElement("script");
            scriptPurify.src = "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.4.8/purify.min.js";
            scriptPurify.integrity = "sha512-JfRHuuInas3e80YgJBTb6JfrK4ngt4FRR9utxm7RbiuRVRNBdPORorA/WTgRKFCK7nbo+9ANMcEOVznsYvi3+A==";
            scriptPurify.crossOrigin = "anonymous";
            scriptPurify.referrerPolicy = "no-referrer";
            scriptPurify.onerror = () => {};
            document.head.appendChild(scriptPurify);
        }
        if (!document.getElementById("ctai-styles")) {
             const styleLink = document.createElement("link");
             styleLink.id = "ctai-styles";
             styleLink.rel = "stylesheet";
             styleLink.href = __CTAI_ASSET_BASE + "styles.css";
             document.head.appendChild(styleLink);
        } else {}
        window.CTAI_CONFIG = settings;
        window.CTAIChat = {
            toggle: () => {
                const chat = document.getElementById("ctai-chat-container");
                if (!chat) return;
                const willOpen = !chat.classList.contains("ctai-open");
                chat.classList.toggle("ctai-open", willOpen);
                if (typeof window.ctaiTrack === "function") {
                    window.ctaiTrack(willOpen ? "open" : "close");
                }
                if (willOpen && typeof window.loadHistory === "function") {
                    setTimeout(() => window.loadHistory(), 100);
                } else if (willOpen && typeof window.loadHistory !== "function") {
                    console.warn("CTAI App: loadHistory no está disponible después del toggle.");
                }
            },
            sendMessageTrigger: () => {
                const sendButton = document.getElementById("ctai-send-button");
                if (sendButton) {
                    sendButton.click();
                } else {}
            }
        };
        if (!window.__CTAI_APP_LOADED__) {
            const scriptApp = document.createElement("script");
            scriptApp.src = __CTAI_ASSET_BASE + "app.js";
            scriptApp.defer = true;
            scriptApp.onload = () => {
                window.__CTAI_APP_LOADED__ = true;
                if (typeof window.initCTAIChatApp === 'function') {
                    window.initCTAIChatApp();
                } else {
                     const chatMessages = document.getElementById("ctai-chat-messages");
                     if (chatMessages) {
                         chatMessages.innerHTML = "<div class='bot-message'>Error crítico: No se pudo cargar la lógica del chat.</div>";
                     }
                }
            };
            scriptApp.onerror = () => {
                window.__CTAI_APP_LOADED__ = false;
                const chatMessages = document.getElementById("ctai-chat-messages");
                 if (chatMessages) {
                     if (typeof window.appendMessage === 'function') {
                         window.appendMessage("bot", "Error crítico: No se pudo cargar la lógica del chat.");
                     } else {
                          chatMessages.innerHTML = "<div class='bot-message'>Error crítico: No se pudo cargar la lógica del chat.</div>";
                     }
                 }
            }
            document.body.appendChild(scriptApp);
        } else {
             if (typeof window.initCTAIChatApp === 'function') {
                  window.initCTAIChatApp();
             } else {
                  console.warn("CTAIChat: app.js ya cargado pero window.initCTAIChatApp no encontrada en re-llamada.");
             }
        }
    }
}
const currentSdkScript = document.currentScript;
let autoInitConfig = null;
if (currentSdkScript && currentSdkScript.dataset.autoInit !== "false") {
    autoInitConfig = {
        userId: currentSdkScript.dataset.userId,
        userKey: currentSdkScript.dataset.userKey,
        apiBase: currentSdkScript.dataset.apiBase,
        chatIconUrl: currentSdkScript.dataset.chatIconUrl,
        containerId: currentSdkScript.dataset.containerId,
        tipoCambio: currentSdkScript.dataset.tipoCambio
    };
    if (!autoInitConfig.userId || !autoInitConfig.userKey) {
       console.error("CTAIChat: (Pre-init) Faltan data-user-id o data-user-key en el tag <script>. La auto-inicialización será omitida.");
       autoInitConfig = null;
    } else {}
} else if (!currentSdkScript) {
    console.warn("CTAIChat: document.currentScript es null. La auto-inicialización podría fallar si depende de data-*.");
} else {}
document.addEventListener("DOMContentLoaded", () => {
    if (autoInitConfig) {
        CTAIWidget.init(autoInitConfig);
    } else if (currentSdkScript?.dataset.autoInit !== "false") {
        console.warn("CTAIChat: No se pudo auto-inicializar debido a configuración faltante o incorrecta. Inicialice manualmente con CTAIWidget.init({...}).");
    } else {}
});