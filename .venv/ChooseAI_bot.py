from aiogram import Bot, Dispatcher, executore, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI
import asyncio
import time 


api = ''
bot = Bot(token=api)
dp = Dispatcher(bot, storage=MemoryStorage())


kb = InlineKeyboardMarkup(resize_keyboard=True).add(
    InlineKeyboardButton(text='openai', callback_data='openai'),
    InlineKeyboardButton(text='ChatGPT', callback_data='chatgpt')
)


@dp.message_handler(commands=['start'])
async def start_message(message):
    await message.answer('Привет! Выбери с кем ты желаешь пообщаться сегодня?', reply_markup=kb)

@dp.callback_query_handler(text='openai')
async def openai_response(user_message):
    system_promt='''
        Ты 
    '''
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[
            {"role":"system", "content": system_promt},
            {"role":"user", "content": user_message}
        ],
        temperature=0.65
    )
    return response['choices'][0]['message']['content']