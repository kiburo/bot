"""
Упрощенный бот БаЦзы
Работает только с mingli.ru и извлекает элемент личности из колонки "ДЕНЬ", верхняя клеточка
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import register_handlers
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    """Основная функция бота"""
    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем обработчики
    register_handlers(dp)
    
    # Запускаем бота
    print("🤖 Упрощенный бот БаЦзы запущен!")
    print("📊 Работает только с mingli.ru")
    print("🎯 Извлекает элемент личности из колонки 'ДЕНЬ', верхняя клеточка")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())