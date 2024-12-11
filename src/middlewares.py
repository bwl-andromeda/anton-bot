import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import asyncpg


class RegisterMiddleware(BaseMiddleware):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,  # Добавляем поддержку CallbackQuery
            data: Dict[str, Any],
    ) -> Any:
        try:
            data['pool'] = self.pool
            if isinstance(event, Message):
                async with self.pool.acquire() as conn:
                    tg_id = event.from_user.id
                    user_name = event.from_user.username
                    user = await conn.fetchrow(
                        "SELECT * FROM users WHERE user_id = $1", tg_id
                    )
                    if not user:
                        await conn.execute(
                            "INSERT INTO users (user_id, user_name) VALUES ($1, $2)",
                            tg_id,
                            user_name,
                        )

            return await handler(event, data)
        except Exception as e:
            logging.error(f"Error in RegisterMiddleware: {e}")
            return await handler(event, data)
