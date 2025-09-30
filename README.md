<div align="center">

# 🏎️ Ferrari AI Chatbot

### Template de Producción para Proyectos de IA con FastAPI

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange.svg)](https://openai.com/)
[![License](https://img.shields.io/badge/License-Educational-purple.svg)](LICENSE)

**Un chatbot inteligente de asesoramiento de Ferrari que sirve como base para proyectos de IA con protección y preparado para producción.**

[🎥 Ver Tutorial en YouTube](#) • [📚 Documentación](DEMO_1_INSTRUCTIONS.md) • [🎓 La Escuela de IA](https://www.skool.com/la-escuela-de-ia-9955)

---

</div>

> [!IMPORTANT]
> **🔐 Estás en la rama `main`** - Esta es la versión production-ready con todas las protecciones de seguridad (validaciones, rate limiting, retry logic, logging estructurado, manejo de errores, etc.).
>
> **🚀 ¿Empezando desde cero?** Consulta la rama [`starter`](https://github.com/ESJavadex/production-template-fastapi-llm/tree/starter) para la versión inicial básica, perfecta para aprender paso a paso.

---

## ✨ Sobre este Proyecto

Este proyecto sirve como **plantilla base para desarrollar aplicaciones de IA production-ready**. Aunque el ejemplo implementado es un chatbot de asesoramiento de Ferrari, la arquitectura y patrones pueden adaptarse a cualquier proyecto que requiera integración con LLMs.

### 🎯 ¿Qué incluye?

- ✅ **Backend robusto con FastAPI** - API moderna y de alto rendimiento
- ✅ **Streaming en tiempo real** - Respuestas fluidas mediante Server-Sent Events
- ✅ **Gestión de conversaciones** - Historial completo de mensajes
- ✅ **Integración con OpenAI** - Utiliza GPT-4o-mini para respuestas inteligentes
- ✅ **Frontend moderno** - Interfaz de chat limpia y responsive
- ✅ **Variables de entorno seguras** - Manejo apropiado de credenciales
- ✅ **Estructura escalable** - Lista para añadir features de producción

## 🚀 Inicio Rápido

### Prerequisitos

- Python 3.12 o superior
- Una API key de OpenAI ([obtener aquí](https://platform.openai.com/api-keys))
- Git instalado

### Instalación en 4 pasos

1️⃣ **Clona el repositorio**
```bash
git clone <repository-url>
cd production-template-fastapi-llm
```

2️⃣ **Crea y activa el entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3️⃣ **Instala las dependencias**
```bash
pip install -r requirements.txt
```

4️⃣ **Configura tus variables de entorno**
```bash
echo "OPENAI_API_KEY=tu_clave_api_aquí" > .env
```

### ▶️ Ejecutar la Aplicación

```bash
uvicorn main:app --reload
```

Abre tu navegador en **http://localhost:8000** y comienza a chatear con tu asistente de Ferrari!

---

## 📁 Estructura del Proyecto

```
production-template-fastapi-llm/
│
├── 📄 main.py                      # Backend FastAPI con endpoints y lógica
├── 📁 static/                      # Archivos del frontend
│   ├── index.html                  # Interfaz de usuario del chat
│   ├── app.js                      # Lógica cliente y gestión de streaming
│   └── style.css                   # Estilos de la aplicación
│
├── 📋 requirements.txt             # Dependencias Python
├── 🔐 .env                         # Variables de entorno (no incluido en git)
├── 📚 DEMO_1_INSTRUCTIONS.md       # Guía para convertir a producción
├── 📖 CLAUDE.md                    # Guía para Claude Code
└── 📝 README.md                    # Este archivo
```

---

## 🔌 API Reference

### `GET /`
Sirve la interfaz principal del chat

### `POST /chat`
Procesa mensajes de chat con respuestas en streaming

**Request Body:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "¿Qué modelos de Ferrari recomiendas para principiantes?"
    }
  ]
}
```

**Response:** Stream de Server-Sent Events
```
data: {"content": "Para principiantes, "}
data: {"content": "recomiendo el Ferrari"}
data: {"content": " Roma..."}
data: [DONE]
```

---

## 🎓 Aprende Más

Este proyecto es parte del contenido educativo de **La Escuela de IA**.

📺 **[Ver el tutorial completo en YouTube](#)** *(próximamente)*

En el tutorial aprenderás:
- Cómo estructurar aplicaciones de IA para producción
- Patrones de diseño para integración con LLMs
- Mejores prácticas de seguridad y manejo de errores
- Cómo escalar y optimizar tu aplicación

Para transformar esta base en un microservicio production-ready completo, consulta `DEMO_1_INSTRUCTIONS.md` donde encontrarás implementaciones de:
- Health checks y monitoreo
- Validación de entrada y límites
- Retry logic y manejo de errores
- Logging estructurado
- Tracking de costes y tokens
- Rate limiting

---

## ✅ Checklist de Producción para LLMs

Una guía completa de los elementos críticos para llevar aplicaciones de IA a producción de forma segura y escalable.

**📋 [Ver Checklist Interactivo Completo](https://llm-production-guard.lovable.app/)** - 53 puntos de control en 10 categorías

### 🔒 Control de Entrada y Usuarios

- [ ] **Limitar longitud de entrada** (frontend y backend) - `Crítico`
- [ ] **Validar y sanitizar entrada** (filtrar HTML, scripts, caracteres especiales) - `Crítico`
- [ ] **Validar esquema de datos** (verificar formato JSON esperado) - `Importante`

### 💰 Control de Costes y Uso

- [ ] **Implementar rate limiting** (limitar peticiones por usuario/IP) - `Crítico`
- [ ] **Monitorizar uso de tokens** (rastrear consumo por petición y usuario) - `Importante`
- [ ] **Configurar alertas de coste** (notificar cuando se superan umbrales) - `Importante`
- [ ] **Mostrar estimaciones de coste** (transparencia con usuarios) - `Recomendado`

### 🛡️ Moderación y Seguridad

- [ ] **Usar API de moderación de contenido** (OpenAI Moderation o reglas custom) - `Crítico`
- [ ] **Proteger contra inyección de prompts** (mantener prompt de sistema en backend) - `Crítico`
- [ ] **Validar respuestas del modelo** (verificar antes de mostrar a usuarios) - `Importante`
- [ ] **Limitar acciones del prompt** (restringir funciones peligrosas) - `Crítico`
- [ ] **Filtrar respuestas tóxicas** (bloquear contenido inapropiado) - `Importante`

### 🔄 Manejo de Errores y Resiliencia

- [ ] **Implementar reintentos automáticos** (retry logic para llamadas API) - `Importante`
- [ ] **Configurar manejo global de errores** (error workflows) - `Importante`
- [ ] **Mensajes de error amigables** (incluir 429, Retry-After headers) - `Importante`
- [ ] **Implementar fallbacks** (caché o modelos alternativos) - `Recomendado`

### 📊 Logging y Trazabilidad

- [ ] **Generar IDs únicos de petición** (request_id para cada llamada) - `Crítico`
- [ ] **Registrar datos completos** (user_id, timestamp, modelo, tokens, coste, latencia) - `Crítico`
- [ ] **Persistir logs de forma segura** (base de datos, Datastore, etc.) - `Importante`
- [ ] **Mantener logs de auditoría** (cumplimiento y debugging) - `Importante`

### 🔐 Secretos y Seguridad

- [ ] **Usar almacenamiento seguro de credenciales** (variables de entorno, nunca hardcodear) - `Crítico`
- [ ] **Externalizar secretos** (AWS Secrets Manager, GCP Secret Manager) - `Recomendado`
- [ ] **Controlar acceso a workflows** (autenticación y permisos mínimos) - `Crítico`

### 📈 Escalabilidad y Operaciones

- [ ] **Configurar queue mode** (gestionar picos de tráfico) - `Importante`
- [ ] **Implementar autoscaling** (escalar infraestructura automáticamente) - `Recomendado`
- [ ] **Monitorizar salud del sistema** (latencia, uptime, rendimiento) - `Importante`

### 🧪 Versionado y Testing

- [ ] **Versionar prompts y modelos** (control de cambios y rollback) - `Importante`
- [ ] **Implementar testing automatizado** (unitarios, integración, e2e) - `Importante`
- [ ] **Testear casos extremos** (entradas largas, inyección, temas sensibles) - `Importante`
- [ ] **Ejecutar tests A/B** (comparar prompts/modelos) - `Recomendado`

### 🔏 Privacidad y Cumplimiento

- [ ] **Anonimizar datos sensibles** (hashear o enmascarar datos personales) - `Crítico`
- [ ] **Definir política de retención de datos** (reglas de almacenamiento y eliminación) - `Importante`
- [ ] **Informar sobre uso de IA** (transparencia con usuarios) - `Importante`
- [ ] **Auditar accesos y cambios** (registrar modificaciones de configuración) - `Importante`

### 👥 UX y Feedback

- [ ] **Comunicar límites claramente** (mostrar cuando se alcanzan límites) - `Importante`
- [ ] **Proporcionar mensajes de error útiles** (explicar degradación en términos amigables) - `Importante`
- [ ] **Habilitar feedback de usuario** (reportar problemas desde la interfaz) - `Recomendado`
- [ ] **Implementar human-in-the-loop** (revisión manual para casos sensibles) - `Recomendado`

> [!TIP]
> **🎯 Prioriza los elementos marcados como "Crítico"** - Estos son fundamentales para seguridad y estabilidad en producción.
>
> Para implementaciones detalladas y código de ejemplo, visita el [**Checklist Interactivo**](https://llm-production-guard.lovable.app/) con 53 puntos de control y ejemplos de código.

---

## 🛠️ Tecnologías Utilizadas

| Tecnología | Propósito |
|------------|-----------|
| **FastAPI** | Framework web moderno y de alto rendimiento |
| **OpenAI API** | Modelo de lenguaje GPT-4o-mini |
| **Uvicorn** | Servidor ASGI para producción |
| **Python-dotenv** | Gestión de variables de entorno |
| **Vanilla JS** | Frontend sin dependencias pesadas |

---

## 👨‍💻 Autor

**Javier Santos**

Creado como parte de [**La Escuela de IA**](https://www.skool.com/la-escuela-de-ia-9955)

🌐 Únete a la comunidad y aprende a construir aplicaciones de IA profesionales

---

## 📄 Licencia

Este proyecto es de código abierto y está disponible con fines educativos.

---

<div align="center">

**⭐ Si este proyecto te resultó útil, considera darle una estrella!**

Made with ❤️ for the AI community

</div>
