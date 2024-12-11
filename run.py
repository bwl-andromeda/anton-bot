import asyncio
import asyncpg
from aiogram.types import BotCommand, BotCommandScopeDefault
from create_aiogram import bot, dp
from config import ADMIN_ID, DB_CONFIG
from src.handlers import router
from src.admin_handlers import admin_router
from src.middlewares import RegisterMiddleware
from src.db import init_database


# Функция, которая настроит командное меню (дефолтное для всех пользователей)
async def set_commands():
    commands = [BotCommand(command='start', description='Старт'),
                BotCommand(command='admin', description='Админ-панель'),
                BotCommand(command='catalog', description="Каталог"),
                BotCommand(command='feedback', description="Отзыв"),
                BotCommand(command='help', description="Связаться"),
                BotCommand(command='pay', description="Пополнить баланс"),
                BotCommand(command='orders', description="Мои заказы")]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


# Функция, которая выполнится когда бот запустится
async def start_bot():
    await set_commands()
    try:
        await bot.send_message(ADMIN_ID, f'Я запущен🥳.')
    except:
        pass


# Функция, которая выполнится когда бот завершит свою работу
async def stop_bot(pool):
    try:
        await bot.send_message(ADMIN_ID, 'Бот остановлен. За что?😔')
    except:
        pass
    finally:
        await pool.close()
        print('Пул закрыт')


async def main():
    await init_database()
    # Инициализация пула соединений
    pool = await asyncpg.create_pool(**DB_CONFIG)
    # Регистрация middleware
    dp.message.middleware(RegisterMiddleware(pool))
    dp.callback_query.middleware(RegisterMiddleware(pool))

    # Регистрация функций
    dp.startup.register(start_bot)
    dp.shutdown.register(lambda: stop_bot(pool))

    dp.include_router(admin_router)
    dp.include_router(router)

    # Запуск бота в режиме long polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
