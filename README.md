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

> [!NOTE]
> **📍 Estás en la rama `starter`** - Esta es la versión inicial del proyecto sin protecciones de seguridad (CORS abierto, sin rate limiting, sin validaciones avanzadas). Es perfecta para aprender y comenzar.
>
> **🔐 Para código production-ready** con todas las protecciones de seguridad, consulta la rama [`main`](https://github.com/ESJavadex/production-template-fastapi-llm/tree/main).

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
