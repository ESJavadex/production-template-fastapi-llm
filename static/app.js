const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

async function sendMessage() {
    const message = userInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    userInput.value = '';

    // Disable button while waiting
    sendBtn.disabled = true;

    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error('Error en la respuesta del servidor');
        }

        const data = await response.json();

        // Add bot response to chat
        addMessage(data.response, 'bot');

    } catch (error) {
        addMessage('Error: No se pudo obtener respuesta', 'bot');
    } finally {
        sendBtn.disabled = false;
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

// Allow Enter to submit
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
