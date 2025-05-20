
let userId = null;
let userKey = null;

function setupAutoResizeTextarea() {
    const textarea = document.getElementById('ctai-user-input');
    if (!textarea) return;
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    textarea.style.paddingRight = "40px";
}

function appendMessage(sender, message) {
    const chatMessages = document.getElementById("ctai-chat-messages");
    if (!chatMessages) return;
    const msgDiv = document.createElement("div");
    msgDiv.classList.add(sender === "user" ? "user-message" : "bot-message");
    msgDiv.textContent = message;
    if (sender === "bot") {
        requestAnimationFrame(() => {
             if (typeof marked !== "undefined") {
                 try {
                     if (msgDiv.parentNode) {
                         msgDiv.innerHTML = marked.parse(message);
                     } else {}
                 } catch (e) {
                     msgDiv.textContent = message;
                 }
             } else {}
        });
    }
    chatMessages.appendChild(msgDiv);
    requestAnimationFrame(() => {
        const container = document.getElementById("ctai-messages-container");
        if(container) container.scrollTop = container.scrollHeight;
        else {}
    });
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
        const response = await fetch(`${API_BASE}/history?usuario=${userId}`);
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

        const responseData = await response.json();
        console.log("Respuesta del servidor:", responseData);
        if (responseData.estatus !== "success" || !Array.isArray(responseData.datos)) {
            appendMessage("bot", "¡Hola! ¿En qué puedo ayudarte hoy?");
            return;
        }

        const history = responseData.datos;

        if (history.length === 0) {
            appendMessage("bot", "¡Hola! ¿En qué puedo ayudarte hoy?");
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

async function sendMessage() {
    const userInput = document.getElementById('ctai-user-input');
    if (!userInput) return;
    const message = userInput.value.trim();
    appendMessage('user', message);
    userInput.value = '';
    userInput.style.height = 'auto';
    showSpinner();
    let spinnerVisible = true;
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_query: message,
                user_id: userId,
                listaPrecio: userKey
            })
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
            throw new Error(errorMessage || `HTTP error ${response.status}`);
        }

        const responseData = await response.json();

        if (responseData.estatus === "success" && responseData.datos) {
            const botResponse = responseData.datos;

            if (spinnerVisible) hideSpinner();
            spinnerVisible = false;

            const chatMessages = document.getElementById('ctai-chat-messages');
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('bot-message');

            if (chatMessages) {
                 chatMessages.appendChild(msgDiv);
            } else {
                 if (spinnerVisible) hideSpinner();
                 return;
            }

            if (typeof marked !== 'undefined') {
                 if (msgDiv.parentNode) {
                      msgDiv.innerHTML = marked.parse(botResponse);
                 } else {
                      msgDiv.textContent = botResponse;
                 }
            } else {
                msgDiv.textContent = botResponse;
            }

            requestAnimationFrame(() => {
                const container = document.getElementById("ctai-messages-container");
                 if(container) container.scrollTop = container.scrollHeight;
            });

        } else {
            if (spinnerVisible) hideSpinner();
            spinnerVisible = false;
            const errorMessage = responseData.mensaje || JSON.stringify(responseData) || 'Respuesta inesperada del servidor.';
            appendMessage('bot', `Error en la respuesta del servidor: ${errorMessage}`);
        }

    } catch (error) {
        if (spinnerVisible) hideSpinner();
        appendMessage('bot', `Error al obtener respuesta: ${error.message || 'Error desconocido'}`);
    }
    if (spinnerVisible) hideSpinner();
}

async function deleteConversation() {
    if (!userId || !API_BASE) {
        appendMessage("bot", "Error: No se pudo eliminar la conversación debido a configuración faltante.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/delete-history?usuario=${userId}`, { method: 'DELETE' });
        if (response.status === 204 || response.status === 200) {
            const chatMessages = document.getElementById("ctai-chat-messages");
            if (chatMessages) {
                chatMessages.innerHTML = "";
                appendMessage("bot", "¡Hola! ¿En qué puedo ayudarte hoy?");
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
            sendMessage();
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