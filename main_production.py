"""
Production-ready Ferrari AI Chatbot with enterprise-grade features:
- Multi-layer security (prompt injection, content moderation, input validation)
- Rate limiting (IP, user, global with Redis)
- Observability (Langfuse/LangSmith/Logfire with PII redaction)
- Cost tracking and budget alerts
- Semantic caching for cost reduction
- Circuit breakers and retry logic
- GDPR and EU AI Act compliance
- Comprehensive error handling

Author: Javier Santos (La Escuela de IA)
License: MIT
"""
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import json
import time
import uuid
from typing import AsyncGenerator

from app.config.settings import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ResponseMetadata,
    TokenUsage,
    HealthCheckResponse,
    ErrorResponse,
    MessageRole
)
from app.security.prompt_injection import get_prompt_guard
from app.services.moderation import get_moderation_service
from app.services.llm_service import get_llm_service
from app.services.cost_tracker import get_cost_tracker
from app.services.cache_service import get_semantic_cache
from app.observability.tracing import get_observability_service
from app.middleware.rate_limiter import RateLimitMiddleware, RateLimitExceeded

# Configure structured logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.log_format == "text"
           else '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Observability provider: {settings.observability_provider}")

    # Initialize services
    logger.info("Initializing services...")

    # Warm up services
    _ = get_prompt_guard()
    _ = get_moderation_service()
    _ = get_llm_service()
    _ = get_observability_service()

    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Close async resources
    try:
        cost_tracker = await get_cost_tracker()
        await cost_tracker.close()

        cache = await get_semantic_cache()
        await cache.close()

        logger.info("All resources closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-ready AI chatbot with enterprise security and observability",
    lifespan=lifespan
)

# Add CORS middleware (configure restrictively in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.environment == "production"
                  else ["*"],  # Permissive only in dev
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add rate limiting middleware
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limiting enabled")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Add unique request ID to all requests for tracing.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all requests with timing information.
    """
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        f"Request started: method={request.method} path={request.url.path} "
        f"request_id={request_id}"
    )

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Request completed: method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={duration_ms:.2f} "
        f"request_id={request_id}"
    )

    return response


# Mount static files for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_root():
    """Serve frontend HTML."""
    return FileResponse("static/index.html")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    checks = {
        "api": True,
        "redis": True,  # Add actual Redis health check in production
        "openai": True,  # Add actual OpenAI connectivity check
    }

    # Determine overall status
    all_healthy = all(checks.values())
    status_str = "healthy" if all_healthy else "degraded"

    return HealthCheckResponse(
        status=status_str,
        version=settings.app_version,
        environment=settings.environment,
        checks=checks
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Main chat endpoint with full production guardrails.

    Security layers:
    1. Input validation (Pydantic)
    2. Prompt injection detection
    3. Content moderation (pre-LLM)
    4. LLM call with circuit breaker
    5. Content moderation (post-LLM)
    6. Cost tracking
    7. Observability tracing

    Performance optimizations:
    - Semantic caching
    - Rate limiting
    - Circuit breakers
    """
    request_id = getattr(req.state, "request_id", str(uuid.uuid4()))
    start_time = time.time()

    # Initialize services
    prompt_guard = get_prompt_guard()
    moderation_service = get_moderation_service()
    llm_service = get_llm_service()
    cost_tracker = await get_cost_tracker()
    cache = await get_semantic_cache()
    observability = get_observability_service()

    # Create trace context
    trace = observability.create_trace(
        request_id=request_id,
        user_id=request.user_id,
        session_id=request.session_id,
        metadata={
            "endpoint": "/chat",
            "model": settings.openai_model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
    )

    try:
        # === LAYER 1: Prompt Injection Detection ===
        with observability.trace_span(trace, "prompt_injection_check", "security") as span:
            messages, injection_detected = prompt_guard.validate_and_prepare_messages(
                request.messages
            )
            span["output"] = {"injection_detected": injection_detected}

            if injection_detected:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prompt injection detected. Please rephrase your message."
                )

        # === LAYER 2: Content Moderation (Pre-LLM) ===
        with observability.trace_span(trace, "moderation_pre_llm", "security") as span:
            last_user_message = next(
                (msg["content"] for msg in reversed(messages) if msg["role"] == "user"),
                ""
            )

            moderation_result = moderation_service.pre_llm_check(last_user_message)
            span["output"] = {"flagged": moderation_result.flagged}

            if moderation_result.flagged:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content violates our usage policies. Please modify your message."
                )

        # === LAYER 3: Semantic Cache Check ===
        cached_response = None
        with observability.trace_span(trace, "cache_check", "cache") as span:
            cached_response = await cache.get(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            span["output"] = {"cache_hit": cached_response is not None}

        if cached_response:
            # Return cached response
            content, cached_metadata = cached_response

            metadata = ResponseMetadata(
                model=settings.openai_model,
                tokens=TokenUsage(
                    input=cached_metadata.get("tokens", {}).get("input", 0),
                    output=cached_metadata.get("tokens", {}).get("output", 0),
                    total=cached_metadata.get("tokens", {}).get("total", 0)
                ),
                cost_usd=cached_metadata.get("cost_usd", 0.0),
                latency_ms=(time.time() - start_time) * 1000,
                cached=True,
                moderation_flagged=False,
                prompt_injection_detected=False,
                retry_count=0
            )

            logger.info(f"Cache hit for request {request_id}")

            # Finalize trace
            observability.finalize_trace(trace)

            return ChatResponse(
                request_id=request_id,
                content=content,
                role=MessageRole.ASSISTANT,
                metadata=metadata
            )

        # === LAYER 4: LLM Call with Circuit Breaker ===
        with observability.trace_span(trace, "llm_call", "llm") as span:
            span["input"] = {"messages": messages, "temperature": request.temperature}

            response_content, token_usage, retry_count = llm_service.chat_completion(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            span["output"] = {
                "content_length": len(response_content),
                "tokens": token_usage.dict(),
                "retry_count": retry_count
            }

        # === LAYER 5: Content Moderation (Post-LLM) ===
        with observability.trace_span(trace, "moderation_post_llm", "security") as span:
            post_moderation = moderation_service.post_llm_check(response_content)
            span["output"] = {"flagged": post_moderation.flagged}

            if post_moderation.flagged:
                # Log and return safe fallback response
                logger.warning(f"LLM output flagged by moderation: request_id={request_id}")
                response_content = (
                    "Lo siento, no puedo proporcionar esa información. "
                    "¿Puedo ayudarte con algo más sobre Ferrari?"
                )

        # === LAYER 6: Cost Calculation & Tracking ===
        cost_usd = llm_service.calculate_cost(token_usage)

        with observability.trace_span(trace, "cost_tracking", "metrics") as span:
            await cost_tracker.track_cost(
                request_id=request_id,
                user_id=request.user_id,
                token_usage=token_usage,
                cost_usd=cost_usd,
                model=settings.openai_model,
                feature="chat",
                cached=False
            )
            span["output"] = {"cost_usd": cost_usd}

        # === LAYER 7: Cache Response ===
        with observability.trace_span(trace, "cache_set", "cache") as span:
            await cache.set(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response=response_content,
                metadata={
                    "tokens": token_usage.dict(),
                    "cost_usd": cost_usd
                }
            )

        # === Prepare Response ===
        latency_ms = (time.time() - start_time) * 1000

        metadata = ResponseMetadata(
            model=settings.openai_model,
            tokens=token_usage,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=False,
            moderation_flagged=post_moderation.flagged,
            prompt_injection_detected=False,
            circuit_breaker_state=str(llm_service.get_circuit_state()) if llm_service.get_circuit_state() else None,
            retry_count=retry_count
        )

        # Finalize trace
        observability.finalize_trace(trace)

        return ChatResponse(
            request_id=request_id,
            content=response_content,
            role=MessageRole.ASSISTANT,
            metadata=metadata
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        observability.finalize_trace(trace)
        raise

    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        observability.finalize_trace(trace)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """
    Streaming chat endpoint.
    Returns Server-Sent Events (SSE) for real-time responses.
    """
    request_id = getattr(req.state, "request_id", str(uuid.uuid4()))

    async def generate() -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        try:
            # Initialize services
            prompt_guard = get_prompt_guard()
            moderation_service = get_moderation_service()
            llm_service = get_llm_service()

            # Validate and prepare messages
            messages, injection_detected = prompt_guard.validate_and_prepare_messages(
                request.messages
            )

            if injection_detected:
                yield f"data: {json.dumps({'error': 'Prompt injection detected'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Pre-LLM moderation
            last_user_message = next(
                (msg["content"] for msg in reversed(messages) if msg["role"] == "user"),
                ""
            )

            moderation_result = moderation_service.pre_llm_check(last_user_message)

            if moderation_result.flagged:
                yield f"data: {json.dumps({'error': 'Content violates policies'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Stream LLM response
            async for chunk in llm_service.chat_completion_stream(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in streaming endpoint: {e}")
            yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/metrics/costs/daily")
async def get_daily_costs():
    """Get daily cost metrics."""
    cost_tracker = await get_cost_tracker()
    return await cost_tracker.get_daily_cost()


@app.get("/metrics/costs/monthly")
async def get_monthly_costs():
    """Get monthly cost metrics."""
    cost_tracker = await get_cost_tracker()
    return await cost_tracker.get_monthly_cost()


@app.get("/metrics/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    cache = await get_semantic_cache()
    return await cache.get_stats()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "rate_limit_exceeded",
            "message": exc.detail,
            "retry_after": exc.retry_after
        },
        headers=exc.headers
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    error = ErrorResponse(
        error="internal_server_error",
        message="An unexpected error occurred",
        request_id=request_id
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error.dict()
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_production:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if settings.environment == "production" else 1,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
