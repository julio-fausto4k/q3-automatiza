import time
from typing import Any, Optional

class CacheManager:
    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        expires = time.time() + ttl if ttl and ttl > 0 else None
        self._store[key] = (value, expires)

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        value, expires = item
        if expires is not None and time.time() >= expires:
            self._store.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_pattern(self, prefix: str) -> None:
        for k in list(self._store.keys()):
            if k.startswith(prefix):
                self._store.pop(k, None)

    def clear(self) -> None:
        self._store.clear()

cache_manager = CacheManager()
