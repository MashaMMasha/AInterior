import aio_pika
import json
from typing import Dict, Any, Optional
import asyncio
from render_service.config import RABBITMQ_URL


class RabbitMQService:
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        
    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            'generation_events',
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
    async def publish_progress(self, generation_id: str, step: str, progress: Dict[str, Any]):
        if not self.channel:
            await self.connect()
            
        message = aio_pika.Message(
            body=json.dumps({
                'generation_id': generation_id,
                'step': step,
                'progress': progress
            }).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await self.exchange.publish(
            message,
            routing_key=f'generation.{generation_id}'
        )
        
    async def close(self):
        if self.connection:
            await self.connection.close()


_rabbitmq_service: Optional[RabbitMQService] = None


def get_rabbitmq_service() -> RabbitMQService:
    global _rabbitmq_service
    if _rabbitmq_service is None:
        _rabbitmq_service = RabbitMQService()
    return _rabbitmq_service
