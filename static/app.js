const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const charCount = document.getElementById('charCount');
const errorMessage = document.getElementById('errorMessage');

// Security and validation constants
const MAX_CHARS = 4000;  // ~1000 tokens
const MAX_MESSAGES = 50;
const FORBIDDEN_PATTERNS = [
    /system\s*:/i,
    /assistant\s*:/i,
    /ignore\s+(previous|prior)\s+instructions/i,
    /forget\s+your\s+prompt/i,
    /<script/i,
    /<iframe/i,
    /javascript:/i,
    /on\w+\s*=/i,  // onclick, onerror, etc.
];

// Store conversation history
let conversationHistory = [];

function sanitizeInput(text) {
    /**
     * Sanitize user input to prevent XSS and injection attacks.
     */
    // Remove null bytes
    text = text.replace(/\x00/g, '');

    // Remove control characters (except newlines, tabs)
    text = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

    // Normalize whitespace
    text = text.replace(/\s+/g, ' ').trim();

    // HTML escape
    const div = document.createElement('div');
    div.textContent = text;
    text = div.innerHTML;

    return text;
}

function validateInput(message) {
    /**
     * Validate input against security rules.
     * Returns {valid: boolean, error: string}
     */

    // Check if empty
    if (!message || message.trim().length === 0) {
        return {valid: false, error: 'El mensaje no puede estar vacío'};
    }

    // Check length
    if (message.length > MAX_CHARS) {
        return {valid: false, error: `El mensaje excede el límite de ${MAX_CHARS} caracteres`};
    }

    // Check conversation history limit
    if (conversationHistory.length >= MAX_MESSAGES) {
        return {valid: false, error: 'Se alcanzó el límite de mensajes. Por favor, recarga la página.'};
    }

    // Check for forbidden patterns (prompt injection attempts)
    for (const pattern of FORBIDDEN_PATTERNS) {
        if (pattern.test(message)) {
            return {
                valid: false,
                error: 'El mensaje contiene patrones no permitidos. Por favor, reformula tu pregunta.'
            };
        }
    }

    // Check for excessive special characters (potential injection)
    const specialCharCount = (message.match(/[<>{}[\]\\`|]/g) || []).length;
    if (specialCharCount > 20) {
        return {
            valid: false,
            error: 'El mensaje contiene demasiados caracteres especiales'
        };
    }

    return {valid: true, error: null};
}

function showError(message) {
    /**
     * Display error message to user.
     */
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function updateCharCount() {
    /**
     * Update character counter display.
     */
    const length = userInput.value.length;
    charCount.textContent = `${length}/${MAX_CHARS}`;

    // Change color based on usage
    if (length > MAX_CHARS * 0.9) {
        charCount.style.color = '#e74c3c';  // Red
    } else if (length > MAX_CHARS * 0.7) {
        charCount.style.color = '#f39c12';  // Orange
    } else {
        charCount.style.color = '#95a5a6';  // Gray
    }

    // Disable send button if over limit
    sendBtn.disabled = length > MAX_CHARS || length === 0;
}

async function sendMessage() {
    const rawMessage = userInput.value;

    // Validate input
    const validation = validateInput(rawMessage);
    if (!validation.valid) {
        showError(validation.error);
        return;
    }

    // Sanitize input
    const message = sanitizeInput(rawMessage);

    if (!message) {
        showError('El mensaje no puede estar vacío');
        return;
    }

    // Hide any previous error
    errorMessage.style.display = 'none';

    // Add user message to chat
    addMessage(message, 'user');

    // Add to conversation history
    conversationHistory.push({ role: 'user', content: message });

    // Clear input
    userInput.value = '';

    // Disable button while waiting
    sendBtn.disabled = true;

    // Create empty bot message that will be filled with streaming response
    const botMessageDiv = createBotMessage();
    let fullResponse = '';

    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ messages: conversationHistory })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail || 'Error en la respuesta del servidor';
            throw new Error(errorMsg);
        }

        // Parse JSON response (non-streaming)
        const data = await response.json();
        fullResponse = data.content;

        // Update bot message with full response
        updateBotMessage(botMessageDiv, fullResponse);

        // Add bot response to conversation history
        conversationHistory.push({ role: 'assistant', content: fullResponse });

    } catch (error) {
        console.error('Error:', error);
        updateBotMessage(botMessageDiv, 'Error: No se pudo obtener respuesta. Por favor, intenta de nuevo.');
        showError('Error de conexión. Por favor, intenta de nuevo.');
    } finally {
        updateCharCount();  // Re-enable button based on input
        userInput.focus();
    }
}

function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const label = type === 'user' ? 'Tú' : 'Bot';

    // Parse markdown for bot messages
    if (type === 'bot') {
        const parsedContent = marked.parse(text);
        messageDiv.innerHTML = `<strong>${label}:</strong><div class="markdown-content">${parsedContent}</div>`;
    } else {
        messageDiv.innerHTML = `<strong>${label}:</strong> ${text}`;
    }

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function createBotMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.innerHTML = `<strong>Bot:</strong><div class="markdown-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return messageDiv;
}

function updateBotMessage(messageDiv, text) {
    const parsedContent = marked.parse(text);
    const contentDiv = messageDiv.querySelector('.markdown-content');
    contentDiv.innerHTML = parsedContent;
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Update character count on input
userInput.addEventListener('input', updateCharCount);

// Allow Enter to submit (not Shift+Enter for multiline)
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) {
            sendMessage();
        }
    }
});

// Prevent paste of excessively long content
userInput.addEventListener('paste', (e) => {
    setTimeout(() => {
        if (userInput.value.length > MAX_CHARS) {
            userInput.value = userInput.value.substring(0, MAX_CHARS);
            showError(`El texto pegado se truncó al límite de ${MAX_CHARS} caracteres`);
        }
        updateCharCount();
    }, 10);
});

// Initialize character counter
updateCharCount();
