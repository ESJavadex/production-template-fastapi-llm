"""
Content moderation service using OpenAI Moderation API.
Provides pre-LLM and post-LLM moderation to ensure safe content.
"""
from typing import Optional
import logging
from datetime import datetime
from openai import OpenAI, OpenAIError

from app.config.settings import get_settings
from app.models.schemas import ModerationResult

logger = logging.getLogger(__name__)


class ModerationService:
    """
    Content moderation using OpenAI's Moderation API.
    """

    def __init__(self, client: Optional[OpenAI] = None):
        self.settings = get_settings()
        self.client = client or OpenAI(api_key=self.settings.openai_api_key)

    def moderate(self, content: str) -> ModerationResult:
        """
        Moderate content using OpenAI Moderation API.

        Args:
            content: Text content to moderate

        Returns:
            ModerationResult with flagged status and category scores
        """
        if not self.settings.moderation_enabled:
            # Moderation disabled, return safe result
            return ModerationResult(
                flagged=False,
                categories={},
                category_scores={},
                timestamp=datetime.utcnow()
            )

        try:
            response = self.client.moderations.create(input=content)
            result = response.results[0]

            # Convert to dict for easier handling
            categories = {
                "hate": result.categories.hate,
                "hate/threatening": result.categories.hate_threatening,
                "harassment": result.categories.harassment,
                "harassment/threatening": result.categories.harassment_threatening,
                "self-harm": result.categories.self_harm,
                "self-harm/intent": result.categories.self_harm_intent,
                "self-harm/instructions": result.categories.self_harm_instructions,
                "sexual": result.categories.sexual,
                "sexual/minors": result.categories.sexual_minors,
                "violence": result.categories.violence,
                "violence/graphic": result.categories.violence_graphic,
            }

            category_scores = {
                "hate": result.category_scores.hate,
                "hate/threatening": result.category_scores.hate_threatening,
                "harassment": result.category_scores.harassment,
                "harassment/threatening": result.category_scores.harassment_threatening,
                "self-harm": result.category_scores.self_harm,
                "self-harm/intent": result.category_scores.self_harm_intent,
                "self-harm/instructions": result.category_scores.self_harm_instructions,
                "sexual": result.category_scores.sexual,
                "sexual/minors": result.category_scores.sexual_minors,
                "violence": result.category_scores.violence,
                "violence/graphic": result.category_scores.violence_graphic,
            }

            flagged = result.flagged

            if flagged:
                logger.warning(
                    f"Content flagged by moderation: {categories}, scores: {category_scores}"
                )

            return ModerationResult(
                flagged=flagged,
                categories=categories,
                category_scores=category_scores,
                timestamp=datetime.utcnow()
            )

        except OpenAIError as e:
            logger.error(f"Moderation API error: {e}")
            # In case of error, fail safe: assume content is safe
            # (alternative: fail closed and block content)
            return ModerationResult(
                flagged=False,
                categories={},
                category_scores={},
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Unexpected moderation error: {e}")
            return ModerationResult(
                flagged=False,
                categories={},
                category_scores={},
                timestamp=datetime.utcnow()
            )

    def moderate_with_threshold(self, content: str, threshold: Optional[float] = None) -> ModerationResult:
        """
        Moderate content with custom threshold.

        Args:
            content: Text content to moderate
            threshold: Custom threshold (overrides config)

        Returns:
            ModerationResult with flagged status based on threshold
        """
        result = self.moderate(content)

        # Apply custom threshold if provided
        if threshold is None:
            threshold = self.settings.moderation_threshold

        # Check if any category score exceeds threshold
        max_score = max(result.category_scores.values()) if result.category_scores else 0.0

        if max_score >= threshold:
            result.flagged = True
            logger.warning(
                f"Content flagged by custom threshold {threshold}: max_score={max_score}"
            )

        return result

    def pre_llm_check(self, content: str) -> ModerationResult:
        """
        Check user input before sending to LLM.

        Args:
            content: User input

        Returns:
            ModerationResult
        """
        if not self.settings.moderation_pre_llm:
            return ModerationResult(
                flagged=False,
                categories={},
                category_scores={},
                timestamp=datetime.utcnow()
            )

        logger.debug("Running pre-LLM moderation check")
        return self.moderate(content)

    def post_llm_check(self, content: str) -> ModerationResult:
        """
        Check LLM output before sending to user.

        Args:
            content: LLM output

        Returns:
            ModerationResult
        """
        if not self.settings.moderation_post_llm:
            return ModerationResult(
                flagged=False,
                categories={},
                category_scores={},
                timestamp=datetime.utcnow()
            )

        logger.debug("Running post-LLM moderation check")
        return self.moderate(content)


# Global instance
_moderation_service: Optional[ModerationService] = None


def get_moderation_service(client: Optional[OpenAI] = None) -> ModerationService:
    """
    Get global ModerationService instance.
    """
    global _moderation_service
    if _moderation_service is None:
        _moderation_service = ModerationService(client=client)
    return _moderation_service
