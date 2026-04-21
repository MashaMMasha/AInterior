import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest

from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan
from obllomov.services.events import (
    AsyncCompositeEventCallback,
    AsyncEventCallback,
    ChatEventCallback,
    CompositeEventCallback,
    EventCallback,
    LogEventCallback,
    RabbitMQEventCallback,
    StageEvent,
)


def _make_event(stage="floor", completed=1, total=8):
    return StageEvent(
        stage=stage,
        completed=completed,
        total=total,
        scene_plan=ScenePlan(query="test"),
        raw_scene_plan=RawScenePlan(),
    )


class TestStageEvent:
    def test_create_minimal(self):
        event = _make_event()
        assert event.stage == "floor"
        assert event.completed == 1
        assert event.total == 8
        assert event.scene_plan.query == "test"

    def test_serialization_roundtrip(self):
        event = _make_event()
        data = event.model_dump()
        restored = StageEvent.model_validate(data)
        assert restored.stage == event.stage
        assert restored.completed == event.completed


class TestLogEventCallback:
    def test_on_stage_logs(self, caplog):
        cb = LogEventCallback()
        with caplog.at_level("INFO"):
            cb.on_stage(_make_event("walls", 2, 8))
        assert "[2/8]" in caplog.text
        assert "walls" in caplog.text

    def test_on_complete_logs(self, caplog):
        cb = LogEventCallback()
        with caplog.at_level("INFO"):
            cb.on_complete(_make_event("completed", 8, 8))
        assert "completed" in caplog.text.lower()

    def test_on_error_logs(self, caplog):
        cb = LogEventCallback()
        with caplog.at_level("ERROR"):
            cb.on_error(RuntimeError("boom"))
        assert "boom" in caplog.text


class TestChatEventCallback:
    def test_on_stage_calls_save_stage(self):
        chat = MagicMock()
        cb = ChatEventCallback(chat, interaction_id=42)
        event = _make_event("floor", 1, 8)

        cb.on_stage(event)

        chat.save_stage.assert_called_once_with(
            42, "floor", event.scene_plan, event.raw_scene_plan
        )

    def test_on_complete_saves_completed_stage(self):
        chat = MagicMock()
        cb = ChatEventCallback(chat, interaction_id=42)
        event = _make_event("completed", 8, 8)

        cb.on_complete(event)

        chat.save_stage.assert_called_once_with(
            42, "completed", event.scene_plan, event.raw_scene_plan
        )

    def test_on_error_does_not_raise(self):
        chat = MagicMock()
        cb = ChatEventCallback(chat, interaction_id=42)
        cb.on_error(RuntimeError("fail"))


class TestCompositeEventCallback:
    def test_on_stage_calls_all(self):
        cb1 = MagicMock(spec=EventCallback)
        cb2 = MagicMock(spec=EventCallback)
        composite = CompositeEventCallback([cb1, cb2])
        event = _make_event()

        composite.on_stage(event)

        cb1.on_stage.assert_called_once_with(event)
        cb2.on_stage.assert_called_once_with(event)

    def test_on_complete_calls_all(self):
        cb1 = MagicMock(spec=EventCallback)
        cb2 = MagicMock(spec=EventCallback)
        composite = CompositeEventCallback([cb1, cb2])
        event = _make_event()

        composite.on_complete(event)

        cb1.on_complete.assert_called_once_with(event)
        cb2.on_complete.assert_called_once_with(event)

    def test_on_error_calls_all(self):
        cb1 = MagicMock(spec=EventCallback)
        cb2 = MagicMock(spec=EventCallback)
        composite = CompositeEventCallback([cb1, cb2])
        err = RuntimeError("x")

        composite.on_error(err)

        cb1.on_error.assert_called_once_with(err)
        cb2.on_error.assert_called_once_with(err)

    def test_empty_composite(self):
        composite = CompositeEventCallback([])
        composite.on_stage(_make_event())
        composite.on_complete(_make_event())
        composite.on_error(RuntimeError("x"))


class TestAsyncCompositeEventCallback:
    @pytest.mark.asyncio
    async def test_on_stage_calls_all(self):
        cb1 = AsyncMock(spec=AsyncEventCallback)
        cb2 = AsyncMock(spec=AsyncEventCallback)
        composite = AsyncCompositeEventCallback([cb1, cb2])
        event = _make_event()

        await composite.on_stage(event)

        cb1.on_stage.assert_awaited_once_with(event)
        cb2.on_stage.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_on_complete_calls_all(self):
        cb1 = AsyncMock(spec=AsyncEventCallback)
        cb2 = AsyncMock(spec=AsyncEventCallback)
        composite = AsyncCompositeEventCallback([cb1, cb2])
        event = _make_event()

        await composite.on_complete(event)

        cb1.on_complete.assert_awaited_once_with(event)
        cb2.on_complete.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_on_error_calls_all(self):
        cb1 = AsyncMock(spec=AsyncEventCallback)
        cb2 = AsyncMock(spec=AsyncEventCallback)
        composite = AsyncCompositeEventCallback([cb1, cb2])
        err = RuntimeError("x")

        await composite.on_error(err)

        cb1.on_error.assert_awaited_once_with(err)
        cb2.on_error.assert_awaited_once_with(err)


class TestRabbitMQEventCallback:
    @pytest.mark.asyncio
    async def test_on_stage_publishes(self):
        cb = RabbitMQEventCallback("amqp://guest:guest@localhost/", "gen-123")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            event = _make_event("floor", 1, 8)
            await cb.on_stage(event)

        mock_exchange.publish.assert_awaited_once()
        published_msg = mock_exchange.publish.call_args
        assert published_msg.kwargs["routing_key"] == "generation.gen-123"

    @pytest.mark.asyncio
    async def test_on_complete_publishes_completed(self):
        cb = RabbitMQEventCallback("amqp://guest:guest@localhost/", "gen-456")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            await cb.on_complete(_make_event("completed", 8, 8))

        import json
        body = json.loads(mock_exchange.publish.call_args.args[0].body.decode())
        assert body["step"] == "completed"
        assert body["generation_id"] == "gen-456"

    @pytest.mark.asyncio
    async def test_on_error_publishes_failed(self):
        cb = RabbitMQEventCallback("amqp://guest:guest@localhost/", "gen-789")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            await cb.on_error(RuntimeError("oops"))

        import json
        body = json.loads(mock_exchange.publish.call_args.args[0].body.decode())
        assert body["step"] == "failed"
        assert body["progress"]["error"] == "oops"

    @pytest.mark.asyncio
    async def test_reuses_connection(self):
        cb = RabbitMQEventCallback("amqp://guest:guest@localhost/", "gen-abc")

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("aio_pika.connect_robust", return_value=mock_connection) as mock_connect:
            await cb.on_stage(_make_event("floor", 1, 8))
            await cb.on_stage(_make_event("walls", 2, 8))

        mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        cb = RabbitMQEventCallback("amqp://guest:guest@localhost/", "gen-xyz")
        mock_connection = AsyncMock()
        cb._connection = mock_connection

        await cb.close()

        mock_connection.close.assert_awaited_once()
