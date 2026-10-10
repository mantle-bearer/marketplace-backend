import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("plans")


def get_cached_plans_response():
    """Retrieves cached active plans response from Redis or returns None on cache miss."""
    try:
        cached = cache.get(settings.PLAN_CACHE_KEY)
        if cached is not None:
            logger.info("Serving active plans list from cache.")
            return cached
    except Exception as exc:
        logger.warning(f"Cache read error: {exc}")
    return None


def set_cached_plans_response(data):
    """Caches the active plans list in Redis with configured TTL."""
    try:
        cache.set(settings.PLAN_CACHE_KEY, data, timeout=settings.PLAN_CACHE_TTL)
        logger.info(f"Cached active plans list for {settings.PLAN_CACHE_TTL}s.")
    except Exception as exc:
        logger.warning(f"Cache write error: {exc}")


def invalidate_plans_cache():
    """
    Invalidates the cached active plans list whenever a plan is created, updated, or deleted.
    """
    try:
        cache.delete(settings.PLAN_CACHE_KEY)
        logger.info("Invalidated active plans cache.")
    except Exception as exc:
        logger.warning(f"Cache invalidation error: {exc}")
