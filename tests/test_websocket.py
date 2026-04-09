"""
Unit tests for src/web/websocket/chat.py.

Scope:
- _normalize_image_attachments() — pure function, tested directly.
- ConnectionManager — async class, tested with AsyncMock WebSocket.

No database, LLM, or network I/O is exercised here.
Run with:
    .venv/bin/python -m pytest tests/test_websocket.py -v --no-cov
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.config.settings import settings
from src.web.websocket.chat import ConnectionManager, _normalize_image_attachments

# ---------------------------------------------------------------------------
# Helper factories — produce valid test data without duplicating constants
# ---------------------------------------------------------------------------

_MINIMAL_JPEG_BYTES = bytes(
    [
        0xFF,
        0xD8,
        0xFF,
        0xE0,
        0x00,
        0x10,
        0x4A,
        0x46,
        0x49,
        0x46,
        0x00,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0xFF,
        0xD9,
    ]
)

_MINIMAL_PNG_BYTES = bytes(
    [
        0x89,
        0x50,
        0x4E,
        0x47,
        0x0D,
        0x0A,
        0x1A,
        0x0A,
        0x00,
        0x00,
        0x00,
        0x0D,
        0x49,
        0x48,
        0x44,
        0x52,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x01,
        0x08,
        0x02,
        0x00,
        0x00,
        0x00,
        0x90,
        0x77,
        0x53,
        0xDE,
        0x00,
        0x00,
        0x00,
        0x0C,
        0x49,
        0x44,
        0x41,
        0x54,
        0x08,
        0xD7,
        0x63,
        0xF8,
        0xCF,
        0xC0,
        0x00,
        0x00,
        0x00,
        0x02,
        0x00,
        0x01,
        0xE2,
        0x21,
        0xBC,
        0x33,
        0x00,
        0x00,
        0x00,
        0x00,
        0x49,
        0x45,
        0x4E,
        0x44,
        0xAE,
        0x42,
        0x60,
        0x82,
    ]
)


def _make_data_url(media_type: str, raw_bytes: bytes) -> str:
    """Return a well-formed data URL for *raw_bytes* with *media_type*."""
    encoded = base64.b64encode(raw_bytes).decode()
    return f"data:{media_type};base64,{encoded}"


def _valid_jpeg_attachment(filename: str = "photo.jpg") -> dict:
    return {
        "data_url": _make_data_url("image/jpeg", _MINIMAL_JPEG_BYTES),
        "media_type": "image/jpeg",
        "filename": filename,
    }


def _valid_png_attachment(filename: str = "scan.png") -> dict:
    return {
        "data_url": _make_data_url("image/png", _MINIMAL_PNG_BYTES),
        "media_type": "image/png",
        "filename": filename,
    }


def _valid_webp_attachment(filename: str = "image.webp") -> dict:
    # Any short byte sequence is enough — we test the contract, not real WEBP decoding.
    raw = b"RIFF\x24\x00\x00\x00WEBPVP8 "
    return {
        "data_url": _make_data_url("image/webp", raw),
        "media_type": "image/webp",
        "filename": filename,
    }


def _oversized_jpeg_attachment() -> dict:
    """Attachment whose decoded payload exceeds MAX_IMAGE_SIZE_MB."""
    big_bytes = b"A" * ((settings.MAX_IMAGE_SIZE_MB * 1024 * 1024) + 1)
    return {
        "data_url": _make_data_url("image/jpeg", big_bytes),
        "media_type": "image/jpeg",
        "filename": "big.jpg",
    }


def _mock_websocket() -> AsyncMock:
    """Return a fully mocked WebSocket with the methods ConnectionManager uses."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ===========================================================================
# _normalize_image_attachments — unit tests
# ===========================================================================


class TestNormalizeImageAttachments:
    """Tests for the pure validation/normalisation function."""

    # --- happy-path cases ---------------------------------------------------

    def test_empty_list_returns_empty(self):
        """An empty list must yield an empty list — no side-effects."""
        result = _normalize_image_attachments([])
        assert result == []

    def test_none_returns_empty(self):
        """None input must return empty list (defensive guard)."""
        result = _normalize_image_attachments(None)
        assert result == []

    @pytest.mark.parametrize(
        ("attachment_factory", "expected_media_type"),
        [
            (_valid_jpeg_attachment, "image/jpeg"),
            (_valid_png_attachment, "image/png"),
            (_valid_webp_attachment, "image/webp"),
        ],
        ids=["jpeg", "png", "webp"],
    )
    def test_valid_single_attachment_accepted(self, attachment_factory, expected_media_type):
        """Each allowed MIME type must be normalised and returned."""
        result = _normalize_image_attachments([attachment_factory()])

        assert len(result) == 1
        item = result[0]
        assert item["type"] == "image"
        assert item["media_type"] == expected_media_type
        assert "data_url" in item
        assert "filename" in item
        assert isinstance(item["size_bytes"], int)
        assert item["size_bytes"] > 0

    def test_multiple_valid_attachments_up_to_limit(self):
        """Up to MAX_IMAGE_ATTACHMENTS attachments must all be returned."""
        attachments = [
            _valid_jpeg_attachment("a.jpg"),
            _valid_png_attachment("b.png"),
            _valid_webp_attachment("c.webp"),
        ]
        assert len(attachments) == settings.MAX_IMAGE_ATTACHMENTS

        result = _normalize_image_attachments(attachments)
        assert len(result) == settings.MAX_IMAGE_ATTACHMENTS

    def test_normalised_output_shape_is_complete(self):
        """Every normalised item must carry the five expected keys."""
        result = _normalize_image_attachments([_valid_jpeg_attachment()])
        item = result[0]
        assert set(item.keys()) == {"type", "filename", "media_type", "data_url", "size_bytes"}

    def test_filename_falls_back_to_generated_name_when_absent(self):
        """If 'filename' key is missing, function must generate image_N."""
        attachment = _valid_jpeg_attachment()
        del attachment["filename"]

        result = _normalize_image_attachments([attachment])
        assert result[0]["filename"] == "image_1"

    def test_size_bytes_matches_actual_decoded_size(self):
        """size_bytes in output must equal the true byte length of the image."""
        result = _normalize_image_attachments([_valid_jpeg_attachment()])
        assert result[0]["size_bytes"] == len(_MINIMAL_JPEG_BYTES)

    # --- error cases --------------------------------------------------------

    def test_too_many_attachments_raises(self):
        """Exceeding MAX_IMAGE_ATTACHMENTS must raise ValueError."""
        too_many = [
            _valid_jpeg_attachment(f"img{i}.jpg")
            for i in range(settings.MAX_IMAGE_ATTACHMENTS + 1)
        ]
        with pytest.raises(ValueError, match=str(settings.MAX_IMAGE_ATTACHMENTS)):
            _normalize_image_attachments(too_many)

    @pytest.mark.parametrize(
        "bad_attachment",
        [
            {"media_type": "image/jpeg", "filename": "x.jpg"},  # missing data_url key
            {"data_url": None, "media_type": "image/jpeg"},  # data_url is None
            {"data_url": "", "media_type": "image/jpeg"},  # data_url is empty string
            {"data_url": "no-comma-here", "media_type": "image/jpeg"},  # no comma separator
        ],
        ids=["missing_key", "none_data_url", "empty_data_url", "no_comma"],
    )
    def test_missing_or_invalid_data_url_raises(self, bad_attachment):
        """Missing or malformed data_url must raise ValueError."""
        with pytest.raises(ValueError, match="data URL válido"):
            _normalize_image_attachments([bad_attachment])

    @pytest.mark.parametrize(
        "unsupported_type",
        ["image/gif", "image/bmp", "image/tiff", "application/pdf", "text/plain", ""],
        ids=["gif", "bmp", "tiff", "pdf", "text", "empty"],
    )
    def test_unsupported_media_type_raises(self, unsupported_type):
        """Media types not in ALLOWED_IMAGE_MEDIA_TYPES must raise ValueError."""
        attachment = {
            "data_url": _make_data_url("image/jpeg", _MINIMAL_JPEG_BYTES),
            "media_type": unsupported_type,
            "filename": "bad.gif",
        }
        with pytest.raises(ValueError, match="Formato de imagen no soportado"):
            _normalize_image_attachments([attachment])

    def test_mime_mismatch_between_header_and_media_type_raises(self):
        """data_url header must agree with declared media_type, or raise ValueError."""
        attachment = {
            # data_url says JPEG but media_type says PNG
            "data_url": _make_data_url("image/jpeg", _MINIMAL_JPEG_BYTES),
            "media_type": "image/png",
            "filename": "mismatch.jpg",
        }
        with pytest.raises(ValueError, match="cabecera"):
            _normalize_image_attachments([attachment])

    def test_invalid_base64_data_raises(self):
        """Non-base64 payload in data_url must raise ValueError."""
        attachment = {
            "data_url": "data:image/jpeg;base64,!!!this is not base64!!!",
            "media_type": "image/jpeg",
            "filename": "corrupt.jpg",
        }
        with pytest.raises(ValueError, match="base64 válido"):
            _normalize_image_attachments([attachment])

    def test_oversized_image_raises(self):
        """Image whose decoded size exceeds MAX_IMAGE_SIZE_MB must raise ValueError."""
        with pytest.raises(ValueError, match=str(settings.MAX_IMAGE_SIZE_MB)):
            _normalize_image_attachments([_oversized_jpeg_attachment()])

    def test_non_dict_item_in_list_raises(self):
        """A non-dict element inside the attachments list must raise ValueError."""
        with pytest.raises(ValueError, match="inválido"):
            _normalize_image_attachments(["not_a_dict"])  # type: ignore[list-item]

    def test_non_dict_item_at_second_position_raises_with_correct_index(self):
        """Error message for a non-dict item must reference its 1-based position."""
        with pytest.raises(ValueError, match="posición 2"):
            _normalize_image_attachments([_valid_jpeg_attachment(), 42])  # type: ignore[list-item]

    def test_first_attachment_valid_second_invalid_raises(self):
        """Mixed-validity list: function must still raise on the invalid entry."""
        with pytest.raises(ValueError):
            _normalize_image_attachments([_valid_jpeg_attachment(), _oversized_jpeg_attachment()])

    def test_base64_data_without_padding_raises(self):
        """Strictly-validated base64 with stripped padding must raise."""
        raw_b64 = base64.b64encode(_MINIMAL_JPEG_BYTES).decode().rstrip("=")
        attachment = {
            "data_url": f"data:image/jpeg;base64,{raw_b64}",
            "media_type": "image/jpeg",
            "filename": "nopad.jpg",
        }
        # validate=True in the source requires correct padding
        with pytest.raises(ValueError, match="base64 válido"):
            _normalize_image_attachments([attachment])

    # --- boundary / edge cases ----------------------------------------------

    def test_exactly_at_size_limit_is_accepted(self):
        """An image exactly at MAX_IMAGE_SIZE_MB must be accepted (not rejected)."""
        at_limit_bytes = b"B" * (settings.MAX_IMAGE_SIZE_MB * 1024 * 1024)
        attachment = {
            "data_url": _make_data_url("image/jpeg", at_limit_bytes),
            "media_type": "image/jpeg",
            "filename": "limit.jpg",
        }
        result = _normalize_image_attachments([attachment])
        assert result[0]["size_bytes"] == len(at_limit_bytes)

    def test_exactly_at_attachment_limit_is_accepted(self):
        """Exactly MAX_IMAGE_ATTACHMENTS attachments must not raise."""
        attachments = [
            _valid_jpeg_attachment(f"x{i}.jpg") for i in range(settings.MAX_IMAGE_ATTACHMENTS)
        ]
        result = _normalize_image_attachments(attachments)
        assert len(result) == settings.MAX_IMAGE_ATTACHMENTS


# ===========================================================================
# ConnectionManager — async unit tests
# ===========================================================================


class TestConnectionManager:
    """Tests for the WebSocket connection lifecycle manager."""

    # --- connect() ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        """connect() must call websocket.accept() exactly once."""
        manager = ConnectionManager()
        ws = _mock_websocket()

        await manager.connect("session-1", ws)

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_registers_connection_by_session_id(self):
        """After connect(), the session_id must be present in active_connections."""
        manager = ConnectionManager()
        ws = _mock_websocket()

        await manager.connect("session-abc", ws)

        assert "session-abc" in manager.active_connections
        assert manager.active_connections["session-abc"] is ws

    @pytest.mark.asyncio
    async def test_connect_closes_old_connection_on_duplicate_session(self):
        """If session_id is already connected, the old WebSocket must be closed."""
        manager = ConnectionManager()
        old_ws = _mock_websocket()
        new_ws = _mock_websocket()

        await manager.connect("session-dup", old_ws)
        await manager.connect("session-dup", new_ws)

        old_ws.close.assert_awaited_once_with(code=4409, reason="Session connected elsewhere")

    @pytest.mark.asyncio
    async def test_connect_replaces_old_with_new_websocket(self):
        """After reconnect, active_connections must hold only the new WebSocket."""
        manager = ConnectionManager()
        old_ws = _mock_websocket()
        new_ws = _mock_websocket()

        await manager.connect("session-replace", old_ws)
        await manager.connect("session-replace", new_ws)

        assert manager.active_connections["session-replace"] is new_ws

    @pytest.mark.asyncio
    async def test_connect_suppresses_exception_from_old_close(self):
        """Even if old WebSocket.close() raises, connect() must not propagate the error."""
        manager = ConnectionManager()
        old_ws = _mock_websocket()
        old_ws.close = AsyncMock(side_effect=RuntimeError("already gone"))
        new_ws = _mock_websocket()

        # Must not raise despite the broken old WebSocket
        await manager.connect("session-broken", old_ws)
        await manager.connect("session-broken", new_ws)

        assert "session-broken" in manager.active_connections

    @pytest.mark.asyncio
    async def test_connect_multiple_independent_sessions(self):
        """Different session IDs must not interfere with each other."""
        manager = ConnectionManager()
        ws_a = _mock_websocket()
        ws_b = _mock_websocket()

        await manager.connect("session-A", ws_a)
        await manager.connect("session-B", ws_b)

        assert manager.active_connections["session-A"] is ws_a
        assert manager.active_connections["session-B"] is ws_b
        # No cross-close calls
        ws_a.close.assert_not_awaited()
        ws_b.close.assert_not_awaited()

    # --- disconnect() -------------------------------------------------------

    def test_disconnect_removes_known_session(self):
        """disconnect() must remove the session_id from active_connections."""
        manager = ConnectionManager()
        manager.active_connections["session-x"] = MagicMock()

        manager.disconnect("session-x")

        assert "session-x" not in manager.active_connections

    def test_disconnect_unknown_session_does_not_raise(self):
        """disconnect() on a session that was never registered must be a no-op."""
        manager = ConnectionManager()

        # Must not raise KeyError or any other exception
        manager.disconnect("session-never-connected")

    def test_disconnect_only_removes_target_session(self):
        """disconnect() must not touch any other registered session."""
        manager = ConnectionManager()
        manager.active_connections["session-keep"] = MagicMock()
        manager.active_connections["session-drop"] = MagicMock()

        manager.disconnect("session-drop")

        assert "session-keep" in manager.active_connections
        assert "session-drop" not in manager.active_connections

    # --- send_json() --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_json_delivers_to_correct_session(self):
        """send_json() must call send_json() on the matching WebSocket."""
        manager = ConnectionManager()
        ws = _mock_websocket()
        manager.active_connections["session-send"] = ws

        payload = {"type": "thinking", "agent_name": "Triaje"}
        await manager.send_json("session-send", payload)

        ws.send_json.assert_awaited_once_with(payload)

    @pytest.mark.asyncio
    async def test_send_json_unknown_session_does_nothing(self):
        """send_json() for an unknown session_id must silently do nothing."""
        manager = ConnectionManager()
        ws = _mock_websocket()
        manager.active_connections["session-other"] = ws

        # Sending to a different, non-existent session
        await manager.send_json("session-ghost", {"type": "error"})

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_json_does_not_cross_sessions(self):
        """A message for session A must never be delivered to session B."""
        manager = ConnectionManager()
        ws_a = _mock_websocket()
        ws_b = _mock_websocket()
        manager.active_connections["session-A"] = ws_a
        manager.active_connections["session-B"] = ws_b

        await manager.send_json("session-A", {"type": "agent_response", "content": "hello"})

        ws_a.send_json.assert_awaited_once()
        ws_b.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_json_after_disconnect_does_nothing(self):
        """After disconnect(), send_json() must not reach the removed WebSocket."""
        manager = ConnectionManager()
        ws = _mock_websocket()
        manager.active_connections["session-gone"] = ws

        manager.disconnect("session-gone")
        await manager.send_json("session-gone", {"type": "ping"})

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_json_passes_payload_unchanged(self):
        """send_json() must not mutate or wrap the payload before forwarding it."""
        manager = ConnectionManager()
        ws = _mock_websocket()
        manager.active_connections["session-intact"] = ws

        original_payload: dict = {
            "type": "graph_update",
            "node": "triage_node",
            "data": {"evaluations": []},
        }
        await manager.send_json("session-intact", original_payload)

        sent_arg = ws.send_json.await_args.args[0]
        assert sent_arg is original_payload
