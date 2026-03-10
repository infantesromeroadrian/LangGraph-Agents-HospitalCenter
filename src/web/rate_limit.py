"""Rate limiting sencillo en memoria para HTTP y WebSocket."""

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request, WebSocket, status

from src.config.settings import settings

RATE_LIMIT_ERROR_MESSAGE = (
    "Has alcanzado el limite temporal de solicitudes. Intentalo de nuevo en breve."
)
WEBSOCKET_RATE_LIMIT_ERROR_MESSAGE = (
    "Has alcanzado el limite temporal de mensajes. Espera un momento antes de continuar."
)


@dataclass(frozen=True)
class RateLimitRule:
    """Regla normalizada de rate limiting."""

    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    """Rate limiter por ventana fija usando timestamps en memoria."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, rule: RateLimitRule) -> int | None:
        """Registra un evento y devuelve retry_after si se supera el limite."""
        now = time.monotonic()
        with self._lock:
            bucket = self._events[key]
            cutoff = now - rule.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.limit:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return retry_after

            bucket.append(now)
            return None

    def reset(self) -> None:
        """Limpia todos los contadores. Util en tests."""
        with self._lock:
            self._events.clear()


_rate_limiter = InMemoryRateLimiter()


def _parse_rate_limit(raw_value: str) -> RateLimitRule:
    """Parsea valores del tipo `120/minute` o `30/hour`."""
    value = raw_value.strip().lower()
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        raise ValueError(f"Rate limit invalido: {raw_value}")

    unit = parts[1]
    if unit in {"second", "seconds", "sec", "s"}:
        window_seconds = 1
    elif unit in {"minute", "minutes", "min", "m"}:
        window_seconds = 60
    elif unit in {"hour", "hours", "h"}:
        window_seconds = 3600
    else:
        raise ValueError(f"Unidad de rate limit no soportada: {raw_value}")

    return RateLimitRule(limit=int(parts[0]), window_seconds=window_seconds)


def _client_ip(request: Request) -> str:
    """Obtiene la IP del cliente con fallback seguro."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _websocket_client_ip(websocket: WebSocket) -> str:
    """Obtiene la IP de un cliente WebSocket."""
    if websocket.client and websocket.client.host:
        return websocket.client.host
    return "unknown"


def _enforce_limit(key: str, rule: RateLimitRule) -> None:
    """Aplica un limite y lanza 429 si se supera."""
    retry_after = _rate_limiter.check(key, rule)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_ERROR_MESSAGE,
            headers={"Retry-After": str(retry_after)},
        )


async def enforce_read_rate_limit(request: Request) -> None:
    """Limita lecturas HTTP por IP de forma moderada."""
    rule = _parse_rate_limit(settings.RATE_LIMIT)
    _enforce_limit(f"http:read:{_client_ip(request)}", rule)


async def enforce_write_rate_limit(request: Request) -> None:
    """Limita escrituras HTTP por IP de forma mas estricta."""
    rule = _parse_rate_limit(settings.WRITE_RATE_LIMIT)
    _enforce_limit(f"http:write:{_client_ip(request)}", rule)


def enforce_websocket_message_rate_limit(websocket: WebSocket, session_id: str) -> int | None:
    """Aplica rate limit a mensajes del WebSocket y devuelve retry_after si se excede."""
    rule = _parse_rate_limit(settings.WEBSOCKET_RATE_LIMIT)
    client_ip = _websocket_client_ip(websocket)
    return _rate_limiter.check(f"ws:{session_id}:{client_ip}", rule)


def reset_rate_limits() -> None:
    """Resetea el estado del rate limiter global."""
    _rate_limiter.reset()
