from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan
from obllomov.shared.log import logger
from obllomov.services.chat import ChatService


class StageEvent(BaseModel):
    stage: str
    completed: int
    total: int
    scene_plan: ScenePlan
    raw_scene_plan: RawScenePlan


class EventCallback(ABC):
    @abstractmethod
    def on_stage(self, event: StageEvent) -> None: ...

    @abstractmethod
    def on_complete(self, event: StageEvent) -> None: ...

    @abstractmethod
    def on_error(self, error: Exception) -> None: ...


class AsyncEventCallback(ABC):
    @abstractmethod
    async def on_stage(self, event: StageEvent) -> None: ...

    @abstractmethod
    async def on_complete(self, event: StageEvent) -> None: ...

    @abstractmethod
    async def on_error(self, error: Exception) -> None: ...


class LogEventCallback(EventCallback):
    def on_stage(self, event: StageEvent) -> None:
        logger.info(f"[{event.completed}/{event.total}] Stage completed: {event.stage}")

    def on_complete(self, event: StageEvent) -> None:
        logger.info(f"Generation completed at stage: {event.stage}")

    def on_error(self, error: Exception) -> None:
        logger.error(f"Generation failed: {error}")


class ChatEventCallback(EventCallback):
    def __init__(self, chat: ChatService, interaction_id: int):
        self._chat = chat
        self._interaction_id = interaction_id

    def on_stage(self, event: StageEvent) -> None:
        self._chat.save_stage(
            self._interaction_id,
            event.stage,
            event.scene_plan,
            event.raw_scene_plan,
        )

    def on_complete(self, event: StageEvent) -> None:
        self._chat.save_stage(
            self._interaction_id,
            "completed",
            event.scene_plan,
            event.raw_scene_plan,
        )

    def on_error(self, error: Exception) -> None:
        logger.error(f"Generation failed during chat interaction {self._interaction_id}: {error}")


class RabbitMQEventCallback(AsyncEventCallback):
    def __init__(self, rabbitmq_url: str, generation_id: str):
        self._url = rabbitmq_url
        self._generation_id = generation_id
        self._connection = None
        self._channel = None
        self._exchange = None

    async def _ensure_connected(self):
        if self._channel:
            return
        import aio_pika
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            "generation_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    async def _publish(self, step: str, progress: Dict[str, Any]):
        import aio_pika
        import json
        await self._ensure_connected()
        message = aio_pika.Message(
            body=json.dumps({
                "generation_id": self._generation_id,
                "step": step,
                "progress": progress,
            }).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(
            message,
            routing_key=f"generation.{self._generation_id}",
        )

    async def on_stage(self, event: StageEvent) -> None:
        await self._publish(event.stage, {
            "completed": event.completed,
            "total": event.total,
            "scene_json": event.scene_plan.to_scene(),
        })

    async def on_complete(self, event: StageEvent) -> None:
        await self._publish("completed", {
            "scene_json": event.scene_plan.to_scene(),
        })

    async def on_error(self, error: Exception) -> None:
        await self._publish("failed", {"error": str(error)})

    async def close(self):
        if self._connection:
            await self._connection.close()


class CompositeEventCallback(EventCallback):
    def __init__(self, callbacks: List[EventCallback]):
        self._callbacks = callbacks

    def on_stage(self, event: StageEvent) -> None:
        for cb in self._callbacks:
            cb.on_stage(event)

    def on_complete(self, event: StageEvent) -> None:
        for cb in self._callbacks:
            cb.on_complete(event)

    def on_error(self, error: Exception) -> None:
        for cb in self._callbacks:
            cb.on_error(error)


class AsyncCompositeEventCallback(AsyncEventCallback):
    def __init__(self, callbacks: List[AsyncEventCallback]):
        self._callbacks = callbacks

    async def on_stage(self, event: StageEvent) -> None:
        for cb in self._callbacks:
            await cb.on_stage(event)

    async def on_complete(self, event: StageEvent) -> None:
        for cb in self._callbacks:
            await cb.on_complete(event)

    async def on_error(self, error: Exception) -> None:
        for cb in self._callbacks:
            await cb.on_error(error)
