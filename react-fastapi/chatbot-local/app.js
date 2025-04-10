const API_BASE = "http://localhost:8000";

let userId = null;
let userKey = null;

// Verificar si marked está disponible
if (typeof marked === "undefined") {
    console.error("La librería marked no está cargada.");
} else {
    console.log("marked está listo para usarse.");
}

// Configurar el textarea que crece automáticamente
function setupAutoResizeTextarea() {
    const textarea = document.getElementById('user-input');
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
}

// Función para alternar la visibilidad del chat
function toggleChat() {
    const chatContainer = document.getElementById("chat-container");
    chatContainer.style.display = chatContainer.style.display === "none" ? "flex" : "none";
}



// Función para ocultar el spinner
function hideSpinner() {
    const spinner = document.getElementById("typing-spinner");
    if (spinner) spinner.remove();
}

// Función para hacer login
async function loginUser() {
    userId = document.getElementById("user-id").value.trim();
    userKey = document.getElementById("user-key").value.trim();

    if (!userId || !userKey) {
        alert("Por favor, ingresa usuario y clave.");
        return;
    }

    document.getElementById("login-box").style.display = "none";
    await loadHistory();
}

// Función para cargar el historial de mensajes
async function loadHistory() {
    try {
        console.log(`Cargando historial para usuario: ${userId}`); // Debug
        const response = await fetch(`${API_BASE}/history/${userId}`);
        
        console.log("Respuesta del servidor:", response); // Debug
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error("Error en la respuesta:", errorText); // Debug
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const history = await response.json();
        console.log("Historial recibido:", history); // Debug

        const chatMessages = document.getElementById("chat-messages");
        chatMessages.innerHTML = "";

        if (history.length === 0) {
            console.log("No hay historial para mostrar"); // Debug
            return;
        }

        history.forEach(msg => {
            console.log("Procesando mensaje:", msg); // Debug
            appendMessage(msg.role === "user" ? "user" : "bot", msg.content);
        });
    } catch (error) {
        console.error("Error cargando el historial:", error);
        appendMessage("bot", "No se pudo cargar el historial de mensajes.");
    }
}

// Función para añadir un mensaje al chat
function appendMessage(sender, message) {
    const chatMessages = document.getElementById("chat-messages");
    const msgDiv = document.createElement("div");
    msgDiv.classList.add(sender === "user" ? "user-message" : "bot-message");
    
    msgDiv.textContent = message;
    chatMessages.appendChild(msgDiv);
    
    if (sender === "bot" && typeof marked !== "undefined") {
        requestAnimationFrame(() => {
            msgDiv.innerHTML = marked.parse(message);
        });
    }
    
    requestAnimationFrame(() => {
        const container = document.getElementById("messages-container");
        container.scrollTop = container.scrollHeight;
    });
}


async function sendMessage() {
    const userInput = document.getElementById('user-input');
    const message = userInput.value.trim();

    if (!message || !userId || !userKey) return;

    appendMessage('user', message);
    userInput.value = '';
    userInput.style.height = 'auto';

    // Mostrar spinner que gira independientemente
    showSpinner();
    let spinnerVisible = true;

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_query: message,
                user_id: userId,
                cliente_clave: userKey
            })
        });

        if (!response.ok) throw new Error(await response.text());

        const chatMessages = document.getElementById('chat-messages');
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('bot-message');
        chatMessages.appendChild(msgDiv);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let botResponse = '';

        // Función para procesar chunks
        const processChunk = ({ done, value }) => {
            if (done) return true;

            const chunk = decoder.decode(value, { stream: true });
            botResponse += chunk;

            // Ocultar spinner al primer contenido válido
            if (spinnerVisible && chunk.trim().length > 0) {
                hideSpinner();
                spinnerVisible = false;
            }

            // Actualizar mensaje
            if (typeof marked !== 'undefined') {
                msgDiv.innerHTML = marked.parse(botResponse);
            } else {
                msgDiv.textContent = botResponse;
            }

            return false;
        };

        // Procesamiento optimizado
        while (true) {
            const { done, value } = await reader.read();
            if (processChunk({ done, value })) break;
            
            // Scroll suave sin bloquear
            requestAnimationFrame(() => {
                const container = document.getElementById('messages-container');
                container.scrollTop = container.scrollHeight;
            });
        }
    } catch (error) {
        console.error('Error:', error);
        if (spinnerVisible) hideSpinner();
        appendMessage('bot', 'Error al generar respuesta');
    }
}

// Funciones del spinner mejoradas
function showSpinner() {
    const chatMessages = document.getElementById('chat-messages');
    const existingSpinner = document.getElementById('typing-spinner');
    if (existingSpinner) return;

    const spinner = document.createElement('div');
    spinner.id = 'typing-spinner';
    spinner.className = 'typing-spinner';
    
    // Forzar layer de composición para animación suave
    spinner.style.transform = 'translateZ(0)';
    
    chatMessages.appendChild(spinner);
}

function hideSpinner() {
    const spinner = document.getElementById('typing-spinner');
    if (spinner) {
        spinner.style.opacity = '0';
        setTimeout(() => spinner.remove(), 200); // Suavizar desaparición
    }
}

// Evento cuando el DOM está cargado
document.addEventListener('DOMContentLoaded', function() {
    setupAutoResizeTextarea();
    
    // Evento para enviar con Enter (sin Shift)
    document.getElementById("user-input").addEventListener("keydown", function(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            document.getElementById("send-button").click(); // Simular click en el botón
        }
    });
    
    // Asegurar que el textarea no se solape con el botón
    document.getElementById("user-input").style.paddingRight = "40px";
});

