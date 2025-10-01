"""
LLM service with circuit breakers, retries, and comprehensive error handling.
Integrates with OpenAI API with production-grade resilience patterns.
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
import time
from enum import Enum
from datetime import datetime, timedelta
from openai import OpenAI, OpenAIError, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from app.config.settings import get_settings
from app.models.schemas import TokenUsage

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: tuple = (Exception,)
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(
                    f"Circuit breaker is OPEN. "
                    f"Retry after {self.recovery_timeout}s"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.
        """
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    def _on_success(self):
        """
        Reset circuit breaker on successful call.
        """
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker CLOSED after successful recovery")

    def _on_failure(self):
        """
        Record failure and potentially open circuit.
        """
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state


class LLMService:
    """
    Production-grade LLM service with resilience patterns.
    """

    def __init__(self, client: Optional[OpenAI] = None):
        self.settings = get_settings()
        self.client = client or OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout,
            max_retries=0  # We handle retries ourselves
        )

        # Circuit breaker for LLM calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.circuit_breaker_failure_threshold,
            recovery_timeout=self.settings.circuit_breaker_recovery_timeout,
            expected_exception=(OpenAIError, APITimeoutError, APIConnectionError)
        ) if self.settings.circuit_breaker_enabled else None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _call_openai_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool = False
    ):
        """
        Call OpenAI API with exponential backoff retry.
        """
        return self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            timeout=self.settings.openai_timeout
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> tuple[str, TokenUsage, int]:
        """
        Non-streaming chat completion.

        Returns:
            Tuple of (response_content, token_usage, retry_count)
        """
        retry_count = 0

        def _call():
            nonlocal retry_count

            try:
                response = self._call_openai_with_retry(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )

                content = response.choices[0].message.content
                usage = TokenUsage(
                    input=response.usage.prompt_tokens,
                    output=response.usage.completion_tokens,
                    total=response.usage.total_tokens
                )

                return content, usage, retry_count

            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                retry_count += 1
                logger.warning(f"OpenAI API error (retry {retry_count}): {e}")
                raise

            except OpenAIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise

        # Use circuit breaker if enabled
        if self.circuit_breaker:
            return self.circuit_breaker.call(_call)
        else:
            return _call()

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion.

        Yields:
            Content chunks as they arrive
        """
        retry_count = 0

        def _call():
            nonlocal retry_count

            try:
                return self._call_openai_with_retry(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                retry_count += 1
                logger.warning(f"OpenAI API error (retry {retry_count}): {e}")
                raise

            except OpenAIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise

        # Get stream with circuit breaker protection
        if self.circuit_breaker:
            stream = self.circuit_breaker.call(_call)
        else:
            stream = _call()

        # Yield chunks
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    def calculate_cost(self, token_usage: TokenUsage) -> float:
        """
        Calculate cost of LLM call based on token usage.

        Args:
            token_usage: Token usage details

        Returns:
            Cost in USD
        """
        input_cost = (token_usage.input / 1_000_000) * self.settings.cost_per_1m_input_tokens
        output_cost = (token_usage.output / 1_000_000) * self.settings.cost_per_1m_output_tokens
        return round(input_cost + output_cost, 6)

    def get_circuit_state(self) -> Optional[CircuitState]:
        """
        Get current circuit breaker state.
        """
        if self.circuit_breaker:
            return self.circuit_breaker.get_state()
        return None


# Global instance
_llm_service: Optional[LLMService] = None


def get_llm_service(client: Optional[OpenAI] = None) -> LLMService:
    """
    Get global LLMService instance.
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(client=client)
    return _llm_service
