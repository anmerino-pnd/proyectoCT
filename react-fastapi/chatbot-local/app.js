let API_BASE = "http://10.10.251.160:8000"; 

let userId = null;
let userKey = null;


function setupAutoResizeTextarea() {
    const textarea = document.getElementById('ctai-user-input');
    if (!textarea) {
         console.warn("CTAI App: Textarea #ctai-user-input no encontrado para auto-resize.");
        return; 
    }
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    textarea.style.paddingRight = "40px";
}

function appendMessage(sender, message) {
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) {
        console.error("CTAI App: Contenedor de mensajes #ctai-chat-messages no encontrado.");
        return;
    }
    const msgDiv = document.createElement("div");
    msgDiv.classList.add(sender === "user" ? "user-message" : "bot-message");
    msgDiv.textContent = message; 

    if (sender === "bot") {
        requestAnimationFrame(() => {
            if (typeof marked !== "undefined") {
                try {
                    msgDiv.innerHTML = marked.parse(message);
                } catch (e) {
                    console.error("CTAI App: Error al parsear Markdown:", e);
                    msgDiv.textContent = message; // Fallback a texto plano
                }
            } else {
                 console.warn("CTAI App: marked library not available for bot message rendering.");
            }
        });
    }

    chatMessages.appendChild(msgDiv);

    requestAnimationFrame(() => {
        const container = document.getElementById("ctai-messages-container");
        if(container) container.scrollTop = container.scrollHeight;
        else console.warn("CTAI App: Contenedor de scroll #ctai-messages-container no encontrado.");
    });
}

function initializeChatbotData() {
    if (!window.CTAI_CONFIG) {
      console.error("CTAI App: Configuración (window.CTAI_CONFIG) no encontrada.");
      return false;
    }

    userId = window.CTAI_CONFIG.userId;
    userKey = window.CTAI_CONFIG.userKey;
    
    API_BASE = window.CTAI_CONFIG.apiBase || API_BASE;

    if (!userId || !userKey) {
        console.error("CTAI App: Configuración incompleta. Faltan userId o userKey.");
        return false;
    }
    return true;
}


async function loadHistory() {
    if (!userId) {
        console.warn("CTAI App: Intento de cargar historial sin userId.");
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/history/${userId}`);

        if (!response.ok) {
             const errorText = await response.text();
             console.error("CTAI App: Error en la respuesta del historial:", response.status, errorText);
             let errorMessage = errorText;
             try {
                 const errorJson = JSON.parse(errorText);
                 if (errorJson.detail) errorMessage = errorJson.detail; 
             } catch (e) {
                 
             }
            throw new Error(`HTTP error! status: ${response.status}. ${errorMessage}`);
        }

        const history = await response.json();

        const chatMessages = document.getElementById("ctai-chat-messages");
        if (!chatMessages) return;
        chatMessages.innerHTML = ""; 

        if (!Array.isArray(history) || history.length === 0) {
            appendMessage("bot", "¡Hola! ¿En qué puedo ayudarte hoy?"); 
            return;
        }

        history.forEach(msg => {
            if (msg && msg.role && msg.content) {
                appendMessage(msg.role === "user" ? "user" : "bot", msg.content);
            } else {
                 console.warn("CTAI App: Mensaje de historial con formato inesperado:", msg);
            }
        });
    } catch (error) {
        console.error("CTAI App: Error cargando el historial:", error);
        appendMessage("bot", "No se pudo cargar el historial de mensajes.");
    }
}

function showSpinner() {
    const chatMessages = document.getElementById('ctai-chat-messages');
    if (!chatMessages) return;
    const existingSpinner = document.getElementById('typing-spinner');
    if (existingSpinner) return; 

    const spinner = document.createElement('div');
    spinner.id = 'typing-spinner';
    spinner.className = 'typing-spinner'; 
    spinner.style.transform = 'translateZ(0)'; 
    chatMessages.appendChild(spinner);
}

function hideSpinner() {
    const spinner = document.getElementById('typing-spinner');
    if (spinner) {
        spinner.style.opacity = '0'; 
        requestAnimationFrame(() => {
             setTimeout(() => spinner.remove(), 300); 
        });
    }
}

async function sendMessage() {
    const userInput = document.getElementById('ctai-user-input');
    if (!userInput) {
        console.error("CTAI App: Input de usuario #ctai-user-input no encontrado.");
        return;
    }
    const message = userInput.value.trim();

    if (!message || !userId || !userKey) {
        console.warn("CTAI App: Intento de enviar mensaje sin datos completos:", { message, userId, userKey });
        return;
    }

    appendMessage('user', message);
    userInput.value = ''; 
    userInput.style.height = 'auto'; 

    showSpinner();
    let spinnerVisible = true;

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_query: message,
                user_id: userId,
                listaPrecio: userKey
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
                break;
            }

            const chunk = decoder.decode(value, { stream: true });

            if (!firstChunkReceived && chunk.trim().length > 0) {
                hideSpinner();
                spinnerVisible = false;
                firstChunkReceived = true;
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

    } catch (error) {
        console.error('CTAI App: Error en sendMessage:', error);
        if (spinnerVisible) hideSpinner();
        appendMessage('bot', `Error al obtener respuesta: ${error.message || 'Error desconocido'}`);
    }
}


window.initCTAIChatApp = function() {
    if (!initializeChatbotData()) {
        console.error("CTAI App: Falló la inicialización de datos. La aplicación no puede continuar.");
         appendMessage("bot", "Error crítico: Faltan datos de configuración (userId o userKey).");
        return;
    }

   
    setupAutoResizeTextarea();


    const userInput = document.getElementById('ctai-user-input');
    const sendButton = document.getElementById("ctai-send-button");

    if (userInput && sendButton) {
        userInput.addEventListener("keydown", function(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault(); 
                 sendMessage();
            }
        });


        sendButton.addEventListener("click", function() {
            sendMessage();
        });

    } else {
         console.error("CTAI App: Input de usuario o botón de enviar no encontrados al intentar configurar listeners.");
    }

    loadHistory();

};

