# Demo 1 — Microservicio de IA "Production-Ready"

## 🎯 Objetivo
Transformar el chatbot básico en un microservicio robusto con todas las guardrails de producción.

---

## 📋 Arquitectura Mínima (Slide 3)

### Componentes clave:
1. **FastAPI con endpoints estructurados**
   - `/health` - Health check
   - `/generate` - Generación con LLM

2. **Seguridad**
   - Variables de entorno (`.env`)
   - Sin claves hardcodeadas

3. **Límites y validación**
   - Límite de entrada (MAX_CHARS ≈ tokens)
   - Validación de payloads

4. **Resiliencia**
   - Reintentos (429/5xx)
   - Timeouts
   - Manejo de errores

5. **Observabilidad**
   - Logging estructurado (JSON)
   - Métricas: tokens, coste, latencia
   - Request tracking (request_id)

6. **Cálculo de costes**
   - tokens_in/out × tarifa
   - Tracking por request

---

## 🛠️ Pasos de Implementación

### 1. Estructura Base de FastAPI

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import os
import time
import hashlib
import logging
import json
from typing import Optional
import uuid

app = FastAPI(title="Production LLM Service", version="1.0.0")

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)
```

### 2. Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    """Health check endpoint para load balancers"""
    return {
        "status": "healthy",
        "service": "llm-service",
        "timestamp": time.time()
    }
```

### 3. Configuración y Límites

```python
# Configuración
MAX_CHARS = 4000  # ~1000 tokens aprox
MAX_RETRIES = 3
RETRY_DELAY = 1  # segundos
TIMEOUT = 30  # segundos

# Costes (GPT-4o-mini)
COST_PER_1M_INPUT_TOKENS = 0.15
COST_PER_1M_OUTPUT_TOKENS = 0.60
```

### 4. Modelo de Request con Validación

```python
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_CHARS)
    model: str = Field(default="gpt-4o-mini")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=4000)

    @validator('prompt')
    def validate_prompt(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Prompt no puede estar vacío')
        return v
```

### 5. Función de Cálculo de Coste

```python
def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calcula el coste de la llamada al LLM"""
    input_cost = (input_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost = (output_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    return round(input_cost + output_cost, 6)
```

### 6. Función con Reintentos

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((Exception,))
)
def call_llm_with_retry(client, model: str, prompt: str, temperature: float, max_tokens: int):
    """Llama al LLM con reintentos exponenciales"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=TIMEOUT
    )
    return response
```

### 7. Logging Estructurado

```python
def log_request(request_id: str, prompt: str, response_text: str,
                tokens_in: int, tokens_out: int, latency_ms: float, cost: float):
    """Log estructurado en JSON"""

    # Hash del prompt para privacidad
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

    log_data = {
        "request_id": request_id,
        "timestamp": time.time(),
        "latency_ms": round(latency_ms, 2),
        "prompt_hash": prompt_hash,
        "prompt_length": len(prompt),
        "response_length": len(response_text),
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "cost_usd": cost,
        "model": "gpt-4o-mini"
    }

    logger.info(json.dumps(log_data))
```

### 8. Endpoint /generate Completo

```python
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/generate")
async def generate(request: GenerateRequest, req: Request):
    """Endpoint principal de generación con todas las guardrails"""

    request_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # Validar longitud
        if len(request.prompt) > MAX_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Prompt excede el límite de {MAX_CHARS} caracteres"
            )

        # Llamar al LLM con reintentos
        response = call_llm_with_retry(
            client=client,
            model=request.model,
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        # Extraer métricas
        response_text = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens

        # Calcular coste
        cost = calculate_cost(tokens_in, tokens_out)

        # Calcular latencia
        latency_ms = (time.time() - start_time) * 1000

        # Log estructurado
        log_request(
            request_id=request_id,
            prompt=request.prompt,
            response_text=response_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost=cost
        )

        # Respuesta estructurada
        return {
            "request_id": request_id,
            "output": response_text,
            "metadata": {
                "model": request.model,
                "tokens": {
                    "input": tokens_in,
                    "output": tokens_out,
                    "total": tokens_in + tokens_out
                },
                "cost_usd": cost,
                "latency_ms": round(latency_ms, 2)
            }
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error(f"Error en request {request_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor. Por favor, intenta de nuevo."
        )
```

### 9. Manejo de Rate Limits (429)

```python
from fastapi import status

@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    """Manejo personalizado de excepciones"""

    # Rate limit de OpenAI
    if "429" in str(exc) or "rate_limit" in str(exc).lower():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit excedido",
                "message": "Por favor, intenta de nuevo en unos segundos",
                "retry_after": 5
            },
            headers={"Retry-After": "5"}
        )

    # Error genérico
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Error interno", "message": str(exc)}
    )
```

---

## 🧪 Pruebas

### 1. Instalar dependencias adicionales

```bash
pip install tenacity
```

Actualizar `requirements.txt`:
```
fastapi
uvicorn
openai
python-dotenv
tenacity
```

### 2. Prueba con curl

```bash
# Health check
curl http://localhost:8000/health

# Generación simple
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explica qué es FastAPI en 2 líneas",
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### 3. Prueba de límites

```bash
# Prompt muy largo (debe fallar)
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$(python -c 'print("a" * 5000)')\"}"
```

### 4. Prueba de carga con `hey`

```bash
# Instalar hey
# macOS: brew install hey
# Linux: go install github.com/rakyll/hey@latest

# Prueba de carga: 100 requests, 10 concurrentes
hey -n 100 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hola, cómo estás?"}' \
  http://localhost:8000/generate
```

**Métricas a observar:**
- Latencia P50 (mediana)
- Latencia P95 (percentil 95)
- Tasa de éxito
- Requests por segundo

---

## 📊 Análisis de Logs

Los logs en formato JSON se pueden analizar fácilmente:

```bash
# Ver todos los logs
cat logs.json | jq '.'

# Calcular coste total
cat logs.json | jq '.cost_usd' | awk '{sum+=$1} END {print "Total: $"sum}'

# Ver latencias
cat logs.json | jq '.latency_ms' | sort -n

# Encontrar requests lentos (>2 segundos)
cat logs.json | jq 'select(.latency_ms > 2000)'
```

---

## 🎯 Checklist de Producción

- [ ] ✅ Variables de entorno (no hardcodear claves)
- [ ] ✅ Límites de entrada (MAX_CHARS)
- [ ] ✅ Validación de payloads (Pydantic)
- [ ] ✅ Timeouts en llamadas al LLM
- [ ] ✅ Reintentos exponenciales
- [ ] ✅ Manejo de errores (429, 5xx)
- [ ] ✅ Logging estructurado (JSON)
- [ ] ✅ Tracking de request_id
- [ ] ✅ Cálculo de costes
- [ ] ✅ Métricas de latencia
- [ ] ✅ Health check endpoint
- [ ] ✅ Respuestas HTTP apropiadas

---

## 💡 Mensaje Clave

> **"El 80% de la solidez viene de límites, timeouts, reintentos y buenos logs. No de trucar prompts."**

---

## 📈 Próximos Pasos

Después de implementar Demo 1:

1. **Demo 2**: Rate limiting por usuario
2. **Demo 3**: Caching de respuestas
3. **Demo 4**: Streaming optimizado
4. **Demo 5**: Observabilidad avanzada (Prometheus/Grafana)
5. **Demo 6**: Deploy en producción (Docker + K8s)

---

## 🔗 Referencias

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Tenacity (Retry Library)](https://tenacity.readthedocs.io/)
- [Structured Logging Best Practices](https://www.structlog.org/)
