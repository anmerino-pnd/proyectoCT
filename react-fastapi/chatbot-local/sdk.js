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
            console.error("CTAIChat: (init) Se requieren 'userId' y 'userKey'. Abortando inicialización.");

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
        } else {
             console.log(`CTAIChat: Usando contenedor existente con id='${settings.containerId}'`);
        }


        container.innerHTML = `
            <div class="chat-bubble" onclick="window.CTAIChat.toggle()">
                <img src="${settings.chatIconUrl}" alt="Abrir chat" class="chat-icon">
            </div>
            <div class="chat-container" id="ctai-chat-container" style="display:none">
                <div class="chat-header">
                    <span>CT Ayuda</span>
                    <button class="close-button" onclick="window.CTAIChat.toggle()">×</button>
                </div>
                <div class="chat-box" id="ctai-chat-box">
                    <div class="messages-container" id="ctai-messages-container">
                        <div class="chat-messages" id="ctai-chat-messages"></div>
                    </div>
                    <div class="chat-input" id="ctai-chat-input">
                        <textarea class="message-input" id="ctai-user-input" placeholder="Escribe tu mensaje" rows="1"></textarea>
                        <button class="send-button" id="ctai-send-button"></button>
                    </div>
                </div>
            </div>
        `;


        if (typeof marked === "undefined") {
            const scriptMarked = document.createElement("script");
            scriptMarked.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
            scriptMarked.onerror = () => console.error("CTAIChat: Error al cargar marked.js.");
            document.head.appendChild(scriptMarked);
        }


        if (!document.querySelector('link[href="styles.css"]')) {
            const styleLink = document.createElement("link");
            styleLink.rel = "stylesheet";
            styleLink.href = "https://ctdev.ctonline.mx/static2/plugins/chatbot/styles.css"; 
            document.head.appendChild(styleLink);
        } else {
             console.log("CTAIChat: styles.css ya parece estar en el DOM.");
        }


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

                } else {
                    console.error("CTAIChat: Contenedor 'ctai-chat-container' no encontrado para toggle.")
                }
            },
            sendMessageTrigger: () => {
                const sendButton = document.getElementById("ctai-send-button");
                if (sendButton) {
                    sendButton.click(); 
                } else {
                    console.error("CTAIChat: Botón 'ctai-send-button' no encontrado para trigger.")
                }
            }
        };


        if (!window.__CTAI_APP_LOADED__) {
            const scriptApp = document.createElement("script");
            scriptApp.src = "app.js"; 
            scriptApp.defer = true; 
        scriptApp.onload = () => {
            window.__CTAI_APP_LOADED__ = true;

            if (typeof window.initCTAIChatApp === 'function') {
                window.initCTAIChatApp();
            } else {
                console.error("CTAI App: window.initCTAIChatApp no encontrada después de cargar app.js. La lógica de la app no se inicializará.");
                    const chatMessages = document.getElementById("ctai-chat-messages");
                    if (typeof window.appendMessage === 'function' && chatMessages) {
                        window.appendMessage("bot", "Error crítico: No se pudo inicializar la lógica del chat.");
                    } else if (chatMessages) {
                        chatMessages.innerHTML = "<div class='bot-message'>Error crítico: No se pudo cargar la lógica del chat.</div>";
                    }
            }
        };
            scriptApp.onerror = () => {
                console.error("CTAIChat: Error al cargar app.js.");
                window.__CTAI_APP_LOADED__ = false;
                const chatMessages = document.getElementById("ctai-chat-messages");
                if (chatMessages) appendMessage("bot", "Error crítico: No se pudo cargar la lógica del chat.");
            }
            document.body.appendChild(scriptApp);
        } else {

             if (typeof window.initCTAIChatApp === 'function') {
                  window.initCTAIChatApp();
             } else {
                  console.warn("CTAI App: app.js ya cargado pero window.initCTAIChatApp no encontrada.");
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
    } 
} else if (!currentSdkScript) {
   console.warn("CTAIChat: document.currentScript es null. La auto-inicialización podría fallar si depende de data-*.");
} 


document.addEventListener("DOMContentLoaded", () => {
    if (autoInitConfig) {
        CTAIWidget.init(autoInitConfig);
    } else if (currentSdkScript?.dataset.autoInit !== "false") {
        console.warn("CTAIChat: No se pudo auto-inicializar debido a configuración faltante o incorrecta. Inicialice manualmente con CTAIWidget.init({...}).");
    } else {
        console.log("CTAIChat: Auto-inicialización omitida según configuración.");
    }
});
