// sdk.js

// widget/sdk.js - Versión con inicialización corregida para timing

class CTAIWidget {
    static init(config = {}) {
        console.log("CTAIChat: CTAIWidget.init llamada con config:", config);

        // 1. Validar configuración ANTES de hacer nada más
        const settings = {
            // Usa el apiBase de la config si existe, si no, usa el por defecto
            apiBase: config.apiBase || "http://10.10.251.160:8000",
            userId: config.userId,
            userKey: config.userKey,
            containerId: config.containerId || "ctai-widget-root",
            chatIconUrl: config.chatIconUrl || "chat.png"
        };

        if (!settings.userId || !settings.userKey) {
            console.error("CTAIChat: (init) Se requieren 'userId' y 'userKey'. Abortando inicialización.");
            // Opcional: Añadir un mensaje de error al cuerpo de la página
             const errorDiv = document.createElement("div");
             errorDiv.style.color = "red";
             errorDiv.textContent = "Error al inicializar el chat: Falta UserID o UserKey.";
             document.body.insertBefore(errorDiv, document.body.firstChild);
            return; // Detener si faltan datos clave
        }

        // 2. Crear contenedor raíz (si no existe)
        let container = document.getElementById(settings.containerId);
        if (!container) {
            console.log(`CTAIChat: Creando contenedor raíz con id='${settings.containerId}'`);
            container = document.createElement("div");
            container.id = settings.containerId;
            document.body.appendChild(container);
        } else {
             console.log(`CTAIChat: Usando contenedor existente con id='${settings.containerId}'`);
        }

        // 3. Inyectar estructura HTML
        // Nota: El botón de enviar ahora llama a CTAIChat.sendMessageTrigger()
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
         console.log("CTAIChat: HTML del widget inyectado.");


        // 4. Cargar marked.js dinámicamente (si no está presente)
        if (typeof marked === "undefined") {
            console.log("CTAIChat: Cargando marked.js...");
            const scriptMarked = document.createElement("script");
            scriptMarked.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
            scriptMarked.onload = () => console.log("CTAIChat: marked.js cargado.");
            scriptMarked.onerror = () => console.error("CTAIChat: Error al cargar marked.js.");
            document.head.appendChild(scriptMarked);
        }

        // 5. Inyectar CSS si no está presente
        // Puedes agregar lógica para evitar duplicados si es necesario
        if (!document.querySelector('link[href="styles.css"]')) {
            console.log("CTAIChat: Aplicando estilos (styles.css)...");
            const styleLink = document.createElement("link");
            styleLink.rel = "stylesheet";
            styleLink.href = "styles.css"; // Asegúrate que la ruta sea correcta desde donde se sirve sdk.js
            document.head.appendChild(styleLink);
        } else {
             console.log("CTAIChat: styles.css ya parece estar en el DOM.");
        }


        // 6. Guardar configuración para app.js (accesible globalmente)
        console.log("CTAIChat: Estableciendo configuración global para app.js:", settings);
        window.CTAI_CONFIG = settings;

        // 7. Exponer API global simple para interacciones básicas (como el toggle)
        window.CTAIChat = {
            toggle: () => {
                const chat = document.getElementById("ctai-chat-container");
                if(chat) {
                    // Usamos !chat.style.display o 'none' para verificar el estado
                    const isHidden = !chat.style.display || chat.style.display === "none";
                    chat.style.display = isHidden ? "flex" : "none";
                    console.log("CTAIChat: Toggle visibility " + (isHidden ? "visible" : "hidden"));
                    // Si se abre, intentar cargar historial por si acaso no cargó antes o refrescar
                    if (isHidden && typeof window.loadHistory === 'function') {
                        // Espera un momento para que la interfaz se renderice antes de hacer scroll
                        setTimeout(() => window.loadHistory(), 100);
                    } else if (isHidden && typeof window.loadHistory !== 'function'){
                         console.warn("CTAI App: loadHistory no está disponible después del toggle.");
                    }

                } else {
                    console.error("CTAIChat: Contenedor 'ctai-chat-container' no encontrado para toggle.")
                }
            },
             // Este trigger simula el click del botón. app.js escuchará ese click.
            sendMessageTrigger: () => {
                const sendButton = document.getElementById("ctai-send-button");
                if (sendButton) {
                    sendButton.click(); // Esto dispara el listener de click en app.js
                    console.log("CTAIChat: Disparando evento de envío (simulando click)");
                } else {
                    console.error("CTAIChat: Botón 'ctai-send-button' no encontrado para trigger.")
                }
            }
            // Puedes añadir más funciones aquí si quieres exponerlas al usuario final,
            // que a su vez llamen a funciones en app.js (si app.js las expone).
        };
         console.log("CTAIChat: API global window.CTAIChat expuesta.");


        // 8. Inyectar app.js y llamar a su inicialización en el evento onload
        // Usamos una bandera global para evitar cargas múltiples si init se llamara varias veces
        if (!window.__CTAI_APP_LOADED__) {
            console.log("CTAIChat: Cargando app.js...");
            const scriptApp = document.createElement("script");
            scriptApp.src = "app.js"; // Asegúrate que la ruta sea correcta
            scriptApp.defer = true; // Defer carga y ejecución hasta que el DOM esté listo (pero nosotros llamaremos a init manualmente)
            // Dentro de la función scriptApp.onload en sdk.js
        scriptApp.onload = () => {
            window.__CTAI_APP_LOADED__ = true;
            console.log("CTAIChat: app.js cargado correctamente (script onload).");

            // --- Logs de depuración cruciales ---
            console.log("CTAIChat: Checking if window.initCTAIChatApp is a function from sdk.js onload..."); // <-- Log de contexto
            console.log("CTAIChat: typeof window.initCTAIChatApp is:", typeof window.initCTAIChatApp); // <-- Añadir este log
            console.log("CTAIChat: window.initCTAIChatApp value is:", window.initCTAIChatApp); // <-- Añadir este log
            console.log("CTAIChat: typeof window.sendMessage is:", typeof window.sendMessage); // <-- Añadir este log
                // -------------------------------------


            // ¡IMPORTANTE! Llamar a la función de inicialización de app.js AQUÍ
            if (typeof window.initCTAIChatApp === 'function') {
                console.log("CTAIChat: Llamando a window.initCTAIChatApp().");
                window.initCTAIChatApp();
            } else {
                console.error("CTAI App: window.initCTAIChatApp no encontrada después de cargar app.js. La lógica de la app no se inicializará.");
                    const chatMessages = document.getElementById("ctai-chat-messages");
                    // Intenta usar appendMessage si está disponible globalmente, si no, fallback
                    if (typeof window.appendMessage === 'function' && chatMessages) {
                        window.appendMessage("bot", "Error crítico: No se pudo inicializar la lógica del chat.");
                    } else if (chatMessages) {
                        chatMessages.innerHTML = "<div class='bot-message'>Error crítico: No se pudo cargar la lógica del chat.</div>";
                    }
            }
        };
            scriptApp.onerror = () => {
                console.error("CTAIChat: Error al cargar app.js.");
                window.__CTAI_APP_LOADED__ = false; // Resetear bandera en caso de error? Depende de la estrategia.
                // Muestra un error visible al usuario
                const chatMessages = document.getElementById("ctai-chat-messages");
                if (chatMessages) appendMessage("bot", "Error crítico: No se pudo cargar la lógica del chat.");
            }
            document.body.appendChild(scriptApp);
        } else {
             console.log("CTAIChat: app.js ya parece estar cargado (bandera __CTAI_APP_LOADED__ es true).");
             // Si ya estaba cargado, y el DOM ya está inyectado (porque init fue llamado),
             // podríamos intentar llamar a initCTAIChatApp de nuevo,
             // pero idealmente init solo se llama una vez.
             // Si init se llama de nuevo, debemos asegurar que initCTAIChatApp
             // sea idempotente (no duplique listeners, etc.)
             if (typeof window.initCTAIChatApp === 'function') {
                  console.log("CTAIChat: Re-llamando a window.initCTAIChatApp().");
                  window.initCTAIChatApp(); // Llama de nuevo, asumiendo idempotencia
             } else {
                  console.warn("CTAI App: app.js ya cargado pero window.initCTAIChatApp no encontrada.");
             }
        }
    } // Fin del método init
} // Fin de la clase CTAIWidget


// --- Lógica de Auto-Inicialización Revisada ---

// 1. Captura la referencia al script actual INMEDIATAMENTE
const currentSdkScript = document.currentScript;
let autoInitConfig = null; // Variable para guardar la config leída

// 2. Intenta leer los atributos data-* AHORA MISMO
// Solo intentamos auto-inicializar si hay un script tag válido y auto-init no es 'false'
if (currentSdkScript && currentSdkScript.dataset.autoInit !== "false") {
    console.log("CTAIChat: Intentando leer configuración desde atributos data-*...");
    autoInitConfig = {
        // Lee los atributos del dataset del script actual
        userId: currentSdkScript.dataset.userId,
        userKey: currentSdkScript.dataset.userKey,
        apiBase: currentSdkScript.dataset.apiBase,
        chatIconUrl: currentSdkScript.dataset.chatIconUrl,
        containerId: currentSdkScript.dataset.containerId
        // Añade otros atributos data-* que necesites aquí
    };
    // Validación temprana básica
    if (!autoInitConfig.userId || !autoInitConfig.userKey) {
       console.error("CTAIChat: (Pre-init) Faltan data-user-id o data-user-key en el tag <script>. La auto-inicialización será omitida.");
       autoInitConfig = null; // Anular config si falta algo esencial
    } else {
       console.log("CTAIChat: Configuración leída desde data-*:", autoInitConfig);
    }
} else if (!currentSdkScript) {
   console.warn("CTAIChat: document.currentScript es null. La auto-inicialización podría fallar si depende de data-*.");
} else {
    console.log("CTAIChat: Auto-inicialización deshabilitada explícitamente (data-auto-init='false').");
}


// 3. Espera a que el DOM esté listo (DOMContentLoaded) para inyectar el HTML y cargar app.js
// Esta parte es crucial porque necesitamos el DOM completo para añadir elementos.
document.addEventListener("DOMContentLoaded", () => {
    console.log("CTAIChat: DOMContentLoaded disparado en el documento principal.");
    // Llama a init SÓLO si capturamos una configuración válida previamente
    if (autoInitConfig) {
        console.log("CTAIChat: Llamando a CTAIWidget.init con configuración auto-detectada...");
        CTAIWidget.init(autoInitConfig);
    } else if (currentSdkScript?.dataset.autoInit !== "false") {
        // Si se esperaba auto-init pero falló la lectura de config
        console.warn("CTAIChat: No se pudo auto-inicializar debido a configuración faltante o incorrecta. Inicialice manualmente con CTAIWidget.init({...}).");
    } else {
        // Si auto-init estaba explícitamente deshabilitado
        console.log("CTAIChat: Auto-inicialización omitida según configuración.");
    }
});

console.log("CTAIChat: sdk.js ejecutado."); // Log final para saber que el script se cargó