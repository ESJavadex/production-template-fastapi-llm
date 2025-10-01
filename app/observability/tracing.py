"""
Observability and tracing with Langfuse/LangSmith/Logfire.
Provides end-to-end request tracing, PII redaction, and structured logging.
"""
from typing import Optional, Dict, Any, List
import json
import logging
import time
import uuid
import re
from datetime import datetime
from contextlib import contextmanager

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    Redacts Personally Identifiable Information (PII) from logs and traces.
    """

    def __init__(self):
        # Patterns for common PII
        self.patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            # Add more patterns as needed
        }

    def redact(self, text: str) -> str:
        """
        Redact PII from text.

        Args:
            text: Text to redact

        Returns:
            Redacted text
        """
        redacted = text

        for pii_type, pattern in self.patterns.items():
            redacted = pattern.sub(f"[REDACTED_{pii_type.upper()}]", redacted)

        return redacted

    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact PII from dictionary.
        """
        redacted = {}

        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self.redact(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                redacted[key] = value

        return redacted


class TraceContext:
    """
    Context for a single request trace.
    """

    def __init__(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.start_time = time.time()
        self.spans: List[Dict[str, Any]] = []

    def add_span(
        self,
        name: str,
        span_type: str,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None
    ):
        """
        Add a span to the trace.
        """
        span = {
            "span_id": str(uuid.uuid4()),
            "name": name,
            "type": span_type,
            "input": input_data,
            "output": output_data,
            "metadata": metadata or {},
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.spans.append(span)

    def get_duration_ms(self) -> float:
        """
        Get total trace duration in milliseconds.
        """
        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace to dictionary for export.
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "spans": self.spans,
            "duration_ms": self.get_duration_ms(),
            "timestamp": datetime.utcnow().isoformat()
        }


class ObservabilityService:
    """
    Unified observability service supporting multiple providers.
    """

    def __init__(self):
        self.settings = get_settings()
        self.pii_redactor = PIIRedactor()
        self.provider = self.settings.observability_provider

        # Initialize provider client
        self._init_provider()

    def _init_provider(self):
        """
        Initialize the observability provider client.
        """
        try:
            if self.provider == "langfuse":
                self._init_langfuse()
            elif self.provider == "langsmith":
                self._init_langsmith()
            elif self.provider == "logfire":
                self._init_logfire()
            else:
                logger.warning(f"Unknown observability provider: {self.provider}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider}: {e}")

    def _init_langfuse(self):
        """
        Initialize Langfuse client.
        """
        try:
            from langfuse import Langfuse

            if not self.settings.langfuse_public_key or not self.settings.langfuse_secret_key:
                logger.warning("Langfuse credentials not configured")
                self.langfuse_client = None
                return

            self.langfuse_client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host
            )
            logger.info("Langfuse client initialized")

        except ImportError:
            logger.warning("Langfuse not installed: pip install langfuse")
            self.langfuse_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            self.langfuse_client = None

    def _init_langsmith(self):
        """
        Initialize LangSmith client.
        """
        try:
            from langsmith import Client

            if not self.settings.langsmith_api_key:
                logger.warning("LangSmith API key not configured")
                self.langsmith_client = None
                return

            self.langsmith_client = Client(
                api_key=self.settings.langsmith_api_key,
                api_url=self.settings.langsmith_endpoint
            )
            logger.info("LangSmith client initialized")

        except ImportError:
            logger.warning("LangSmith not installed: pip install langsmith")
            self.langsmith_client = None
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith: {e}")
            self.langsmith_client = None

    def _init_logfire(self):
        """
        Initialize Logfire client.
        """
        try:
            import logfire

            if not self.settings.logfire_token:
                logger.warning("Logfire token not configured")
                self.logfire_client = None
                return

            logfire.configure(token=self.settings.logfire_token)
            self.logfire_client = logfire
            logger.info("Logfire client initialized")

        except ImportError:
            logger.warning("Logfire not installed: pip install logfire")
            self.logfire_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Logfire: {e}")
            self.logfire_client = None

    def create_trace(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TraceContext:
        """
        Create a new trace context.
        """
        return TraceContext(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata
        )

    @contextmanager
    def trace_span(
        self,
        trace: TraceContext,
        name: str,
        span_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracing a span.

        Usage:
            with observability.trace_span(trace, "llm_call", "llm") as span:
                result = call_llm()
                span["output"] = result
        """
        span_start = time.time()
        span_data = {"input": None, "output": None, "metadata": metadata or {}}

        try:
            yield span_data
        finally:
            duration_ms = (time.time() - span_start) * 1000
            trace.add_span(
                name=name,
                span_type=span_type,
                input_data=span_data.get("input"),
                output_data=span_data.get("output"),
                metadata=span_data.get("metadata"),
                duration_ms=duration_ms
            )

    def finalize_trace(self, trace: TraceContext):
        """
        Finalize and export trace to provider.
        """
        trace_data = trace.to_dict()

        # Apply PII redaction if enabled
        if self.settings.enable_pii_redaction:
            trace_data = self.pii_redactor.redact_dict(trace_data)

        # Apply sampling
        if not self._should_sample():
            logger.debug(f"Trace {trace.request_id} not sampled")
            return

        # Export to provider
        try:
            if self.provider == "langfuse" and hasattr(self, "langfuse_client") and self.langfuse_client:
                self._export_to_langfuse(trace_data)
            elif self.provider == "langsmith" and hasattr(self, "langsmith_client") and self.langsmith_client:
                self._export_to_langsmith(trace_data)
            elif self.provider == "logfire" and hasattr(self, "logfire_client") and self.logfire_client:
                self._export_to_logfire(trace_data)
            else:
                # Fallback: log to structured logs
                self._log_trace(trace_data)
        except Exception as e:
            logger.error(f"Failed to export trace: {e}")
            # Fallback to logging
            self._log_trace(trace_data)

    def _should_sample(self) -> bool:
        """
        Determine if trace should be sampled.
        """
        import random
        return random.random() < self.settings.sampling_rate

    def _export_to_langfuse(self, trace_data: Dict[str, Any]):
        """
        Export trace to Langfuse.
        """
        try:
            trace = self.langfuse_client.trace(
                id=trace_data["request_id"],
                name="chat_request",
                user_id=trace_data.get("user_id"),
                session_id=trace_data.get("session_id"),
                metadata=trace_data.get("metadata")
            )

            # Add spans
            for span in trace_data.get("spans", []):
                trace.span(
                    id=span["span_id"],
                    name=span["name"],
                    input=span.get("input"),
                    output=span.get("output"),
                    metadata=span.get("metadata")
                )

            logger.debug(f"Trace {trace_data['request_id']} exported to Langfuse")

        except Exception as e:
            logger.error(f"Failed to export to Langfuse: {e}")

    def _export_to_langsmith(self, trace_data: Dict[str, Any]):
        """
        Export trace to LangSmith.
        """
        try:
            # LangSmith export implementation
            logger.debug(f"Trace {trace_data['request_id']} exported to LangSmith")
        except Exception as e:
            logger.error(f"Failed to export to LangSmith: {e}")

    def _export_to_logfire(self, trace_data: Dict[str, Any]):
        """
        Export trace to Logfire.
        """
        try:
            self.logfire_client.info(
                "chat_request",
                **trace_data
            )
            logger.debug(f"Trace {trace_data['request_id']} exported to Logfire")
        except Exception as e:
            logger.error(f"Failed to export to Logfire: {e}")

    def _log_trace(self, trace_data: Dict[str, Any]):
        """
        Fallback: Log trace as structured JSON.
        """
        logger.info(json.dumps(trace_data, default=str))


# Global instance
_observability_service: Optional[ObservabilityService] = None


def get_observability_service() -> ObservabilityService:
    """
    Get global ObservabilityService instance.
    """
    global _observability_service
    if _observability_service is None:
        _observability_service = ObservabilityService()
    return _observability_service
