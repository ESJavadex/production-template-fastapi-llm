const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// Store conversation history
let conversationHistory = [];

async function sendMessage() {
    const message = userInput.value.trim();

    if (!message) return;

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
            throw new Error('Error en la respuesta del servidor');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        break;
                    }

                    try {
                        const parsed = JSON.parse(data);
                        fullResponse += parsed.content;
                        updateBotMessage(botMessageDiv, fullResponse);
                    } catch (e) {
                        // Skip invalid JSON
                    }
                }
            }
        }

        // Add bot response to conversation history
        conversationHistory.push({ role: 'assistant', content: fullResponse });

    } catch (error) {
        updateBotMessage(botMessageDiv, 'Error: No se pudo obtener respuesta');
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

// Allow Enter to submit
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
