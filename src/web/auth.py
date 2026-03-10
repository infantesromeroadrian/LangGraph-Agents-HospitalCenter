"""Autenticacion y autorizacion para API y WebSocket."""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Literal
from uuid import UUID

from fastapi import Cookie, Header, HTTPException, Response, WebSocket, status

from src.config.settings import settings

logger = logging.getLogger(__name__)

PATIENT_AUTH_COOKIE_NAME = "medical_patient_token"
SESSION_AUTH_COOKIE_NAME = "medical_session_token"
ADMIN_API_KEY_HEADER = "X-Admin-Key"

TOKEN_TYPE_PATIENT = "patient"
TOKEN_TYPE_SESSION = "session"

COOKIE_PATH = "/"
UNAUTHORIZED_DETAIL = "Autenticacion requerida."
FORBIDDEN_DETAIL = "No tienes permisos para este recurso."


class WebSocketAuthorizationError(Exception):
    """Error de autorizacion para WebSocket."""

    def __init__(self, close_code: int, reason: str):
        super().__init__(reason)
        self.close_code = close_code
        self.reason = reason


def _b64url_encode(data: bytes) -> str:
    """Codifica bytes en base64url sin padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Decodifica base64url con padding opcional."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _sign_token_segment(payload_segment: str) -> str:
    """Firma el payload serializado con HMAC SHA256."""
    secret_key = settings.get_token_signing_key().encode("utf-8")
    signature = hmac.new(secret_key, payload_segment.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(signature)


def _serialize_token_payload(payload: dict[str, Any]) -> str:
    """Serializa el payload de token en JSON compacto."""
    return _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _deserialize_token_payload(payload_segment: str) -> dict[str, Any]:
    """Deserializa el payload de token desde JSON compacto."""
    payload_bytes = _b64url_decode(payload_segment)
    return json.loads(payload_bytes.decode("utf-8"))


def _build_access_token(
    *,
    token_type: Literal["patient", "session"],
    medical_record_number: str,
    ttl_seconds: int,
    session_id: UUID | str | None = None,
) -> str:
    """Construye un token firmado para paciente o sesion."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "token_type": token_type,
        "medical_record_number": medical_record_number,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if session_id is not None:
        payload["session_id"] = str(session_id)

    payload_segment = _serialize_token_payload(payload)
    signature_segment = _sign_token_segment(payload_segment)
    return f"{payload_segment}.{signature_segment}"


def _decode_access_token(
    token: str | None,
    *,
    expected_type: Literal["patient", "session"],
) -> dict[str, Any]:
    """Valida firma, expiracion y tipo del token."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)

    try:
        payload_segment, signature_segment = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
        ) from exc

    expected_signature = _sign_token_segment(payload_segment)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
        )

    try:
        payload = _deserialize_token_payload(payload_segment)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
        ) from exc

    if payload.get("token_type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido.",
        )

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso expirado.",
        )

    return payload


def create_patient_access_token(medical_record_number: str) -> str:
    """Crea un token firmado para acceder a recursos del paciente."""
    return _build_access_token(
        token_type=TOKEN_TYPE_PATIENT,
        medical_record_number=medical_record_number,
        ttl_seconds=settings.PATIENT_TOKEN_TTL_HOURS * 3600,
    )


def create_session_access_token(session_id: UUID | str, medical_record_number: str) -> str:
    """Crea un token firmado para acceder a recursos de sesion."""
    return _build_access_token(
        token_type=TOKEN_TYPE_SESSION,
        medical_record_number=medical_record_number,
        ttl_seconds=settings.SESSION_TOKEN_TTL_HOURS * 3600,
        session_id=session_id,
    )


def _set_auth_cookie(
    response: Response, *, cookie_name: str, token: str, max_age_seconds: int
) -> None:
    """Configura una cookie HttpOnly para tokens de acceso."""
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=max_age_seconds,
        path=COOKIE_PATH,
    )


def set_patient_auth_cookie(response: Response, token: str) -> None:
    """Configura la cookie de acceso de paciente."""
    _set_auth_cookie(
        response,
        cookie_name=PATIENT_AUTH_COOKIE_NAME,
        token=token,
        max_age_seconds=settings.PATIENT_TOKEN_TTL_HOURS * 3600,
    )


def set_session_auth_cookie(response: Response, token: str) -> None:
    """Configura la cookie de acceso de sesion."""
    _set_auth_cookie(
        response,
        cookie_name=SESSION_AUTH_COOKIE_NAME,
        token=token,
        max_age_seconds=settings.SESSION_TOKEN_TTL_HOURS * 3600,
    )


def clear_session_auth_cookie(response: Response) -> None:
    """Elimina la cookie de sesion activa."""
    response.delete_cookie(
        key=SESSION_AUTH_COOKIE_NAME,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=COOKIE_PATH,
    )


def require_patient_token(
    patient_token: str | None = Cookie(default=None, alias=PATIENT_AUTH_COOKIE_NAME),
) -> dict[str, Any]:
    """Valida la cookie de paciente y devuelve su payload."""
    return _decode_access_token(patient_token, expected_type=TOKEN_TYPE_PATIENT)


def require_session_token(
    session_token: str | None = Cookie(default=None, alias=SESSION_AUTH_COOKIE_NAME),
) -> dict[str, Any]:
    """Valida la cookie de sesion y devuelve su payload."""
    return _decode_access_token(session_token, expected_type=TOKEN_TYPE_SESSION)


def require_admin_key(
    admin_api_key: str | None = Header(default=None, alias=ADMIN_API_KEY_HEADER),
) -> None:
    """Valida la clave administrativa para endpoints operativos."""
    expected_admin_key = settings.get_admin_api_key()
    if not admin_api_key or not hmac.compare_digest(admin_api_key, expected_admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)


def ensure_medical_record_access(token_payload: dict[str, Any], medical_record_number: str) -> None:
    """Comprueba que el token pertenece al paciente solicitado."""
    token_mrn = token_payload.get("medical_record_number")
    if token_mrn != medical_record_number:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)


def ensure_session_access(token_payload: dict[str, Any], session_id: UUID | str) -> None:
    """Comprueba que el token pertenece a la sesion solicitada."""
    token_session_id = token_payload.get("session_id")
    if token_session_id != str(session_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)


def require_websocket_session_access(websocket: WebSocket, session_id: str) -> dict[str, Any]:
    """Valida la cookie de sesion antes de aceptar el WebSocket."""
    session_token = websocket.cookies.get(SESSION_AUTH_COOKIE_NAME)
    if not session_token:
        raise WebSocketAuthorizationError(close_code=4401, reason=UNAUTHORIZED_DETAIL)

    try:
        token_payload = _decode_access_token(session_token, expected_type=TOKEN_TYPE_SESSION)
    except HTTPException as exc:
        raise WebSocketAuthorizationError(close_code=4401, reason=exc.detail) from exc

    if token_payload.get("session_id") != session_id:
        raise WebSocketAuthorizationError(close_code=4403, reason=FORBIDDEN_DETAIL)

    return token_payload
