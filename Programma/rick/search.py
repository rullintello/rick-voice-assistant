import hashlib
import logging
import time

from tavily import TavilyClient

from . import config, jsonstore


def _cache_key(query: str) -> str:
    return hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    cache = jsonstore.read_json(config.SEARCH_CACHE_FILE, {})
    return cache if isinstance(cache, dict) else {}


def _save_cache(cache: dict) -> None:
    try:
        jsonstore.write_json(config.SEARCH_CACHE_FILE, cache)
    except OSError:
        # the cache is only an optimization - failing to write it must not
        # cost the user the answer that was just found
        logging.exception("Couldn't save the search cache")


def search_web(query: str) -> str:
    """Returns a block of web-search snippets for `query`, or "" if search is
    unavailable or fails. Results are cached per-question so a repeated
    question (from anyone using Rick) doesn't spend the search quota again."""
    api_key = config.get_tavily_api_key()
    if not api_key:
        return ""

    key = _cache_key(query)
    cache = _load_cache()
    cached = cache.get(key)
    if not (isinstance(cached, dict) and isinstance(cached.get("context"), str)):
        cached = None
    if cached and (time.time() - cached.get("ts", 0)) < config.SEARCH_CACHE_TTL_HOURS * 3600:
        return cached["context"]

    try:
        response = TavilyClient(api_key=api_key).search(
            query, search_depth="basic", max_results=4, include_answer=False
        )
        results = response.get("results", [])
    except Exception:
        logging.exception("Web search failed")
        return cached["context"] if cached else ""

    if not results:
        return ""

    context = "\n".join(
        f"- {item.get('title', '')}: {item.get('content', '')} ({item.get('url', '')})"
        for item in results
    )

    cache[key] = {"ts": time.time(), "context": context}
    _save_cache(cache)
    return context
