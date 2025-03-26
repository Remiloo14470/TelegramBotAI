import asyncio
import logging
import sqlite3
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from openai import AsyncOpenAI


bot_token = ""
openai_api_key = ""
deepseek_api_key = ""
deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
proxy_url = "http://oMbozo:hpbBrC@154.30.135.149:8000"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=bot_token)
dp = Dispatcher()

client = AsyncOpenAI(api_key=openai_api_key)

# Подключение к базе данных
def db_connect():
    conn = sqlite3.connect("chat_context.db")
    return conn

# Инициализация базы данных
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
    if not result or not result[0]:
        return []

    try:
        return json.loads(result[0])  # Преобразуем строку JSON в список
    except json.JSONDecodeError:
        return []

# Сохранение контекста пользователя
def save_user_context(user_id, username, context, model=None):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_contexts (user_id, username, context, model) VALUES (?, ?, ?, ?)",
                   (user_id, username, json.dumps(context), model if model else ""))
    conn.commit()
    conn.close()

    #Создание кнопок выбора
kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='OpenAI GPT', callback_data='openai')],
    [InlineKeyboardButton(text='GPT-4 (DeepSeek)', callback_data='deepseek')]
])


@dp.message()
async def start_handler(message: types.Message):
    if message.text.lower()=="/start":
        user_id = message.from_user.id
        username = message.from_user.username
        save_user_context(user_id, username, [], None)
        await message.answer("Привет! Я GPT-бот. Выбери, с какой моделью ты хочешь общаться:",
        reply_markup=kb)


@dp.callback_query()
async def handle_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username
    action = call.data

    if action == 'openai':
        save_user_context(user_id, username, [], "openai")
        await call.message.answer("Выбрана модель OpenAI GPT. Можешь писать сообщение.")


    elif action == 'deepseek':
        save_user_context(user_id, username, [], "deepseek")
        await call.message.answer("Выбрана модель GPT-4 от DeepSeek. Можешь писать сообщение.")


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text.strip()

    if not text:
        return

    context = get_user_context(user_id)
    if not isinstance(context, list):
        context = []

    context.append({"role": "user", "content": text})

    model = get_user_context(user_id)
    if model == "deepseek":
        model_type = "deepseek-chat"
    else:
        model_type = "gpt-4"

    try:
        if model_type == "deepseek-chat":
            headers = {
                "Authorization": "Bearer ",
                "Content-Type": "application/json"
            }

            data = {
                "model": "deepseek-chat",
                "messages": context,
                "temperature": 0.7
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(deepseek_api_url, headers=headers, json=data, proxy=proxy_url) as response:
                    result = await response.json()
                    if "choices" in result:
                        reply = result["choices"][0]["message"]["content"]
                        context.append({"role": "assistant", "content": reply})
                        save_user_context(user_id, username, context)
                        await message.answer(reply)
                    else:
                        await message.answer(f"Ошибка в ответе API: {result}")
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=context,
                temperature=0.65
            )
            reply = response.choices[0].message.content
            context.append({"role": "assistant", "content": reply})
            save_user_context(user_id, username, context)
            await message.answer(reply)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")


async def main():
    dp.message.register(start_handler)
    dp.callback_query.register(handle_callback)
    dp.message.register(handle_message)

    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())