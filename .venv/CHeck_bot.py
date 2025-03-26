import asyncio
import logging
import sqlite3
import json
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from openai import AsyncOpenAI


bot_token = "7892230681:AAGMIcg2zicj7_rTQ71wAcu_fFHNhwNA2_Y"
openai_api_key = "YOUR_OPENAI_KEY"
deepseek_api_key = "sk-7411fff5b44043f7943e24907e6ae599"
deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
proxy_url = "http://oMbozo:hpbBrC@154.30.135.149:8000"

bot = Bot(token=bot_token)
dp = Dispatcher()
router = Router()
logging.basicConfig(level=logging.INFO)

client = AsyncOpenAI(api_key=openai_api_key)

# Подключение к базе данных
def db_connect():
    return sqlite3.connect("chat_context.db")

def init_db():
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_contexts (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        context TEXT,
                        model TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Получение контекста пользователя
def get_user_context(user_id):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT context FROM user_contexts WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result and result[0] else []

# Получение модели пользователя
def get_user_model(user_id):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT model FROM user_contexts WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Сохранение контекста пользователя
def save_user_context(user_id, username, context, model=None):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_contexts (user_id, username, context, model) VALUES (?, ?, ?, ?)",
                   (user_id, username, json.dumps(context), model if model else ""))
    conn.commit()
    conn.close()

# Кнопки
kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='OpenAI GPT', callback_data='openai')],
    [InlineKeyboardButton(text='GPT-4 (DeepSeek)', callback_data='deepseek')]
])

# Обработчики
@router.message()
async def start_handler(message: types.Message):
    if message.text.lower() == "/start":
        user_id = message.from_user.id
        username = message.from_user.username
        await message.answer(f"Привет, {username}! Выбери модель:", reply_markup=kb)


@router.callback_query()
async def handle_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username
    action = call.data

    logging.info(f"Пользователь {user_id} выбрал модель: {action}")

    if action == 'openai':
        save_user_context(user_id, username, [], "openai")
        await call.message.answer("Выбрана модель OpenAI GPT. Можешь начать общение.")

    elif action == 'deepseek':
        save_user_context(user_id, username, [], "deepseek")
        await call.message.answer("Выбрана модель GPT-4 от DeepSeek. Можешь начать общение.")


@router.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text.strip()

    logging.info(f"Получено сообщение от {user_id}: {text}")

    if not text:
        return

    model = get_user_model(user_id)

    if not model:
        await message.answer("Вы не выбрали модель. Используйте команду /start, чтобы выбрать.")
        return

    context = get_user_context(user_id)
    if not isinstance(context, list):
        context = []

    context.append({"role": "user", "content": text})

    if model == "openai":
        logging.info(f"Отправляем сообщение в OpenAI для {user_id}")
        try:
            response = await client.chat.completions.create(
                model='gpt-4',
                messages=context,
                temperature=0.65
            )
            reply = response.choices[0].message.content
            context.append({"role": "assistant", "content": reply})
            save_user_context(user_id, username, context, model)
            await message.answer(reply)
        except Exception as e:
            logging.error(f"Ошибка OpenAI: {e}")
            await message.answer(f"Ошибка OpenAI: {e}")

    elif model == "deepseek":
        logging.info(f"Отправляем сообщение в DeepSeek для {user_id}")
        headers = {
            "Authorization": f"Bearer {deepseek_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": context,
            "temperature": 0.7
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(deepseek_api_url, headers=headers, json=data, proxy=proxy_url) as response:
                    result = await response.json()
                    if "choices" in result:
                        reply = result["choices"][0]["message"]["content"]
                        context.append({"role": "assistant", "content": reply})
                        save_user_context(user_id, username, context, model)
                        await message.answer(reply)
                    else:
                        logging.error(f"Ошибка в ответе API: {result}")
                        await message.answer(f"Ошибка в ответе API: {result}")
        except Exception as e:
            logging.error(f"Ошибка DeepSeek: {e}")
            await message.answer(f"Ошибка DeepSeek: {e}")

# Запуск бота
async def main():
    dp.include_router(router)  # Подключаем обработчики
    logging.info("Бот запущен и слушает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
