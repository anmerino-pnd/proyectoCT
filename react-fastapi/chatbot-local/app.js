// app.js

// Configura la URL base de tu API backend - Ahora se espera que venga de la configuración
let API_BASE = "https://10.10.251.160:8000"; // Valor por defecto (puede ser sobreescrito por config)

let userId = null;
let userKey = null;

// NOTA: La comprobación inicial de marked no es estrictamente necesaria aquí
// ya que sdk.js lo carga y appendMessage comprueba antes de usar.

// Configurar el textarea que crece automáticamente
function setupAutoResizeTextarea() {
    const textarea = document.getElementById('ctai-user-input');
    if (!textarea) {
         console.warn("CTAI App: Textarea #ctai-user-input no encontrado para auto-resize.");
        return; // Salir si el textarea no existe
    }
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    // Asegurar que el textarea no se solape con el botón
    textarea.style.paddingRight = "40px";
     console.log("CTAI App: Auto-resize setup done.");
}

// Función para alternar la visibilidad del chat (Expuesta globalmente por SDK)
// No necesitamos definirla aquí si el SDK ya la maneja en el global CTAIChat
// Pero si quisieras llamarla desde app.js, debería estar aquí.
// En este setup, el SDK manejará el toggle.

// Función para añadir un mensaje al chat
function appendMessage(sender, message) {
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) {
        console.error("CTAI App: Contenedor de mensajes #ctai-chat-messages no encontrado.");
        return;
    }
    const msgDiv = document.createElement("div");
    msgDiv.classList.add(sender === "user" ? "user-message" : "bot-message");
    msgDiv.textContent = message; // Poner texto plano primero

    // Parsear como Markdown SOLO si es del bot Y marked está cargado
    if (sender === "bot") {
        requestAnimationFrame(() => {
            // Comprobación al momento de renderizar
            if (typeof marked !== "undefined") {
                try {
                    msgDiv.innerHTML = marked.parse(message);
                     // console.log("CTAI App: Mensaje de bot parseado con marked.");
                } catch (e) {
                    console.error("CTAI App: Error al parsear Markdown:", e);
                    msgDiv.textContent = message; // Fallback a texto plano
                }
            } else {
                // Si marked aún no carga, se queda como texto plano.
                // Esto es menos ideal pero evita errores.
                 console.warn("CTAI App: marked library not available for bot message rendering.");
            }
        });
    }

    chatMessages.appendChild(msgDiv);

    // Scroll (usa el ID correcto del contenedor)
    requestAnimationFrame(() => {
        const container = document.getElementById("ctai-messages-container");
        if(container) container.scrollTop = container.scrollHeight;
        else console.warn("CTAI App: Contenedor de scroll #ctai-messages-container no encontrado.");
    });
     console.log(`CTAI App: Mensaje de ${sender} añadido.`);
}

// Función para inicializar datos desde la configuración global
function initializeChatbotData() {
    if (!window.CTAI_CONFIG) {
      console.error("CTAI App: Configuración (window.CTAI_CONFIG) no encontrada.");
      return false;
    }

    userId = window.CTAI_CONFIG.userId;
    userKey = window.CTAI_CONFIG.userKey;
    // Usa la base de la API de la config, si existe
    API_BASE = window.CTAI_CONFIG.apiBase || API_BASE;

    if (!userId || !userKey) {
        console.error("CTAI App: Configuración incompleta. Faltan userId o userKey.");
        return false;
    }

    console.log("CTAI App: Inicializado con UserID:", userId);
    // console.log("CTAI App: Usando API_BASE:", API_BASE);
    return true;
}


// Función para cargar el historial de mensajes
async function loadHistory() {
    if (!userId) {
        console.warn("CTAI App: Intento de cargar historial sin userId.");
        return;
    }
    try {
        console.log(`CTAI App: Cargando historial para usuario: ${userId}`);
        const response = await fetch(`${API_BASE}/history/${userId}`);
         // console.log("CTAI App: Respuesta del servidor (historial):", response);

        if (!response.ok) {
             const errorText = await response.text();
             console.error("CTAI App: Error en la respuesta del historial:", response.status, errorText);
             // Intenta parsear JSON si es posible, si no, usa el texto
             let errorMessage = errorText;
             try {
                 const errorJson = JSON.parse(errorText);
                 if (errorJson.detail) errorMessage = errorJson.detail; // Ejemplo si tu API usa FastAPI
             } catch (e) {
                 // Ignorar error de parseo, usar texto plano
             }
            throw new Error(`HTTP error! status: ${response.status}. ${errorMessage}`);
        }

        const history = await response.json();
        console.log("CTAI App: Historial recibido:", history);

        const chatMessages = document.getElementById("ctai-chat-messages");
        if (!chatMessages) return;
        chatMessages.innerHTML = ""; // Limpiar mensajes previos

        if (!Array.isArray(history) || history.length === 0) {
            console.log("CTAI App: No hay historial para mostrar o formato incorrecto");
            appendMessage("bot", "¡Hola! ¿En qué puedo ayudarte hoy?"); // Mensaje inicial si no hay historial
            return;
        }

        history.forEach(msg => {
            if (msg && msg.role && msg.content) {
                // console.log("CTAI App: Procesando mensaje de historial:", msg);
                appendMessage(msg.role === "user" ? "user" : "bot", msg.content);
            } else {
                 console.warn("CTAI App: Mensaje de historial con formato inesperado:", msg);
            }
        });
         console.log("CTAI App: Historial cargado y mostrado.");
    } catch (error) {
        console.error("CTAI App: Error cargando el historial:", error);
        appendMessage("bot", "No se pudo cargar el historial de mensajes.");
    }
}

// Funciones del spinner (sin cambios)
function showSpinner() {
    const chatMessages = document.getElementById('ctai-chat-messages');
    if (!chatMessages) return;
    const existingSpinner = document.getElementById('typing-spinner');
    if (existingSpinner) return; // Ya existe uno

    const spinner = document.createElement('div');
    spinner.id = 'typing-spinner';
    spinner.className = 'typing-spinner'; // Asegúrate que esta clase exista en tu CSS
    spinner.style.transform = 'translateZ(0)'; // Hint para performance
    chatMessages.appendChild(spinner);
     console.log("CTAI App: Spinner mostrado.");
}

function hideSpinner() {
    const spinner = document.getElementById('typing-spinner');
    if (spinner) {
        spinner.style.opacity = '0'; // Desvanecer
        // Usar requestAnimationFrame + setTimeout para asegurar que la transición funciona
        requestAnimationFrame(() => {
             setTimeout(() => spinner.remove(), 300); // Eliminar después de la transición (ajusta el tiempo a tu CSS)
        });
         console.log("CTAI App: Spinner ocultado.");
    }
}

// Función para enviar mensajes (sin cambios significativos en la lógica de fetch)
async function sendMessage() {
    const userInput = document.getElementById('ctai-user-input');
    if (!userInput) {
        console.error("CTAI App: Input de usuario #ctai-user-input no encontrado.");
        return;
    }
    const message = userInput.value.trim();

    if (!message || !userId || !userKey) {
        console.warn("CTAI App: Intento de enviar mensaje sin datos completos:", { message, userId, userKey });
        // Podrías mostrar un mensaje al usuario aquí si falta algo
        return;
    }

    appendMessage('user', message);
    userInput.value = ''; // Limpiar input
    userInput.style.height = 'auto'; // Resetear altura

    showSpinner();
    let spinnerVisible = true;

    try {
        console.log("CTAI App: Enviando mensaje...");
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                 // Considera añadir headers de autenticación si tu API los requiere
                 // 'X-User-ID': userId,
                 // 'X-User-Key': userKey,
            },
            body: JSON.stringify({
                user_query: message,
                user_id: userId,
                cliente_clave: userKey
            })
        });

        if (!response.ok) {
             const errorText = await response.text();
             console.error("CTAI App: Error en respuesta del chat:", response.status, errorText);
              let errorMessage = errorText;
              try {
                  const errorJson = JSON.parse(errorText);
                  if (errorJson.detail) errorMessage = errorJson.detail;
              } catch (e) {} // Ignorar error de parseo
             throw new Error(errorMessage || `HTTP error ${response.status}`);
        }

        const chatMessages = document.getElementById('ctai-chat-messages');
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('bot-message');
        chatMessages.appendChild(msgDiv);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let botResponse = '';
        let firstChunkReceived = false;

        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                console.log("CTAI App: Stream finalizado.");
                break;
            }

            const chunk = decoder.decode(value, { stream: true });

            if (!firstChunkReceived && chunk.trim().length > 0) {
                hideSpinner();
                spinnerVisible = false;
                firstChunkReceived = true;
                 console.log("CTAI App: Primer chunk recibido, ocultando spinner.");
            }

            botResponse += chunk;

            if (typeof marked !== 'undefined') {
                msgDiv.innerHTML = marked.parse(botResponse);
            } else {
                msgDiv.textContent = botResponse;
            }

            requestAnimationFrame(() => {
                const container = document.getElementById("ctai-messages-container");
                if(container) container.scrollTop = container.scrollHeight;
            });
        }

        if (spinnerVisible) { // Ocultar si no hubo chunks
            hideSpinner();
        }
         console.log("CTAI App: Mensaje recibido y mostrado.");

    } catch (error) {
        console.error('CTAI App: Error en sendMessage:', error);
        if (spinnerVisible) hideSpinner();
        appendMessage('bot', `Error al obtener respuesta: ${error.message || 'Error desconocido'}`);
    }
}

// --- Nueva función de Inicialización de la Lógica ---
// Esta función será llamada por el SDK después de inyectar el DOM y cargar app.js
window.initCTAIChatApp = function() {
    console.log("CTAI App: initCTAIChatApp llamada.");
    // 1. Inicializar datos desde la configuración global
    if (!initializeChatbotData()) {
        console.error("CTAI App: Falló la inicialización de datos. La aplicación no puede continuar.");
         // Podrías mostrar un mensaje de error permanente en el chat
         appendMessage("bot", "Error crítico: Faltan datos de configuración (userId o userKey).");
        return; // Detener si la inicialización de datos falla
    }

    // 2. Configurar listeners y elementos DOM que dependen de que el HTML esté inyectado
    setupAutoResizeTextarea();

    // Configurar evento para enviar con Enter (sin Shift)
    const userInput = document.getElementById('ctai-user-input');
    const sendButton = document.getElementById("ctai-send-button");

    if (userInput && sendButton) {
        userInput.addEventListener("keydown", function(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault(); // Prevenir salto de línea
                // Llamar directamente a sendMessage
                 console.log("CTAI App: Enter presionado (sin Shift). Llamando sendMessage.");
                 sendMessage();
            }
        });

        // Configurar evento click para el botón de enviar
        sendButton.addEventListener("click", function() {
             console.log("CTAI App: Botón de enviar clickeado. Llamando sendMessage.");
            sendMessage();
        });
         console.log("CTAI App: Event listeners para input y botón configurados.");

    } else {
         console.error("CTAI App: Input de usuario o botón de enviar no encontrados al intentar configurar listeners.");
    }

    // 3. Cargar historial
    loadHistory();

    console.log("CTAI App: Inicialización de lógica completada.");
};

console.log("CTAI App: app.js finished parsing.");
console.log("CTAI App: window.initCTAIChatApp type is:", typeof window.initCTAIChatApp);
console.log("CTAI App: window.initCTAIChatApp value is:", window.initCTAIChatApp); // <-- Añadir este log
console.log("CTAI App: window.sendMessage type is:", typeof window.sendMessage); // <-- Añadir este log