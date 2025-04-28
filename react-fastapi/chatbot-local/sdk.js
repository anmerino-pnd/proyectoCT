class CTAIWidget {
    static init(config = {}) {
        const settings = {
            apiBase: config.apiBase || "http://10.10.251.160:8000",
            userId: config.userId,
            userKey: config.userKey,
            containerId: config.containerId || "ctai-widget-root",
            chatIconUrl: config.chatIconUrl || "chat.png"
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
            <div class="chat-container" id="ctai-chat-container" style="display:none">
                <div class="chat-header">
                    <span>CT Ayuda</span>
                    <div class="buttons-container">
                        <button class="deleteButton" id="ctai-delete-history-button" aria-label="Eliminar historial">
                             <svg fill="none" viewBox="0 0 50 59" class="bin"> 
                                <path fill="#B5BAC1" d="M0 7.5C0 5.01472 2.01472 3 4.5 3H45.5C47.9853 3 50 5.01472 50 7.5V7.5C50 8.32843 49.3284 9 48.5 9H1.5C0.671571 9 0 8.32843 0 7.5V7.5Z"></path> 
                                <path fill="#B5BAC1" d="M17 3C17 1.34315 18.3431 0 20 0H29.3125C30.9694 0 32.3125 1.34315 32.3125 3V3H17V3Z"></path> 
                                <path fill="#B5BAC1" d="M2.18565 18.0974C2.08466 15.821 3.903 13.9202 6.18172 13.9202H43.8189C46.0976 13.9202 47.9160 15.8210 47.8150 18.0975L46.1699 55.1775C46.0751 57.3155 44.3140 59.0002 42.1739 59.0002H7.8268C5.68661 59.0002 3.92559 57.3155 3.83073 55.1775L2.18565 18.0974ZM18.0003 49.5402C16.6196 49.5402 15.5003 48.4209 15.5003 47.0402V24.9602C15.5003 23.5795 16.6196 22.4602 18.0003 22.4602C19.3810 22.4602 20.5003 23.5795 20.5003 24.9602V47.0402C20.5003 48.4209 19.3810 49.5402 18.0003 49.5402ZM29.5003 47.0402C29.5003 48.4209 30.6196 49.5402 32.0003 49.5402C33.3810 49.5402 34.5003 48.4209 34.5003 47.0402V24.9602C34.5003 23.5795 33.3810 22.4602 32.0003 22.4602C30.6196 22.4602 29.5003 23.5795 29.5003 24.9602V47.0402Z" clip-rule="evenodd" fill-rule="evenodd"></path> 
                                <path fill="#B5BAC1" d="M2 13H48L47.6742 21.28H2.32031L2 13Z"></path> 
                            </svg>
                            <span class="tooltip">Delete</span> 
                        </button>
                        <button class="close-button" onclick="window.CTAIChat.toggle()" aria-label="Cerrar chat">×</button>
                    </div>
                </div>
                <div class="chat-box" id="ctai-chat-box">
                    <div class="messages-container" id="ctai-messages-container">
                        <div class="chat-messages" id="ctai-chat-messages"></div>
                    </div>
                    <div class="chat-input" id="ctai-chat-input">
                        <textarea class="message-input" id="ctai-user-input" placeholder="Escribe tu mensaje" rows="1"></textarea>
                        <button class="send-button" id="ctai-send-button" aria-label="Enviar mensaje"></button>
                    </div>
                </div>
            </div>
        `;
        if (typeof marked === "undefined") {
            const scriptMarked = document.createElement("script");
            scriptMarked.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
            scriptMarked.onerror = () => {};
            document.head.appendChild(scriptMarked);
        }
        if (!document.querySelector('link[href="styles.css"]')) {
             const styleLink = document.createElement("link");
             styleLink.rel = "stylesheet";
             // *** CAMBIA ESTA LÍNEA SEGÚN TU AMBIENTE ***
             styleLink.href = "styles.css"; // Para probar en local
             // styleLink.href = "https://ctdev.ctonline.mx/static2/plugins/chatbot/styles.css"; // Para desplegar
             // styleLink.href = "https://pagina-dev.empresa.com/chatbot-api/styles.css"; // Proxy en dev
             document.head.appendChild(styleLink);
        } else {}
        window.CTAI_CONFIG = settings;
        window.CTAIChat = {
            toggle: () => {
                const chat = document.getElementById("ctai-chat-container");
                if(chat) {
                    const isHidden = !chat.style.display || chat.style.display === "none";
                    chat.style.display = isHidden ? "flex" : "none";
                    if (isHidden && typeof window.loadHistory === 'function') {
                         setTimeout(() => window.loadHistory(), 100);
                    } else if (isHidden && typeof window.loadHistory !== 'function'){
                         console.warn("CTAI App: loadHistory no está disponible después del toggle.");
                    }
                } else {}
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
            scriptApp.src = "app.js"; // Para probar en local
            // scriptApp.src = "https://ctdev.ctonline.mx/static2/plugins/chatbot/app.js"; // Para desplegar
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
        containerId: currentSdkScript.dataset.containerId
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