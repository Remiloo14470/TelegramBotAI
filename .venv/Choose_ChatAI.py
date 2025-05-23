import asyncio
import logging
import sqlite3
import json
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from openai import AsyncOpenAI


bot_token = ""
openai_api_key = ""
deepseek_api_key = ""
deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
proxy_url = ""

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


def clear_database():
    conn = sqlite3.connect("chat_context.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user_contexts")
    conn.commit()
    conn.close()

# clear_database()
# print("База данных очищена!")

init_db()

# Получение контекста пользователя
def get_user_context(user_id):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT context FROM user_contexts WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    try:
        return json.loads(result[0]) if result and result[0] else []
    except (TypeError, json.JSONDecodeError):
        return []

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
    [InlineKeyboardButton(text='DeepSeek', callback_data='deepseek')]
])

# Обработчики
@router.message(lambda message: message.text == "/start")
async def start_handler(message:types.Message):
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
        await call.message.answer("Выбрана модель OpenAI GPT. Ты можешь начать общение. Чтобы вернуться к выбору "
                                  "модели набери команду /start")

    elif action == 'deepseek':
        context = get_user_context(user_id)
        save_user_context(user_id, username, context, "deepseek")
        cont = get_user_context(user_id)
        print(cont)
        await call.message.answer("Выбрана модель DeepSeek. Ты можешь начать общение. Чтобы вернуться к выбору "
                                  "модели набери команду /start")


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
        logging.info(f"Отправляем запрос в OpenAI для {user_id}")

        async with aiohttp.ClientSession() as session:
            try:
                response = await session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4",
                        "messages": context,
                        "temperature": 0.65
                    },
                    proxy=proxy_url
                )

                if response.status == 200:
                    result = await response.json()
                    reply = result["choices"][0]["message"]["content"]
                    context.append({"role": "assistant", "content": reply})
                    save_user_context(user_id, username, context, model)
                    logging.info(f"Контекст сохранен для {user_id}: {context}")
                    await message.answer(reply)
                else:
                    error_text = await response.text()
                    logging.error(f"Ошибка OpenAI {response.status}: {error_text}")
                    await message.answer(f"Ошибка OpenAI {response.status}: {error_text}")

            except Exception as e:
                logging.error(f"Ошибка при обращении к OpenAI: {e}")
                await message.answer(f"Ошибка при обращении к OpenAI: {e}")

    elif model == "deepseek":
        logging.info(f"Отправляем сообщение в DeepSeek для {user_id}")
        logging.info(f"Текущий контекст перед отправкой: {context}")

        system_prompt = {
            "role": "system",
            "content": "Ты — DeepSeek Chat, созданный китайской компанией DeepSeek. Не называй себя ChatGPT или OpenAI."
        }
        if model == "deepseek" and not any(msg.get("role") == "system" for msg in context):
            context.insert(0, system_prompt)
        context = [system_prompt] + context

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        deepseek_api_url,
                        headers={
                            "Authorization": f"Bearer {deepseek_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": context,
                            "temperature": 1.3
                        },
                        proxy=proxy_url
                ) as response:
                    result = await response.json()
                    logging.info(f"Ответ от DeepSeek API: {result}")
                    if "choices" in result:
                        reply = result["choices"][0]["message"]["content"]
                        context.append({"role": "assistant", "content": reply})
                        logging.info(f"Обновленный контекст после ответа: {context}")
                        save_user_context(user_id, username, context, model)
                        logging.info(f"Контекст сохранен для {user_id}: {context}")
                        await message.answer(reply)
                    else:
                        logging.error(f"Ошибка в ответе API: {result}")
                        await message.answer(f"Ошибка в ответе API: {result}")
        except Exception as e:
            logging.error(f"Ошибка DeepSeek: {e}")
            await message.answer(f"Ошибка DeepSeek: {e}")


async def main():
    dp.include_router(router)
    logging.info("Бот запущен и слушает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
