from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from src.keyboards import start_keyboard, admin_keyboard
from src.states import SendAdminMessage, Payment, BuyFlower
from create_aiogram import bot
from config import ADMIN_ID

router = Router(name=__name__)


@router.message(CommandStart())
async def start_handler(message: Message):
    try:
        start_message_if_user_exist = f"Приветствую тебя {message.from_user.full_name}!\nХочешь что-то заказать?"
        await message.answer(start_message_if_user_exist, reply_markup=await start_keyboard())
    except Exception as e:
        print(e)
        await message.answer("Произошла ошибка...")


@router.message(Command('admin'))
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        admin_message = "Выберите действие:"
        await message.answer(admin_message, reply_markup=await admin_keyboard())
    else:
        await message.answer("У вас нет доступа к данному функционалу!", reply_markup=await start_keyboard())


@router.message(Command('pay'))
@router.message(F.text == "Пополнить баланс")
async def update_balance(message: Message, state: FSMContext):
    await message.answer("Введите сумму, на которую хотите пополнить свой баланс:")
    await state.set_state(Payment.amount)


@router.message(Payment.amount)
async def update_balance_amount(message: Message, state: FSMContext, pool):
    user_id = message.from_user.id
    amount = message.text

    # Проверка, что введено число
    if not amount.isdigit():
        await message.answer("Пожалуйста, введите корректное число.")
        return

    amount = int(amount)  # Преобразуем строку в число

    async with pool.acquire() as conn:
        try:
            # Обновляем баланс пользователя
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount,
                user_id
            )

            # Добавляем запись в таблицу transactions
            await conn.execute(
                "INSERT INTO transactions (user_id, amount, type) VALUES ($1, $2, 'deposit')",
                user_id,
                amount
            )

            await message.answer(f"Платеж на сумму {amount} рублей прошел успешно!",
                                 reply_markup=await start_keyboard())
            await state.clear()  # Очищаем состояние только после успешного выполнения

        except Exception as e:
            print(f"Ошибка при обновлении баланса: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=await start_keyboard())


@router.message(F.text == 'Профиль')
@router.message(Command('profile'))
async def profile_panel(message: Message, pool):
    user_id = message.from_user.id
    async with pool.acquire() as conn:
        try:
            # Получение информации о пользователе из базы данных
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await message.answer("Пользователь не найден в базе данных.", reply_markup=await start_keyboard())
            else:
                profile_text = "Ваш профиль:\n\n"
                profile_text += f"Имя пользователя: {user['user_name']}\n"
                profile_text += f"Баланс: {user['balance']} рублей\n"
                await message.answer(profile_text, reply_markup=await start_keyboard())
        except Exception as e:
            print(e)
            await message.answer("Произошла ошибка...", reply_markup=await start_keyboard())


@router.message(F.text == 'Каталог')
@router.message(Command('catalog'))
async def catalog_panel(message: Message, pool):
    async with pool.acquire() as conn:
        try:
            flowers = await conn.fetch("SELECT * FROM flowers")
            if not flowers:
                await message.answer("Каталог пуст. Попробуйте позже.", reply_markup=await start_keyboard())
            else:
                catalog_text = "Доступные цветы:\n\n"
                buttons = []
                for flower in flowers:
                    catalog_text += f"{flower['name']} - {flower['price']} рублей\n"
                    buttons.append(
                        [InlineKeyboardButton(text=f"Купить {flower['name']}",
                                              callback_data=f"buy_flower_{flower['id']}")]
                    )

                # Создание клавиатуры с кнопками для покупки
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer(catalog_text, reply_markup=keyboard)
        except Exception as e:
            print(e)
            await message.answer("Произошла ошибка...", reply_markup=await start_keyboard())


@router.callback_query(F.data.startswith("buy_flower_"))
async def buy_flower_callback(callback: CallbackQuery, state: FSMContext, pool):
    flower_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with pool.acquire() as conn:
        try:
            # Получаем информацию о цветке
            flower = await conn.fetchrow("SELECT * FROM flowers WHERE id = $1", flower_id)
            if not flower:
                await callback.message.answer("Цветок не найден!")
                return

            # Сохраняем информацию о цветке в состояние
            await state.update_data(flower_id=flower_id, flower_price=flower['price'])

            await callback.message.answer(f"Вы выбрали цветок '{flower['name']}'.\n"
                                          f"Введите количество цветков, которое хотите купить:")
            await state.set_state(BuyFlower.select_quantity)

        except Exception as e:
            print(f"Ошибка при выборе цветка: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=await start_keyboard())


@router.message(BuyFlower.select_quantity)
async def select_quantity_handler(message: Message, state: FSMContext, pool):
    user_id = message.from_user.id
    quantity = message.text

    # Проверяем, что введено число
    if not quantity.isdigit():
        await message.answer("Пожалуйста, введите корректное число.")
        return

    quantity = int(quantity)
    if quantity <= 0:
        await message.answer("Количество должно быть больше 0.")
        return

    # Получаем данные о цветке из состояния
    data = await state.get_data()
    flower_id = data['flower_id']
    flower_price = data['flower_price']
    total_price = flower_price * quantity

    async with pool.acquire() as conn:
        try:
            # Получаем информацию о пользователе
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await message.answer("Пользователь не найден!")
                return

            # Проверяем баланс пользователя
            if user['balance'] < total_price:
                await message.answer("Недостаточно средств на балансе!")
                return

            # Создаем заказ
            await conn.execute(
                "INSERT INTO orders (user_id, flower_id, quantity, total_price, status) VALUES ($1, $2, $3, $4, $5)",
                user_id,
                flower_id,
                quantity,
                total_price,
                'pending'  # Статус "ожидает подтверждения"
            )

            order_id = await conn.fetchval("SELECT id FROM orders WHERE user_id = $1 ORDER BY id DESC LIMIT 1", user_id)

            # Обновляем баланс пользователя
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                total_price,
                user_id
            )

            # Добавляем запись в таблицу transactions
            await conn.execute(
                "INSERT INTO transactions (user_id, amount, type) VALUES ($1, $2, 'withdrawal')",
                user_id,
                total_price
            )

            # Уведомляем пользователя
            await message.answer(f"Ваш заказ на {quantity} цветков успешно создан!\n"
                                 f"С вами свяжется администратор для подтверждения заказа.")

            # Уведомляем администратора
            flower = await conn.fetchrow("SELECT * FROM flowers WHERE id = $1", flower_id)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Готово", callback_data=f"complete_order_{order_id}")]
                ]
            )
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Поступил новый заказ:\n"
                     f"Пользователь: {user['user_name']} (ID: {user_id})\n"
                     f"Цветок: {flower['name']}\n"
                     f"Количество: {quantity}\n"
                     f"Общая стоимость: {total_price} рублей\n"
                     f"Статус: pending",
                reply_markup=keyboard
            )

            await state.clear()

        except Exception as e:
            print(f"Ошибка при создании заказа: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=await start_keyboard())


@router.callback_query(F.data.startswith("complete_order_"))
async def complete_order_callback(callback: CallbackQuery, pool):
    order_id = int(callback.data.split("_")[2])

    async with pool.acquire() as conn:
        try:
            # Обновляем статус заказа
            await conn.execute("UPDATE orders SET status = 'completed' WHERE id = $1", order_id)

            # Уведомляем администратора
            await callback.message.edit_text(
                "Заказ успешно завершен!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
            )

        except Exception as e:
            print(f"Ошибка при завершении заказа: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(F.text == "Мои заказы")
@router.message(Command('orders'))
async def orders(message: Message, pool):
    user_id = message.from_user.id

    async with pool.acquire() as conn:
        try:
            # Получаем заказы пользователя
            orders = await conn.fetch("SELECT * FROM orders WHERE user_id = $1", user_id)
            if not orders:
                await message.answer("У вас пока нет заказов.", reply_markup=await start_keyboard())
                return

            # Формируем сообщение с заказами
            orders_text = "Ваши заказы:\n\n"
            for order in orders:
                flower = await conn.fetchrow("SELECT * FROM flowers WHERE id = $1", order['flower_id'])
                if not flower:
                    flower_name = "Цветок не найден"
                else:
                    flower_name = flower['name']

                orders_text += f"Заказ №{order['id']}:\n"
                orders_text += f"Цветок: {flower_name}\n"
                orders_text += f"Количество: {order['quantity']}\n"
                orders_text += f"Общая стоимость: {order['total_price']} рублей\n"
                orders_text += f"Статус: {order['status']}\n\n"

            await message.answer(orders_text, reply_markup=await start_keyboard())

        except Exception as e:
            print(f"Ошибка при получении заказов: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(Command('feedback'))
@router.message(F.text == "Отзыв")
async def review(message: Message, state: FSMContext):
    await message.answer("Напишите свой отзыв и он отправиться администратору!")
    await state.set_state(SendAdminMessage.admin_message)


@router.message(SendAdminMessage.admin_message)
async def send_message(message: Message, state: FSMContext):
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Отзыв от {message.from_user.full_name}(Имя пользователя: {message.from_user.username}): {message.text}"
    )
    await message.answer("Сообщение успешно отправлено администратору!", reply_markup=await start_keyboard())
    await state.clear()


@router.message(Command('help'))
@router.message(F.text == "Связаться")
async def help_function(message: Message):
    help_message = "Если у вас возникли проблемы с ботом, или с заказом напишите сюда: @platonn02"
    await message.answer(help_message, reply_markup=await start_keyboard())
