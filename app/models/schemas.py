"""
Pydantic models with strict validation and sanitization for production.
All input/output is validated to prevent injection attacks and ensure data integrity.
"""
from pydantic import BaseModel, Field, field_validator, computed_field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import re
import html
import uuid


class MessageRole(str, Enum):
    """Enum for message roles with strict validation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """
    Individual message with strict validation and sanitization.
    """
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., min_length=1, max_length=4000, description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """
        Sanitize message content to prevent XSS and injection attacks.
        """
        # Strip leading/trailing whitespace
        v = v.strip()

        # Check for empty after stripping
        if not v:
            raise ValueError("Message content cannot be empty")

        # HTML escape to prevent XSS
        v = html.escape(v)

        # Remove null bytes
        v = v.replace('\x00', '')

        # Normalize whitespace (collapse multiple spaces)
        v = re.sub(r'\s+', ' ', v)

        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: MessageRole) -> MessageRole:
        """
        Ensure only valid roles are used.
        System role should only be set by backend, never by user input.
        """
        return v

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "¿Cuál es el precio del Ferrari F8 Tributo?",
                "timestamp": "2025-10-01T12:00:00Z"
            }
        }


class ChatRequest(BaseModel):
    """
    Chat request with comprehensive validation.
    Enforces limits on message count, length, and structure.
    """
    messages: List[Message] = Field(..., min_length=1, max_length=50, description="Conversation messages")
    user_id: Optional[str] = Field(default=None, max_length=128, description="Optional user identifier")
    session_id: Optional[str] = Field(default=None, max_length=128, description="Optional session identifier")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=4000, description="Max tokens to generate")
    stream: bool = Field(default=True, description="Whether to stream responses")

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: List[Message]) -> List[Message]:
        """
        Validate message structure and prevent injection.
        """
        if not v:
            raise ValueError("Messages list cannot be empty")

        # Ensure messages alternate between user and assistant (after system)
        # System messages should only come from backend
        user_roles = [msg.role for msg in v]
        if MessageRole.SYSTEM in user_roles:
            raise ValueError("System role cannot be set by client")

        # Check for duplicate consecutive roles
        for i in range(len(v) - 1):
            if v[i].role == v[i+1].role:
                raise ValueError(f"Duplicate consecutive role: {v[i].role}")

        # Validate total content length to prevent token limit abuse
        total_chars = sum(len(msg.content) for msg in v)
        if total_chars > 20000:  # ~5000 tokens approx
            raise ValueError(f"Total message content exceeds limit: {total_chars} > 20000 chars")

        return v

    @field_validator("user_id", "session_id")
    @classmethod
    def sanitize_identifiers(cls, v: Optional[str]) -> Optional[str]:
        """
        Sanitize user and session identifiers.
        """
        if v is None:
            return None

        # Remove dangerous characters
        v = re.sub(r'[^\w\-.]', '', v)

        if not v:
            return None

        return v

    @computed_field
    @property
    def estimated_input_tokens(self) -> int:
        """
        Estimate input tokens (rough approximation: 1 token ≈ 4 chars).
        """
        total_chars = sum(len(msg.content) for msg in self.messages)
        return total_chars // 4

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Hola, ¿qué modelos de Ferrari hay disponibles?"}
                ],
                "user_id": "user123",
                "session_id": "sess456",
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": True
            }
        }


class ChatResponse(BaseModel):
    """
    Chat response with metadata for observability and cost tracking.
    """
    request_id: str = Field(..., description="Unique request identifier")
    content: str = Field(..., description="Assistant response content")
    role: MessageRole = Field(default=MessageRole.ASSISTANT, description="Response role")
    metadata: "ResponseMetadata" = Field(..., description="Response metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_abc123",
                "content": "Tenemos varios modelos disponibles: F8 Tributo, SF90, Roma...",
                "role": "assistant",
                "metadata": {
                    "model": "gpt-4o-mini",
                    "tokens": {"input": 20, "output": 50, "total": 70},
                    "cost_usd": 0.00005,
                    "latency_ms": 1250.5,
                    "cached": False
                },
                "timestamp": "2025-10-01T12:00:01Z"
            }
        }


class ResponseMetadata(BaseModel):
    """
    Metadata about the LLM response for observability and cost tracking.
    """
    model: str = Field(..., description="Model used")
    tokens: "TokenUsage" = Field(..., description="Token usage")
    cost_usd: float = Field(..., ge=0.0, description="Cost in USD")
    latency_ms: float = Field(..., ge=0.0, description="Latency in milliseconds")
    cached: bool = Field(default=False, description="Whether response was from cache")
    moderation_flagged: bool = Field(default=False, description="Whether content was flagged by moderation")
    prompt_injection_detected: bool = Field(default=False, description="Whether prompt injection was detected")
    circuit_breaker_state: Optional[str] = Field(default=None, description="Circuit breaker state")
    retry_count: int = Field(default=0, ge=0, description="Number of retries")


class TokenUsage(BaseModel):
    """
    Token usage details for cost tracking.
    """
    input: int = Field(..., ge=0, description="Input tokens")
    output: int = Field(..., ge=0, description="Output tokens")
    total: int = Field(..., ge=0, description="Total tokens")

    @field_validator("total")
    @classmethod
    def validate_total(cls, v: int, info) -> int:
        """
        Ensure total matches input + output.
        """
        input_tokens = info.data.get("input", 0)
        output_tokens = info.data.get("output", 0)
        expected_total = input_tokens + output_tokens

        if v != expected_total:
            # Auto-correct instead of raising error
            return expected_total

        return v


class HealthCheckResponse(BaseModel):
    """
    Health check response for load balancers and monitoring.
    """
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    checks: Dict[str, bool] = Field(default_factory=dict, description="Individual health checks")


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")


class ModerationResult(BaseModel):
    """
    Content moderation result from OpenAI Moderation API.
    """
    flagged: bool = Field(..., description="Whether content was flagged")
    categories: Dict[str, bool] = Field(..., description="Flagged categories")
    category_scores: Dict[str, float] = Field(..., description="Category scores")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Moderation timestamp")


class PromptInjectionResult(BaseModel):
    """
    Prompt injection detection result.
    """
    detected: bool = Field(..., description="Whether injection was detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    matched_patterns: List[str] = Field(default_factory=list, description="Matched injection patterns")
    semantic_similarity: Optional[float] = Field(default=None, description="Semantic similarity score")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")


class CostTrackingRecord(BaseModel):
    """
    Cost tracking record for budget monitoring.
    """
    request_id: str = Field(..., description="Request ID")
    user_id: Optional[str] = Field(default=None, description="User ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    model: str = Field(..., description="Model used")
    tokens_input: int = Field(..., ge=0, description="Input tokens")
    tokens_output: int = Field(..., ge=0, description="Output tokens")
    cost_usd: float = Field(..., ge=0.0, description="Cost in USD")
    cached: bool = Field(default=False, description="Whether from cache")
    feature: Optional[str] = Field(default=None, description="Feature/endpoint used")


class GDPRDataAccessRequest(BaseModel):
    """
    GDPR data access request.
    """
    user_id: str = Field(..., max_length=128, description="User ID")
    email: str = Field(..., max_length=255, description="User email for verification")
    request_type: str = Field(..., description="Type: access, export, delete")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, v: str) -> str:
        allowed = ["access", "export", "delete"]
        if v not in allowed:
            raise ValueError(f"Request type must be one of: {allowed}")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        # Basic email validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class PromptVersion(BaseModel):
    """
    Prompt version for A/B testing and migrations.
    """
    version: str = Field(..., description="Version identifier")
    system_prompt: str = Field(..., description="System prompt text")
    active: bool = Field(default=True, description="Whether version is active")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
