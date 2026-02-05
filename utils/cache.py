# utils/cache.py — простое in-memory кэширование
import time
import logging
from typing import Any, Optional, Callable, Awaitable
from collections import defaultdict

logger = logging.getLogger(__name__)


class SimpleCache:
    """Простой in-memory кэш с TTL."""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._hits = defaultdict(int)
        self._misses = defaultdict(int)
    
    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Получить значение из кэша."""
        if key not in self._cache:
            self._misses[key] += 1
            return default
        
        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            self._misses[key] += 1
            return default
        
        self._hits[key] += 1
        return value
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        """Установить значение в кэш с TTL."""
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Удалить значение из кэша."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
        self._hits.clear()
        self._misses.clear()
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику кэша."""
        total_hits = sum(self._hits.values())
        total_misses = sum(self._misses.values())
        total_requests = total_hits + total_misses
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "hits": total_hits,
            "misses": total_misses,
            "hit_rate": f"{hit_rate:.2f}%",
        }


# Глобальный экземпляр кэша
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Получить глобальный экземпляр кэша."""
    return _cache


async def cached(
    key_prefix: str,
    ttl: int,
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Декоратор для кэширования результатов async функций.
    
    Args:
        key_prefix: Префикс ключа кэша
        ttl: Время жизни кэша в секундах
        func: Функция для выполнения
        *args, **kwargs: Аргументы функции
    
    Returns:
        Результат функции или из кэша
    """
    cache = get_cache()
    
    # Создаем ключ кэша из префикса и аргументов
    key_parts = [key_prefix]
    if args:
        key_parts.extend(str(arg) for arg in args)
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
    cache_key = ":".join(key_parts)
    
    # Пытаемся получить из кэша
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.debug(f"Cache hit: {cache_key}")
        return cached_value
    
    # Выполняем функцию и кэшируем результат
    logger.debug(f"Cache miss: {cache_key}")
    result = await func(*args, **kwargs)
    cache.set(cache_key, result, ttl)
    return result
