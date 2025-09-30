# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **production-ready template for AI projects** using FastAPI and OpenAI's GPT models. While the current implementation is a Ferrari AI chatbot, the project serves as an educational base that demonstrates how to build AI-powered applications with proper architecture, security, and scalability patterns.

### Purpose
- **Educational template** created by Javier Santos as part of La Escuela de IA
- **Production baseline** for LLM-powered applications with streaming responses
- **Reference implementation** showing best practices for FastAPI + OpenAI integration
- **Scalable foundation** ready to be enhanced with production features (see DEMO_1_INSTRUCTIONS.md)

The application serves a web interface where users chat with an AI assistant specialized in Ferrari sales, demonstrating real-world chatbot patterns including conversation history and streaming responses.

## Architecture

### Backend (main.py)
- **FastAPI application** with CORS middleware enabled for cross-origin requests
- **OpenAI integration** using GPT-4o-mini model for chat completions
- **Static file serving** for the frontend (HTML/CSS/JS)
- **Streaming responses** via Server-Sent Events (SSE) for real-time chat
- **System prompt**: Configured to act as a Ferrari sales advisor ("Eres un AI Chatbot encargado de ayudar al usuario y asesorar para comprar un Ferrari")

### Frontend (static/)
- **index.html**: Chat interface with message display and input
- **app.js**: Handles chat logic, streaming responses, and conversation history
- **style.css**: Styling for the chat interface

### Key Patterns
- Conversation history is maintained client-side and sent with each request
- Messages flow: User message → Backend with full history → OpenAI API → Stream back to client
- System prompt is prepended to all conversations in the backend

## Environment Setup

Required environment variable in `.env`:
```
OPENAI_API_KEY=your_api_key_here
```

## Common Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload

# Run production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Access Points
- Main application: http://localhost:8000
- API endpoint: POST http://localhost:8000/chat

## API Structure

### POST /chat
Request:
```json
{
  "messages": [
    {"role": "user", "content": "message text"},
    {"role": "assistant", "content": "response text"}
  ]
}
```

Response: Server-Sent Events stream
```
data: {"content": "chunk of text"}
data: {"content": "another chunk"}
data: [DONE]
```

## Development Notes

This is currently a basic implementation. The `DEMO_1_INSTRUCTIONS.md` file contains a roadmap for transforming this into a production-ready microservice with:
- Health check endpoints
- Request validation with Pydantic
- Retry logic with exponential backoff
- Structured logging
- Token usage and cost tracking
- Rate limiting
- Error handling for 429/5xx responses

When implementing production features, refer to the patterns and code examples in `DEMO_1_INSTRUCTIONS.md`.

## Project Attribution

Created by Javier Santos as part of La Escuela de IA (https://www.skool.com/la-escuela-de-ia-9955)
