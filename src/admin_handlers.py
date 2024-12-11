from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from src.states import AddFlower, EditFlower
from src.keyboards import admin_keyboard, start_keyboard
from create_aiogram import bot
from config import ADMIN_ID

admin_router = Router(name=__name__)


@admin_router.callback_query(F.data == "add_flower")
async def add_flower(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите названия цветка:")
    await state.set_state(AddFlower.name)


@admin_router.message(AddFlower.name)
async def add_flower_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену цветка:")
    await state.set_state(AddFlower.price)


@admin_router.message(AddFlower.price)
async def add_flower_price(message: Message, state: FSMContext, pool):
    await state.update_data(price=message.text)
    data = await state.get_data()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO flowers (name,price) VALUES ($1, $2)",
                data['name'],
                data['price']
            )
            await message.answer("Цветок успешно добавлен!", reply_markup=await admin_keyboard())
        except Exception as e:
            print(e)
            await  message.answer("К сожалению произошла ошибка! Попробуйте еще раз!",
                                  reply_markup=await admin_keyboard())
    await state.clear()


@admin_router.callback_query(F.data == "delete_flower")
async def delete_flower_callback(callback: CallbackQuery, pool):
    async with pool.acquire() as conn:
        try:
            flowers = await conn.fetch("SELECT * FROM flowers")
            if not flowers:
                await callback.message.answer("Каталог пуст!", reply_markup=await admin_keyboard())
            else:
                kb = [
                    [InlineKeyboardButton(text=flower['name'], callback_data=f"delete_flower_{flower['id']}")]
                    for flower in flowers
                ]
                keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
                await callback.message.answer("Выберите цветок для удаления:", reply_markup=keyboard)
        except Exception as e:
            print(e)
            await callback.message.answer("Произошла ошибка...")


@admin_router.callback_query(F.data.startswith("delete_flower_"))
async def delete_flower_confirm(callback: CallbackQuery, pool):
    flower_id = int(callback.data.split("_")[2])
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM flowers WHERE id = $1", flower_id)
            await callback.message.answer("Цветок успешно удален!", reply_markup=await admin_keyboard())
        except Exception as e:
            print(e)
            await callback.message.answer("Произошла ошибка...", reply_markup=await admin_keyboard())


@admin_router.callback_query(F.data == "edit_flower")
async def select_flower_to_edit(callback: CallbackQuery, state: FSMContext, pool):
    async with pool.acquire() as conn:
        # Получаем список цветов
        flowers = await conn.fetch("SELECT id, name FROM flowers")
        if not flowers:
            await callback.message.answer("Каталог пуст. Добавьте цветы сначала.")
            return

        # Создаем инлайн-кнопки для выбора цветка
        buttons = [
            [InlineKeyboardButton(text=flower['name'], callback_data=f"edit_flower_{flower['id']}")]
            for flower in flowers
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.answer("Выберите цветок для редактирования:", reply_markup=keyboard)
        await state.set_state(EditFlower.select_flower)


@admin_router.callback_query(F.data.startswith("edit_flower_"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    flower_id = int(callback.data.split("_")[2])
    await state.update_data(flower_id=flower_id)

    # Создаем инлайн-кнопки для выбора поля
    buttons = [
        [InlineKeyboardButton(text="Редактировать название", callback_data="edit_name")],
        [InlineKeyboardButton(text="Редактировать цену", callback_data="edit_price")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.answer("Выберите поле для редактирования:", reply_markup=keyboard)
    await state.set_state(EditFlower.select_field)


@admin_router.callback_query(F.data.in_({"edit_name", "edit_price"}))
async def ask_new_value(callback: CallbackQuery, state: FSMContext):
    field = "name" if callback.data == "edit_name" else "price"
    await state.update_data(field=field)

    await callback.message.answer(f"Введите новое значение для поля '{field}':")
    await state.set_state(EditFlower.update_value)


@admin_router.message(EditFlower.update_value)
async def update_flower_value(message: Message, state: FSMContext, pool):
    data = await state.get_data()
    flower_id = data['flower_id']
    field = data['field']
    new_value = message.text

    # Проверка корректности ввода
    if field == "price":
        try:
            new_value = float(new_value)
        except ValueError:
            await message.answer("Цена должна быть числом. Попробуйте снова.")
            return

    async with pool.acquire() as conn:
        try:
            # Обновляем значение в базе данных
            await conn.execute(
                f"UPDATE flowers SET {field} = $1 WHERE id = $2",
                new_value,
                flower_id
            )
            await message.answer(f"Поле '{field}' успешно обновлено!", reply_markup=await admin_keyboard())
        except Exception as e:
            print(f"Ошибка при обновлении цветка: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=await admin_keyboard())

    await state.clear()
