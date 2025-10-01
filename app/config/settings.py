"""
Production-grade configuration management with Pydantic Settings.
Supports environment variables, secret managers, and validation.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """
    Centralized configuration with validation and security best practices.
    All sensitive values should be loaded from environment or secret manager.
    """

    # === Application Settings ===
    app_name: str = Field(default="Ferrari AI Chatbot - Production", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Debug mode - NEVER enable in production")

    # === API Settings ===
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of worker processes")

    # === OpenAI Settings ===
    openai_api_key: str = Field(..., description="OpenAI API Key - MUST be set via env or secret manager")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    openai_timeout: int = Field(default=30, description="OpenAI API timeout in seconds")
    openai_max_retries: int = Field(default=3, description="Max retries for OpenAI API calls")

    # === Security & Validation Limits ===
    max_message_length: int = Field(default=4000, description="Max characters per message (~1000 tokens)")
    max_messages_per_session: int = Field(default=50, description="Max messages in conversation history")
    max_total_session_tokens: int = Field(default=8000, description="Max total tokens per session")
    max_conversation_age_hours: int = Field(default=24, description="Max age of conversation in hours")

    # === Rate Limiting ===
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute_per_ip: int = Field(default=10, description="Requests per minute per IP")
    rate_limit_requests_per_minute_per_user: int = Field(default=20, description="Requests per minute per user")
    rate_limit_requests_per_hour_global: int = Field(default=1000, description="Global requests per hour")
    rate_limit_redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL for rate limiting")

    # === Prompt Injection Protection ===
    prompt_injection_enabled: bool = Field(default=True, description="Enable prompt injection detection")
    prompt_injection_blocked_patterns: List[str] = Field(
        default=[
            "ignore previous instructions",
            "forget your prompt",
            "you are now",
            "act as",
            "new instructions",
            "disregard",
            "system:",
            "assistant:",
            "set your prompt to",
        ],
        description="Patterns that trigger prompt injection detection"
    )
    prompt_injection_similarity_threshold: float = Field(
        default=0.85,
        description="Semantic similarity threshold for injection detection"
    )

    # === Content Moderation ===
    moderation_enabled: bool = Field(default=True, description="Enable OpenAI content moderation")
    moderation_pre_llm: bool = Field(default=True, description="Moderate user input before sending to LLM")
    moderation_post_llm: bool = Field(default=True, description="Moderate LLM output before sending to user")
    moderation_threshold: float = Field(default=0.5, description="Moderation score threshold (0-1)")

    # === Observability ===
    observability_provider: str = Field(default="langfuse", description="Provider: langfuse, langsmith, logfire")

    # LangSmith
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API Key")
    langsmith_project: str = Field(default="ferrari-chatbot-prod", description="LangSmith project name")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith endpoint")

    # Langfuse
    langfuse_public_key: Optional[str] = Field(default=None, description="Langfuse public key")
    langfuse_secret_key: Optional[str] = Field(default=None, description="Langfuse secret key")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", description="Langfuse host")

    # Logfire
    logfire_token: Optional[str] = Field(default=None, description="Logfire token")

    # General observability
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    enable_pii_redaction: bool = Field(default=True, description="Redact PII from logs")
    sampling_rate: float = Field(default=1.0, description="Trace sampling rate (0.0-1.0)")

    # === Cost Tracking ===
    cost_tracking_enabled: bool = Field(default=True, description="Enable cost tracking")
    cost_per_1m_input_tokens: float = Field(default=0.15, description="Cost per 1M input tokens (USD)")
    cost_per_1m_output_tokens: float = Field(default=0.60, description="Cost per 1M output tokens (USD)")
    cost_budget_daily_usd: float = Field(default=100.0, description="Daily cost budget in USD")
    cost_budget_monthly_usd: float = Field(default=2000.0, description="Monthly cost budget in USD")
    cost_alert_threshold: float = Field(default=0.8, description="Alert when budget reaches this fraction (0-1)")
    cost_alert_email: Optional[str] = Field(default=None, description="Email for cost alerts")

    # === Caching ===
    cache_enabled: bool = Field(default=True, description="Enable semantic caching")
    cache_redis_url: str = Field(default="redis://localhost:6379/1", description="Redis URL for caching")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    cache_similarity_threshold: float = Field(default=0.95, description="Similarity threshold for cache hits")

    # === Circuit Breaker ===
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_failure_threshold: int = Field(default=5, description="Failures before opening circuit")
    circuit_breaker_recovery_timeout: int = Field(default=60, description="Seconds before attempting recovery")
    circuit_breaker_expected_exception: tuple = Field(default=(Exception,), description="Exceptions that trigger circuit breaker")

    # === GDPR Compliance ===
    gdpr_enabled: bool = Field(default=True, description="Enable GDPR compliance features")
    gdpr_data_retention_days: int = Field(default=90, description="Days to retain user data")
    gdpr_encryption_enabled: bool = Field(default=True, description="Encrypt data at rest")
    gdpr_encryption_key: Optional[str] = Field(default=None, description="Encryption key for data at rest")
    gdpr_audit_log_enabled: bool = Field(default=True, description="Enable audit logging for GDPR")
    gdpr_dpo_email: str = Field(default="dpo@company.com", description="Data Protection Officer email")

    # === EU AI Act Compliance ===
    eu_ai_act_enabled: bool = Field(default=True, description="Enable EU AI Act compliance")
    eu_ai_act_risk_level: str = Field(default="limited", description="Risk level: minimal, limited, high, unacceptable")
    eu_ai_act_human_oversight: bool = Field(default=True, description="Require human oversight")
    eu_ai_act_transparency_notice: bool = Field(default=True, description="Display AI transparency notice")
    eu_ai_act_bias_monitoring: bool = Field(default=True, description="Monitor for bias in responses")

    # === CORS ===
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_allow_methods: List[str] = Field(default=["GET", "POST", "OPTIONS"], description="Allowed HTTP methods")
    cors_allow_headers: List[str] = Field(default=["*"], description="Allowed headers")

    # === Prompt Versioning ===
    prompt_version: str = Field(default="v1.0", description="Current prompt version")
    prompt_versioning_enabled: bool = Field(default=True, description="Enable prompt versioning")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v

    @field_validator("debug")
    @classmethod
    def validate_debug(cls, v: bool, info) -> bool:
        # Force debug=False in production
        if info.data.get("environment") == "production" and v:
            raise ValueError("Debug mode cannot be enabled in production environment")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v

    @field_validator("eu_ai_act_risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        allowed = ["minimal", "limited", "high", "unacceptable"]
        if v not in allowed:
            raise ValueError(f"Risk level must be one of: {allowed}")
        return v

    @field_validator("sampling_rate", "cost_alert_threshold", "cache_similarity_threshold", "prompt_injection_similarity_threshold", "moderation_threshold")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Rate must be between 0.0 and 1.0")
        return v


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings singleton.
    Lazily loads settings on first access.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    Useful for testing or configuration updates.
    """
    global _settings
    _settings = Settings()
    return _settings
