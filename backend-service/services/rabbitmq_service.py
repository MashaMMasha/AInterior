import aio_pika
import json
from typing import Optional
import asyncio
from backend_service.config import RABBITMQ_URL


class RabbitMQService:
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        
    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        
    async def subscribe_to_generation(self, generation_id: str, callback):
        if not self.channel:
            await self.connect()
            
        exchange = await self.channel.declare_exchange(
            'generation_events',
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        queue = await self.channel.declare_queue(
            f'generation_{generation_id}',
            exclusive=True,
            auto_delete=True
        )
        
        await queue.bind(exchange, routing_key=f'generation.{generation_id}')
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body.decode())
                    await callback(data)
                    
                    if data.get('step') in ['completed', 'failed']:
                        break
        
    async def close(self):
        if self.connection:
            await self.connection.close()


_rabbitmq_service: Optional[RabbitMQService] = None


def get_rabbitmq_service() -> RabbitMQService:
    global _rabbitmq_service
    if _rabbitmq_service is None:
        _rabbitmq_service = RabbitMQService()
    return _rabbitmq_service
