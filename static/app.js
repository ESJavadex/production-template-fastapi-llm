const promptTextarea = document.getElementById('prompt');
const charCount = document.getElementById('charCount');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');
const responseSection = document.getElementById('responseSection');
const responseContent = document.getElementById('responseContent');
const metadata = document.getElementById('metadata');
const errorDiv = document.getElementById('error');

// Character counter
promptTextarea.addEventListener('input', () => {
    charCount.textContent = promptTextarea.value.length;
});

async function generate() {
    const prompt = promptTextarea.value.trim();

    if (!prompt) {
        showError('Por favor, escribe un prompt');
        return;
    }

    // Hide previous results and errors
    responseSection.style.display = 'none';
    errorDiv.style.display = 'none';

    // Show loading
    loading.style.display = 'block';
    generateBtn.disabled = true;

    const startTime = Date.now();

    try {
        // No timeout, no abort controller - let it hang!
        const response = await fetch(`http://localhost:8000/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt: prompt })
        });

        const latency = Date.now() - startTime;

        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Show response
        responseContent.textContent = data.output;
        metadata.innerHTML = `
            <strong>⏱️ Latencia:</strong> ${latency}ms<br>
            <strong>📊 Tokens estimados:</strong> ~${Math.ceil(data.output.length / 4)}<br>
            <strong>💰 Coste estimado:</strong> $${((prompt.length + data.output.length) / 4 * 0.00015 / 1000).toFixed(6)}<br>
            <strong>⚠️ Sin logs, sin límites, sin control</strong>
        `;

        responseSection.style.display = 'block';

    } catch (error) {
        showError(`💥 FALLÓ (como esperábamos): ${error.message}`);
    } finally {
        loading.style.display = 'none';
        generateBtn.disabled = false;
    }
}

function showError(message) {
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

// Allow Enter + Ctrl/Cmd to submit
promptTextarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        generate();
    }
});
