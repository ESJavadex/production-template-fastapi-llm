"""
Cost tracking and budget management system.
Tracks LLM costs per user/feature and sends alerts when budgets are exceeded.
"""
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from redis.asyncio import Redis

from app.config.settings import get_settings
from app.models.schemas import CostTrackingRecord, TokenUsage

logger = logging.getLogger(__name__)


class CostTracker:
    """
    Tracks LLM costs and enforces budgets.
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        self.settings = get_settings()
        self.redis_client = redis_client

    async def _get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.settings.rate_limit_redis_url,  # Reuse rate limit Redis
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis_client

    async def track_cost(
        self,
        request_id: str,
        user_id: Optional[str],
        token_usage: TokenUsage,
        cost_usd: float,
        model: str,
        feature: str = "chat",
        cached: bool = False
    ):
        """
        Track cost for a request.

        Args:
            request_id: Unique request ID
            user_id: User ID (optional)
            token_usage: Token usage details
            cost_usd: Cost in USD
            model: Model used
            feature: Feature/endpoint name
            cached: Whether response was from cache
        """
        if not self.settings.cost_tracking_enabled:
            return

        try:
            record = CostTrackingRecord(
                request_id=request_id,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                model=model,
                tokens_input=token_usage.input,
                tokens_output=token_usage.output,
                cost_usd=cost_usd,
                cached=cached,
                feature=feature
            )

            # Store in Redis with daily/monthly aggregations
            await self._store_cost_record(record)

            # Check budget alerts
            await self._check_budget_alerts(record)

            logger.info(
                f"Cost tracked: request_id={request_id}, "
                f"user_id={user_id}, cost=${cost_usd:.6f}, "
                f"tokens={token_usage.total}, cached={cached}"
            )

        except Exception as e:
            logger.error(f"Failed to track cost: {e}")

    async def _store_cost_record(self, record: CostTrackingRecord):
        """
        Store cost record in Redis with aggregations.
        """
        redis_client = await self._get_redis()

        # Keys for aggregation
        today = datetime.utcnow().strftime("%Y-%m-%d")
        month = datetime.utcnow().strftime("%Y-%m")

        # Daily aggregation
        daily_key = f"costs:daily:{today}"
        await redis_client.hincrby(daily_key, "count", 1)
        await redis_client.hincrbyfloat(daily_key, "total_cost", record.cost_usd)
        await redis_client.hincrbyfloat(daily_key, "total_tokens", record.tokens_input + record.tokens_output)
        await redis_client.expire(daily_key, 86400 * 90)  # Keep for 90 days

        # Monthly aggregation
        monthly_key = f"costs:monthly:{month}"
        await redis_client.hincrby(monthly_key, "count", 1)
        await redis_client.hincrbyfloat(monthly_key, "total_cost", record.cost_usd)
        await redis_client.hincrbyfloat(monthly_key, "total_tokens", record.tokens_input + record.tokens_output)
        await redis_client.expire(monthly_key, 86400 * 365)  # Keep for 1 year

        # Per-user aggregation (if user_id provided)
        if record.user_id:
            user_daily_key = f"costs:user:{record.user_id}:daily:{today}"
            await redis_client.hincrby(user_daily_key, "count", 1)
            await redis_client.hincrbyfloat(user_daily_key, "total_cost", record.cost_usd)
            await redis_client.expire(user_daily_key, 86400 * 90)

        # Per-feature aggregation
        feature_daily_key = f"costs:feature:{record.feature}:daily:{today}"
        await redis_client.hincrby(feature_daily_key, "count", 1)
        await redis_client.hincrbyfloat(feature_daily_key, "total_cost", record.cost_usd)
        await redis_client.expire(feature_daily_key, 86400 * 90)

        # Store individual record (for audit trail)
        record_key = f"costs:record:{record.request_id}"
        await redis_client.set(
            record_key,
            json.dumps(record.dict(), default=str),
            ex=86400 * 90  # Keep for 90 days
        )

    async def _check_budget_alerts(self, record: CostTrackingRecord):
        """
        Check if cost exceeds budget thresholds and send alerts.
        """
        redis_client = await self._get_redis()

        # Get daily cost
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_key = f"costs:daily:{today}"
        daily_cost_str = await redis_client.hget(daily_key, "total_cost")
        daily_cost = float(daily_cost_str) if daily_cost_str else 0.0

        # Get monthly cost
        month = datetime.utcnow().strftime("%Y-%m")
        monthly_key = f"costs:monthly:{month}"
        monthly_cost_str = await redis_client.hget(monthly_key, "total_cost")
        monthly_cost = float(monthly_cost_str) if monthly_cost_str else 0.0

        # Check daily budget
        daily_threshold = self.settings.cost_budget_daily_usd * self.settings.cost_alert_threshold
        if daily_cost >= daily_threshold:
            await self._send_budget_alert(
                "daily",
                daily_cost,
                self.settings.cost_budget_daily_usd,
                self.settings.cost_alert_threshold
            )

        # Check monthly budget
        monthly_threshold = self.settings.cost_budget_monthly_usd * self.settings.cost_alert_threshold
        if monthly_cost >= monthly_threshold:
            await self._send_budget_alert(
                "monthly",
                monthly_cost,
                self.settings.cost_budget_monthly_usd,
                self.settings.cost_alert_threshold
            )

    async def _send_budget_alert(
        self,
        period: str,
        current_cost: float,
        budget: float,
        threshold: float
    ):
        """
        Send budget alert (email, Slack, PagerDuty, etc.).
        """
        alert_key = f"costs:alert_sent:{period}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        redis_client = await self._get_redis()

        # Check if alert already sent today
        alert_sent = await redis_client.get(alert_key)
        if alert_sent:
            return

        percentage = (current_cost / budget) * 100

        logger.critical(
            f"BUDGET ALERT: {period.upper()} cost ${current_cost:.2f} "
            f"has reached {percentage:.1f}% of budget ${budget:.2f} "
            f"(threshold: {threshold*100:.0f}%)"
        )

        # In production, send email/Slack/PagerDuty alert here
        # if self.settings.cost_alert_email:
        #     send_email(
        #         to=self.settings.cost_alert_email,
        #         subject=f"Budget Alert: {period} cost at {percentage:.1f}%",
        #         body=f"Current cost: ${current_cost:.2f}\nBudget: ${budget:.2f}"
        #     )

        # Mark alert as sent (expires after 24 hours)
        await redis_client.set(alert_key, "1", ex=86400)

    async def get_daily_cost(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get daily cost summary.
        """
        redis_client = await self._get_redis()
        date_str = (date or datetime.utcnow()).strftime("%Y-%m-%d")
        daily_key = f"costs:daily:{date_str}"

        data = await redis_client.hgetall(daily_key)

        if not data:
            return {
                "date": date_str,
                "count": 0,
                "total_cost": 0.0,
                "total_tokens": 0
            }

        return {
            "date": date_str,
            "count": int(data.get("count", 0)),
            "total_cost": float(data.get("total_cost", 0.0)),
            "total_tokens": int(float(data.get("total_tokens", 0)))
        }

    async def get_monthly_cost(self, month: Optional[str] = None) -> Dict[str, Any]:
        """
        Get monthly cost summary.

        Args:
            month: Month in format "YYYY-MM" (default: current month)
        """
        redis_client = await self._get_redis()
        month_str = month or datetime.utcnow().strftime("%Y-%m")
        monthly_key = f"costs:monthly:{month_str}"

        data = await redis_client.hgetall(monthly_key)

        if not data:
            return {
                "month": month_str,
                "count": 0,
                "total_cost": 0.0,
                "total_tokens": 0
            }

        return {
            "month": month_str,
            "count": int(data.get("count", 0)),
            "total_cost": float(data.get("total_cost", 0.0)),
            "total_tokens": int(float(data.get("total_tokens", 0)))
        }

    async def get_user_cost(self, user_id: str, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get cost for a specific user.
        """
        redis_client = await self._get_redis()
        date_str = (date or datetime.utcnow()).strftime("%Y-%m-%d")
        user_key = f"costs:user:{user_id}:daily:{date_str}"

        data = await redis_client.hgetall(user_key)

        if not data:
            return {
                "user_id": user_id,
                "date": date_str,
                "count": 0,
                "total_cost": 0.0
            }

        return {
            "user_id": user_id,
            "date": date_str,
            "count": int(data.get("count", 0)),
            "total_cost": float(data.get("total_cost", 0.0))
        }

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
_cost_tracker: Optional[CostTracker] = None


async def get_cost_tracker() -> CostTracker:
    """Get global CostTracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
