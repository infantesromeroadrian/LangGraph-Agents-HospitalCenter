"""Comprehensive unit tests for LLMService and DatabaseService."""

import json
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from openai import OpenAIError
from src.models.message import Message
from src.models.session import Session

# ---------------------------------------------------------------------------
# Helpers — build LLMService with a fully-mocked AsyncOpenAI client
# ---------------------------------------------------------------------------

def _make_llm_service(base_url: str = "https://api.openai.com/v1") -> "LLMService":  # noqa: F821
    """Return an LLMService instance whose AsyncOpenAI client is a MagicMock."""
    from src.services.llm_service import LLMService

    with patch("src.services.llm_service.settings") as mock_settings:
        mock_settings.OPENAI_BASE_URL = base_url
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.OPENAI_TIMEOUT = 60
        mock_settings.OPENAI_MODEL = "gpt-4o"
        mock_settings.OPENAI_TEMPERATURE = 0.7
        mock_settings.OPENAI_MAX_TOKENS = 2000

        # Prevent real HTTP client construction
        with patch("src.services.llm_service.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            service = LLMService()

    return service


def _make_db_service() -> "DatabaseService":  # noqa: F821
    """Return a DatabaseService with database_url set to a safe test value."""
    from src.services.database_service import DatabaseService

    with patch("src.services.database_service.settings") as mock_settings:
        mock_settings.DATABASE_URL = "postgresql://test:test@localhost/test_db"
        service = DatabaseService()

    return service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def llm_service():
    return _make_llm_service()


@pytest.fixture
def groq_llm_service():
    return _make_llm_service(base_url="https://api.groq.com/openai/v1")


@pytest.fixture
def db_service():
    return _make_db_service()


@pytest.fixture
def sample_messages_list():
    """Simple list of OpenAI-format message dicts."""
    return [
        {"role": "system", "content": "Eres un asistente médico."},
        {"role": "user", "content": "Tengo dolor de cabeza."},
    ]


@pytest.fixture
def sample_session():
    return Session(session_id=uuid4(), patient_info={"age": 45, "gender": "F"})


@pytest.fixture
def sample_message(sample_session):
    return Message(
        role="user",
        content="Tengo fiebre.",
        session_id=sample_session.session_id,
    )


# ===========================================================================
# LLMService Tests
# ===========================================================================

class TestLLMServiceComplete:
    """Tests for LLMService.complete()."""

    @pytest.mark.asyncio
    async def test_complete_success_returns_content(self, llm_service, sample_messages_list):
        """complete() extracts and returns the message content from the API response."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Puede ser una migraña tensional."

        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await llm_service.complete(sample_messages_list)

        assert result == "Puede ser una migraña tensional."
        llm_service.client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_none_content_returns_empty_string(self, llm_service, sample_messages_list):
        """complete() must return '' when API delivers content=None, not crash."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = None

        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await llm_service.complete(sample_messages_list)

        assert result == ""

    @pytest.mark.asyncio
    async def test_complete_propagates_openai_error(self, llm_service, sample_messages_list):
        """complete() must let OpenAIError bubble up after retries are exhausted."""
        # Disable tenacity retries so the test is fast

        llm_service.client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("connection failed")
        )

        with pytest.raises(OpenAIError):
            # tenacity will retry 3 times — we accept that but still expect the raise
            await llm_service.complete(sample_messages_list)

    @pytest.mark.asyncio
    async def test_complete_uses_max_tokens_for_groq(self, groq_llm_service, sample_messages_list):
        """Groq-compatible endpoints must receive max_tokens, not max_completion_tokens."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        groq_llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await groq_llm_service.complete(sample_messages_list)

        call_kwargs = groq_llm_service.client.chat.completions.create.call_args.kwargs
        assert "max_tokens" in call_kwargs
        assert "max_completion_tokens" not in call_kwargs

    @pytest.mark.asyncio
    async def test_complete_uses_max_completion_tokens_for_openai(
        self, llm_service, sample_messages_list
    ):
        """Standard OpenAI endpoints must receive max_completion_tokens, not max_tokens."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await llm_service.complete(sample_messages_list)

        call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
        assert "max_completion_tokens" in call_kwargs
        assert "max_tokens" not in call_kwargs

    @pytest.mark.asyncio
    async def test_complete_respects_temperature_override(self, llm_service, sample_messages_list):
        """Explicit temperature kwarg overrides the instance default."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await llm_service.complete(sample_messages_list, temperature=0.1)

        call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_complete_with_response_format(self, llm_service, sample_messages_list):
        """response_format is forwarded to the API when provided."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"key": "val"}'
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await llm_service.complete(
            sample_messages_list, response_format={"type": "json_object"}
        )

        call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_complete_without_response_format(self, llm_service, sample_messages_list):
        """response_format key must be absent when not requested."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "plain text"
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await llm_service.complete(sample_messages_list)

        call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
        assert "response_format" not in call_kwargs


class TestLLMServiceCompleteJson:
    """Tests for LLMService.complete_json()."""

    @pytest.mark.asyncio
    async def test_complete_json_success_returns_dict(self, llm_service, sample_messages_list):
        """complete_json() parses and returns a valid JSON string as a dict."""
        payload = {"urgency": "urgente", "specialties": ["cardiologia"]}
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(payload)
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await llm_service.complete_json(sample_messages_list)

        assert isinstance(result, dict)
        assert result["urgency"] == "urgente"
        assert result["specialties"] == ["cardiologia"]

    @pytest.mark.asyncio
    async def test_complete_json_invalid_json_raises_value_error(
        self, llm_service, sample_messages_list
    ):
        """complete_json() wraps JSONDecodeError in ValueError."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "esto no es JSON válido"
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="LLM no retornó JSON válido"):
            await llm_service.complete_json(sample_messages_list)

    @pytest.mark.asyncio
    async def test_complete_json_passes_json_object_format(self, llm_service, sample_messages_list):
        """complete_json() always requests response_format json_object."""
        payload = {"result": "ok"}
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(payload)
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await llm_service.complete_json(sample_messages_list)

        call_kwargs = llm_service.client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}


class TestLLMServiceStreamComplete:
    """Tests for LLMService.stream_complete()."""

    @pytest.mark.asyncio
    async def test_stream_complete_yields_chunks(self, llm_service, sample_messages_list):
        """stream_complete() yields each non-None chunk content in order."""
        chunks = ["Hola", " paciente", ", ¿cómo", " estás?"]

        def _make_chunk(text):
            c = MagicMock()
            c.choices[0].delta.content = text
            return c

        async def _async_iter():
            for text in chunks:
                yield _make_chunk(text)

        mock_stream = _async_iter()
        llm_service.client.chat.completions.create = AsyncMock(return_value=mock_stream)

        collected = []
        async for piece in llm_service.stream_complete(sample_messages_list):
            collected.append(piece)

        assert collected == chunks

    @pytest.mark.asyncio
    async def test_stream_complete_skips_none_chunks(self, llm_service, sample_messages_list):
        """stream_complete() must not yield chunks where delta.content is None."""
        def _chunk(text):
            c = MagicMock()
            c.choices[0].delta.content = text
            return c

        async def _async_iter():
            yield _chunk("first")
            yield _chunk(None)   # should be skipped
            yield _chunk("last")

        llm_service.client.chat.completions.create = AsyncMock(return_value=_async_iter())

        collected = []
        async for piece in llm_service.stream_complete(sample_messages_list):
            collected.append(piece)

        assert collected == ["first", "last"]

    @pytest.mark.asyncio
    async def test_stream_complete_uses_max_tokens_for_groq(
        self, groq_llm_service, sample_messages_list
    ):
        """Groq streaming must use max_tokens, not max_completion_tokens."""
        async def _empty():
            return
            yield  # make it an async generator

        groq_llm_service.client.chat.completions.create = AsyncMock(return_value=_empty())

        async for _ in groq_llm_service.stream_complete(sample_messages_list):
            pass

        call_kwargs = groq_llm_service.client.chat.completions.create.call_args.kwargs
        assert "max_tokens" in call_kwargs
        assert "max_completion_tokens" not in call_kwargs
        assert call_kwargs.get("stream") is True


class TestLLMServiceHelpers:
    """Tests for create_message() and format_conversation_history()."""

    def test_create_message_returns_correct_dict(self, llm_service):
        """create_message() produces a well-formed OpenAI message dict."""
        msg = llm_service.create_message("user", "Tengo tos.")
        assert msg == {"role": "user", "content": "Tengo tos."}

    @pytest.mark.parametrize("role", ["system", "user", "assistant"])
    def test_create_message_supports_all_roles(self, llm_service, role):
        """create_message() works for all three standard OpenAI roles."""
        msg = llm_service.create_message(role, "content")
        assert msg["role"] == role

    def test_format_conversation_history_empty(self, llm_service):
        """format_conversation_history() returns empty list for empty input."""
        assert llm_service.format_conversation_history([]) == []

    def test_format_conversation_history_single_message(self, llm_service):
        """format_conversation_history() maps role and content from Message objects."""
        msg = Message(role="user", content="Hola")
        result = llm_service.format_conversation_history([msg])

        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "Hola"}

    def test_format_conversation_history_preserves_order(self, llm_service):
        """format_conversation_history() maintains the original message sequence."""
        msgs = [
            Message(role="user", content="Mensaje 1"),
            Message(role="assistant", content="Respuesta 1"),
            Message(role="user", content="Mensaje 2"),
        ]
        result = llm_service.format_conversation_history(msgs)

        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["content"] == "Mensaje 2"

    def test_groq_detection_true(self):
        """is_groq_compatible is True when base_url contains api.groq.com."""
        service = _make_llm_service(base_url="https://api.groq.com/openai/v1")
        assert service.is_groq_compatible is True

    def test_groq_detection_false(self):
        """is_groq_compatible is False for standard OpenAI endpoint."""
        service = _make_llm_service(base_url="https://api.openai.com/v1")
        assert service.is_groq_compatible is False


# ===========================================================================
# DatabaseService Tests
# ===========================================================================

class TestDatabaseServiceEnsurePool:
    """Tests for DatabaseService._ensure_pool() lifecycle logic."""

    @pytest.mark.asyncio
    async def test_ensure_pool_creates_pool_when_none(self, db_service):
        """_ensure_pool() calls connect() when pool is None."""
        assert db_service.pool is None

        mock_pool = MagicMock()
        with patch("src.services.database_service.asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            await db_service._ensure_pool()

        assert db_service.pool is mock_pool

    @pytest.mark.asyncio
    async def test_ensure_pool_recreates_on_pid_change(self, db_service):
        """_ensure_pool() closes the old pool and creates a new one when PID changes."""
        old_pool = AsyncMock()
        db_service.pool = old_pool
        db_service._worker_pid = 99999  # force PID mismatch

        new_pool = MagicMock()
        with patch("src.services.database_service.asyncpg.create_pool", new=AsyncMock(return_value=new_pool)):
            await db_service._ensure_pool()

        old_pool.close.assert_called_once()
        assert db_service.pool is new_pool

    @pytest.mark.asyncio
    async def test_ensure_pool_noop_when_pool_exists_and_pid_matches(self, db_service):
        """_ensure_pool() does nothing when the pool exists and PID is current."""
        mock_pool = MagicMock()
        db_service.pool = mock_pool
        db_service._worker_pid = os.getpid()

        with patch("src.services.database_service.asyncpg.create_pool") as mock_create:
            await db_service._ensure_pool()

        mock_create.assert_not_called()
        assert db_service.pool is mock_pool


class TestDatabaseServiceGetConnection:
    """Tests for DatabaseService.get_connection()."""

    @pytest.mark.asyncio
    async def test_get_connection_acquires_and_releases(self, db_service):
        """get_connection() yields connection and releases it in the finally block."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()  # health check passes

        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_pool.release = AsyncMock()
        db_service.pool = mock_pool
        db_service._worker_pid = os.getpid()

        async with db_service.get_connection() as conn:
            assert conn is mock_conn

        mock_pool.release.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_get_connection_reconnects_on_corrupt_connection(self, db_service):
        """get_connection() releases the corrupted conn, reconnects, and returns fresh conn."""
        corrupt_conn = AsyncMock()
        corrupt_conn.execute = AsyncMock(side_effect=Exception("connection reset"))

        fresh_conn = AsyncMock()
        fresh_conn.execute = AsyncMock()

        call_count = 0

        async def acquire_side_effect(timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return corrupt_conn
            return fresh_conn

        mock_pool = AsyncMock()
        mock_pool.acquire = acquire_side_effect
        mock_pool.release = AsyncMock()
        db_service.pool = mock_pool
        db_service._worker_pid = os.getpid()

        new_pool = AsyncMock()
        new_pool.acquire = AsyncMock(return_value=fresh_conn)
        new_pool.release = AsyncMock()

        with patch("src.services.database_service.asyncpg.create_pool", new=AsyncMock(return_value=new_pool)):
            async with db_service.get_connection() as conn:
                assert conn is fresh_conn


class TestDatabaseServiceDisconnect:
    """Tests for DatabaseService.disconnect()."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool_and_sets_none(self, db_service):
        """disconnect() calls pool.close() and sets pool to None."""
        mock_pool = AsyncMock()
        db_service.pool = mock_pool

        await db_service.disconnect()

        mock_pool.close.assert_called_once()
        assert db_service.pool is None

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_pool_is_none(self, db_service):
        """disconnect() does not raise when pool is already None."""
        assert db_service.pool is None
        await db_service.disconnect()  # must not raise


class TestDatabaseServiceCreateSession:
    """Tests for DatabaseService.create_session()."""

    @pytest.mark.asyncio
    async def test_create_session_executes_insert(self, db_service, sample_session):
        """create_session() executes the INSERT and returns the same session object."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.create_session(sample_session)

        assert result is sample_session
        mock_conn.execute.assert_called_once()

        sql, *args = mock_conn.execute.call_args.args
        assert "INSERT INTO sessions" in sql
        assert sample_session.session_id in args

    @pytest.mark.asyncio
    async def test_create_session_serializes_patient_info_as_json(
        self, db_service, sample_session
    ):
        """patient_info dict is JSON-serialised before being passed to execute()."""
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        await db_service.create_session(sample_session)

        _, patient_info_arg, *_ = mock_conn.execute.call_args.args[1:]
        parsed = json.loads(patient_info_arg)
        assert parsed == sample_session.patient_info


class TestDatabaseServiceGetSession:
    """Tests for DatabaseService.get_session()."""

    @pytest.mark.asyncio
    async def test_get_session_returns_session_when_found(self, db_service, sample_session):
        """get_session() hydrates and returns a Session when a row is found."""
        row_dict = sample_session.to_dict()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row_dict)

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.get_session(sample_session.session_id)

        assert isinstance(result, Session)
        assert str(result.session_id) == str(sample_session.session_id)

    @pytest.mark.asyncio
    async def test_get_session_returns_none_when_not_found(self, db_service):
        """get_session() returns None when fetchrow yields nothing."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.get_session(uuid4())

        assert result is None


class TestDatabaseServiceAddMessage:
    """Tests for DatabaseService.add_message()."""

    @pytest.mark.asyncio
    async def test_add_message_executes_insert_and_returns_message(
        self, db_service, sample_message
    ):
        """add_message() executes INSERT and returns the same Message object."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.add_message(sample_message)

        assert result is sample_message
        mock_conn.execute.assert_called_once()
        sql, *args = mock_conn.execute.call_args.args
        assert "INSERT INTO messages" in sql

    @pytest.mark.asyncio
    async def test_add_message_serializes_metadata_as_json(self, db_service):
        """Metadata dict is JSON-serialised before being passed to execute()."""
        msg = Message(
            role="assistant",
            content="Respuesta médica.",
            session_id=uuid4(),
            metadata={"source": "triage", "confidence": 0.9},
        )

        mock_conn = AsyncMock()
        captured_args = []

        async def _capture(*args):
            captured_args.extend(args)

        mock_conn.execute = _capture

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        await db_service.add_message(msg)

        # metadata is the 6th positional arg (index 6): sql,$1,$2,$3,$4,$5,$6,$7
        metadata_arg = captured_args[6]
        parsed = json.loads(metadata_arg)
        assert parsed == msg.metadata


class TestDatabaseServiceGetSessionMessages:
    """Tests for DatabaseService.get_session_messages()."""

    @pytest.mark.asyncio
    async def test_get_session_messages_without_limit(self, db_service):
        """get_session_messages() fetches all rows when limit is None."""
        session_id = uuid4()
        row1 = Message(role="user", content="Hola", session_id=session_id).to_dict()
        row2 = Message(role="assistant", content="Hola paciente", session_id=session_id).to_dict()

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row1, row2])

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.get_session_messages(session_id)

        assert len(result) == 2
        assert isinstance(result[0], Message)

        sql = mock_conn.fetch.call_args.args[0]
        assert "LIMIT" not in sql

    @pytest.mark.asyncio
    async def test_get_session_messages_with_limit(self, db_service):
        """get_session_messages(limit=N) includes LIMIT clause and passes N as parameter."""
        session_id = uuid4()
        row = Message(role="user", content="Msg", session_id=session_id).to_dict()

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.get_session_messages(session_id, limit=1)

        assert len(result) == 1
        sql, *args = mock_conn.fetch.call_args.args
        assert "LIMIT" in sql
        assert 1 in args

    @pytest.mark.asyncio
    async def test_get_session_messages_empty_returns_empty_list(self, db_service):
        """get_session_messages() returns [] when no rows are found."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        result = await db_service.get_session_messages(uuid4())
        assert result == []


class TestDatabaseServiceCleanupOldSessions:
    """Tests for DatabaseService.cleanup_old_sessions()."""

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions_executes_delete(self, db_service):
        """cleanup_old_sessions() runs a DELETE statement with the correct days arg."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 7")

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        await db_service.cleanup_old_sessions(days=30)

        mock_conn.execute.assert_called_once()
        sql, *args = mock_conn.execute.call_args.args
        assert "DELETE FROM sessions" in sql
        assert 30 in args

    @pytest.mark.asyncio
    @pytest.mark.parametrize("days", [7, 30, 90])
    async def test_cleanup_old_sessions_passes_days_parameter(self, db_service, days):
        """cleanup_old_sessions() forwards the `days` parameter to the query."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=f"DELETE {days}")

        @asynccontextmanager
        async def _fake_get_connection():
            yield mock_conn

        db_service.get_connection = _fake_get_connection

        await db_service.cleanup_old_sessions(days=days)

        _, passed_days = mock_conn.execute.call_args.args
        assert passed_days == days


class TestDatabaseServiceConnect:
    """Tests for DatabaseService.connect() — pool creation."""

    @pytest.mark.asyncio
    async def test_connect_calls_asyncpg_create_pool(self, db_service):
        """connect() calls asyncpg.create_pool with the correct DATABASE_URL."""
        mock_pool = MagicMock()

        with patch(
            "src.services.database_service.asyncpg.create_pool",
            new=AsyncMock(return_value=mock_pool),
        ) as mock_create:
            await db_service.connect()

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        # First positional arg must be the database URL
        assert call_args.args[0] == "postgresql://test:test@localhost/test_db"
        assert db_service.pool is mock_pool

    @pytest.mark.asyncio
    async def test_connect_raises_on_asyncpg_failure(self, db_service):
        """connect() propagates the exception when asyncpg.create_pool fails."""
        with (
            patch(
                "src.services.database_service.asyncpg.create_pool",
                new=AsyncMock(side_effect=Exception("connection refused")),
            ),
            pytest.raises(Exception, match="connection refused"),
        ):
            await db_service.connect()
