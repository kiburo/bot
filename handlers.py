"""
Упрощенные обработчики для бота БаЦзы
Только необходимые команды согласно ТЗ
"""
from aiogram import Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, Video
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import json
from typing import Dict

from database import Database
from simple_bazi_calculator import SimpleBaziCalculator
from notion_integration import NotionIntegration
from formulations_manager import FormulationsManager
from config import NOTION_TOKEN, NOTION_DATABASE_ID

# Инициализация базы данных и калькулятора
db = Database()
bazi_calc = SimpleBaziCalculator()
notion_client = NotionIntegration(NOTION_TOKEN, NOTION_DATABASE_ID)
formulations = FormulationsManager()

# Состояния для FSM
class UserStates(StatesGroup):
    waiting_for_choice = State()
    waiting_for_contact_name = State()
    waiting_for_contact_email = State()
    waiting_for_contact_phone = State()
    waiting_for_birth_date = State()
    waiting_for_birth_time = State()
    waiting_for_birth_city = State()

def register_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков"""
    
    @dp.message(Command("start"))
    async def start_handler(message: Message, state: FSMContext):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        
        # Сохраняем пользователя в базе данных
        db.save_user(user_id, username=message.from_user.username, first_name=message.from_user.first_name)
        
        welcome_text = formulations.get_formulation('greeting', 'start')
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да, хочу", callback_data="yes_want")]
        ])
        
        await message.answer(welcome_text, reply_markup=keyboard)
        await state.set_state(UserStates.waiting_for_choice)
    
    @dp.callback_query(lambda c: c.data == "yes_want")
    async def yes_want_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Да, хочу'"""
        await callback_query.answer()
        
        explanation_text = formulations.get_formulation('greeting', 'yes_want')
        
        await callback_query.message.answer(explanation_text, parse_mode='Markdown')
        
        # Запрашиваем имя
        name_text = formulations.get_formulation('data_collection', 'name')
        await callback_query.message.answer(name_text)
        await state.set_state(UserStates.waiting_for_contact_name)
    
    @dp.message(UserStates.waiting_for_contact_name)
    async def process_contact_name(message: Message, state: FSMContext):
        """Обработка имени пользователя"""
        contact_name = message.text.strip()
        
        # Сохраняем имя в сессии
        await state.update_data(contact_name=contact_name)
        
        # Запрашиваем email
        email_text = formulations.get_formulation('data_collection', 'email', name=contact_name)
        await message.answer(email_text)
        await state.set_state(UserStates.waiting_for_contact_email)
    
    @dp.message(UserStates.waiting_for_contact_email)
    async def process_contact_email(message: Message, state: FSMContext):
        """Обработка email пользователя"""
        contact_email = message.text.strip()
        
        # Простая валидация email
        if "@" not in contact_email or "." not in contact_email:
            await message.answer("❌ Пожалуйста, введите корректный email адрес:")
            return
        
        # Сохраняем email в сессии
        await state.update_data(contact_email=contact_email)
        
        # Запрашиваем телефон
        phone_text = formulations.get_formulation('data_collection', 'phone')
        await message.answer(phone_text)
        await state.set_state(UserStates.waiting_for_contact_phone)
    
    @dp.message(UserStates.waiting_for_contact_phone)
    async def process_contact_phone(message: Message, state: FSMContext):
        """Обработка телефона пользователя"""
        contact_phone = message.text.strip()
        
        # Сохраняем телефон в сессии
        await state.update_data(contact_phone=contact_phone)
        
        # Получаем все данные из сессии
        data = await state.get_data()
        
        # Сохраняем контактную информацию в базу данных
        user_id = message.from_user.id
        db.save_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            contact_name=data.get('contact_name'),
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone')
        )
        
        # Переходим к запросу даты рождения
        date_text = formulations.get_formulation('data_collection', 'birth_date', name=data.get('contact_name'))
        await message.answer(date_text)
        await state.set_state(UserStates.waiting_for_birth_date)
    
    @dp.message(UserStates.waiting_for_birth_date)
    async def process_birth_date(message: Message, state: FSMContext):
        """Обработка даты рождения"""
        birth_date = message.text.strip()
        
        # Простая валидация даты
        if not _validate_date(birth_date):
            await message.answer(
                "❌ Неверный формат даты. Введите дату в формате дд.мм.гггг (например: 15.03.1990):"
            )
            return
        
        await state.update_data(birth_date=birth_date)
        
        # Спрашиваем время рождения с кнопками
        time_text = formulations.get_formulation('data_collection', 'birth_time')
        
        keyboard_time = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Час рождения известен", callback_data="time_known")],
            [InlineKeyboardButton(text="🔘 Не знаю", callback_data="time_unknown")]
        ])
        
        await message.answer(time_text, reply_markup=keyboard_time)
        await state.set_state(UserStates.waiting_for_birth_time)
    
    @dp.callback_query(lambda c: c.data == "time_known")
    async def time_known_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Час рождения известен'"""
        await callback_query.answer()
        
        time_text = "🕐 Введите время рождения в формате чч:мм (например: 14:30):"
        
        await callback_query.message.answer(time_text)
        await state.set_state(UserStates.waiting_for_birth_time)
    
    @dp.callback_query(lambda c: c.data == "time_unknown")
    async def time_unknown_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Не знаю'"""
        await callback_query.answer()
        
        # Устанавливаем время по умолчанию
        await state.update_data(birth_time="12:00")
        
        # Спрашиваем город рождения
        city_text = "🏙️ Введите город рождения:"
        
        await callback_query.message.answer(city_text)
        await state.set_state(UserStates.waiting_for_birth_city)
    
    @dp.message(UserStates.waiting_for_birth_time)
    async def process_birth_time(message: Message, state: FSMContext):
        """Обработка времени рождения"""
        birth_time = message.text.strip()
        
        # Простая валидация времени
        if not _validate_time(birth_time):
            await message.answer(
                "❌ Неверный формат времени. Введите время в формате чч:мм (например: 14:30):"
            )
            return
        
        await state.update_data(birth_time=birth_time)
        
        # Спрашиваем город рождения
        city_text = formulations.get_formulation('data_collection', 'birth_city')
        
        await message.answer(city_text)
        await state.set_state(UserStates.waiting_for_birth_city)
    
    @dp.message(UserStates.waiting_for_birth_city)
    async def process_birth_city(message: Message, state: FSMContext):
        """Обработка города рождения и расчет БаЦзы"""
        birth_city = message.text.strip()
        
        if not birth_city:
            await message.answer("❌ Пожалуйста, введите город рождения:")
            return
        
        await state.update_data(birth_city=birth_city)
        
        # Получаем все данные
        data = await state.get_data()
        birth_date = data['birth_date']
        birth_time = data['birth_time']
        
        # Показываем сообщение о расчете
        await message.answer(formulations.get_formulation('calculation', 'processing'), parse_mode='Markdown')
        
        # Отправляем второе сообщение через 2 секунды
        await asyncio.sleep(2)
        
        calculation_text = formulations.get_formulation('calculation', 'description')
        
        await message.answer(calculation_text, parse_mode='Markdown')
        
        # Рассчитываем БаЦзы
        await _calculate_and_send_bazi(message, birth_date, birth_time, birth_city)
        
        await state.clear()
    
    @dp.message(Command("help"))
    async def help_handler(message: Message):
        """Обработчик команды /help"""
        help_text = (
            "🔮 *Помощь по боту БаЦзы*\n\n"
            "*Доступные команды:*\n"
            "• /start - Создать персональную карту БаЦзы\n"
            "• /menu - Главное меню бота\n"
            "• /consultation - Информация о консультациях\n"
            "• /strategy - Персональная стратегия по элементу личности\n"
            "• /help - Показать эту справку\n\n"
            "*Как создать карту:*\n"
            "1. Нажмите /start\n"
            "2. Выберите: 'Да, хочу' или 'Я знаю'\n"
            "3. Введите дату рождения (дд.мм.гггг)\n"
            "4. Укажите время или напишите 'не знаю'\n"
            "5. Введите город рождения\n"
            "6. Получите интерактивную карту!\n\n"
            "*Что вы узнаете:*\n"
            "• Элемент личности и полярность\n"
            "• Животное года рождения\n"
            "• Суперсилу и качества для карьеры\n"
            "• Совет на месяц\n"
            "• Прогноз на 2025 год"
        )
        
        await message.answer(help_text, parse_mode='Markdown')
    
    @dp.message(Command("menu"))
    async def menu_handler(message: Message):
        """Главное меню бота"""
        menu_text = (
            "🏠 *Главное меню*\n\n"
            "Выберите интересующий вас раздел:"
        )
        
        keyboard_menu = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Твои Прогнозы", callback_data="menu_forecasts")],
            [InlineKeyboardButton(text="📚 Интересное", callback_data="menu_interesting")],
            [InlineKeyboardButton(text="💬 Консультации", callback_data="menu_consultations")],
            [InlineKeyboardButton(text="📋 Программы", callback_data="menu_programs")],
            [InlineKeyboardButton(text="👤 Про меня", callback_data="menu_about")],
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu_question")],
            [InlineKeyboardButton(text="🔘 Создать карту БаЦзы", callback_data="start_new")],
            [InlineKeyboardButton(text="📤 Поделись ботом", callback_data="share_bot")]
        ])
        
        await message.answer(menu_text, reply_markup=keyboard_menu, parse_mode='Markdown')
    
    @dp.message(Command("consultation"))
    async def consultation_handler(message: Message):
        """Обработчик команды /consultation"""
        user_id = message.from_user.id
        
        # Получаем информацию о консультациях
        consultation_data = notion_client.get_consultation_info()
        consultation_message = notion_client.format_consultation_message(consultation_data)
        
        # Создаем кнопки для записи
        keyboard_book = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Записаться на консультацию", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="🔘 Узнать больше о БаЦзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔘 Создать карту БаЦзы", callback_data="start_new")]
        ])
        
        await message.answer(consultation_message, reply_markup=keyboard_book, parse_mode='Markdown')
    
    @dp.message(Command("strategy"))
    async def strategy_handler(message: Message):
        """Обработчик команды /strategy"""
        user_id = message.from_user.id
        
        # Получаем данные пользователя
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await message.answer(
                "❌ Сначала создайте карту БаЦзы с помощью команды /start, "
                "чтобы получить персональную стратегию."
            )
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            element = bazi_data['element']
            polarity = bazi_data['polarity']
            
            # Получаем стратегию для элемента
            strategy_message = formulations.format_strategy_message(element, polarity)
            
            # Создаем кнопки
            keyboard_strategy = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Узнать больше о БаЦзы", callback_data=f"learn_more_{user_id}")],
                [InlineKeyboardButton(text="🔘 Консультация", callback_data=f"consultation_options_{user_id}")],
                [InlineKeyboardButton(text="🔘 Создать новую карту", callback_data="start_new")]
            ])
            
            await message.answer(strategy_message, reply_markup=keyboard_strategy, parse_mode='Markdown')
            
        except Exception as e:
            await message.answer("❌ Ошибка при загрузке данных. Попробуйте создать карту заново.")
    
    @dp.message(Command("getfileid"))
    async def get_file_id_handler(message: Message):
        """Временный обработчик для получения file_id и message_id"""
        await message.answer(
            "📎 *Получение ID сообщений из канала*\n\n"
            "Перешлите сообщение из канала (текст, голосовое или фото), и я покажу:\n"
            "• Message ID (для пересылки)\n"
            "• File ID (для голосовых и фото)\n\n"
            "Это нужно для настройки бота на работу с сообщениями из канала.",
            parse_mode='Markdown'
        )
    
    @dp.message(lambda message: message.voice is not None)
    async def voice_file_id_handler(message: Message):
        """Обработчик голосовых сообщений для получения file_id и message_id"""
        if message.voice:
            file_id = message.voice.file_id
            message_id = message.message_id
            
            # Получаем информацию о пересланном сообщении
            forward_info = ""
            if message.forward_from_chat:
                forward_info = f"• Канал: {message.forward_from_chat.title}\n"
                forward_info += f"• ID канала: `{message.forward_from_chat.id}`\n"
            
            await message.answer(
                f"🎵 Голосовое сообщение получено!\n\n"
                f"📋 Информация:\n"
                f"• Message ID: {message_id}\n"
                f"• File ID: {file_id}\n"
                f"• Длительность: {message.voice.duration} сек\n"
                f"• Размер: {message.voice.file_size} байт\n\n"
                f"{forward_info}\n"
                f"💡 Как использовать:\n"
                f"Скопируйте file_id и замените в коде бота."
            )
            print(f"Voice file_id: {file_id}, message_id: {message_id}")  # Также выводим в консоль
    
    @dp.message(lambda message: message.photo is not None)
    async def photo_file_id_handler(message: Message):
        """Обработчик фотографий для получения file_id и message_id"""
        if message.photo:
            # Получаем самое большое фото (последний элемент в списке)
            photo = message.photo[-1]
            file_id = photo.file_id
            message_id = message.message_id
            
            # Получаем информацию о пересланном сообщении
            forward_info = ""
            if message.forward_from_chat:
                forward_info = f"• Канал: {message.forward_from_chat.title}\n"
                forward_info += f"• ID канала: `{message.forward_from_chat.id}`\n"
            
            await message.answer(
                f"📸 Фотография получена!\n\n"
                f"📋 Информация:\n"
                f"• Message ID: {message_id}\n"
                f"• File ID: {file_id}\n"
                f"• Размер: {photo.width}x{photo.height} пикселей\n"
                f"• Размер файла: {photo.file_size} байт\n\n"
                f"{forward_info}\n"
                f"💡 Как использовать:\n"
                f"Скопируйте file_id и замените в коде бота."
            )
            print(f"Photo file_id: {file_id}, message_id: {message_id}")  # Также выводим в консоль
    
    @dp.message(lambda message: message.video is not None)
    async def video_file_id_handler(message: Message):
        """Временный обработчик видео для получения file_id"""
        if message.video:
            video = message.video
            file_id = video.file_id
            file_unique_id = video.file_unique_id
            message_id = message.message_id
            
            # Получаем информацию о пересланном сообщении
            forward_info = ""
            if message.forward_from_chat:
                forward_info = f"• Канал: {message.forward_from_chat.title}\n"
                forward_info += f"• ID канала: `{message.forward_from_chat.id}`\n"
                forward_info += f"• Message ID в канале: `{message.forward_from_message_id}`\n"
            
            info_text = (
                f"📹 *Видео получено!*\n\n"
                f"📋 *Информация:*\n"
                f"• Message ID: `{message_id}`\n"
                f"• File ID: `{file_id}`\n"
                f"• File Unique ID: `{file_unique_id}`\n"
                f"• Длительность: {video.duration} сек\n"
                f"• Размер: {video.width}x{video.height} пикселей\n"
                f"• Размер файла: {video.file_size} байт\n\n"
            )
            
            if forward_info:
                info_text += f"📂 *Информация о пересылке:*\n{forward_info}\n"
            
            info_text += (
                f"💡 *Как использовать:*\n"
                f"Скопируйте `file_id` и используйте в коде бота для отправки видео через `bot.send_video()`"
            )
            
            await message.answer(info_text, parse_mode='Markdown')
            print(f"Video file_id: {file_id}")
            print(f"Video file_unique_id: {file_unique_id}")
            print(f"Message ID: {message_id}")
            if message.forward_from_chat:
                print(f"Forwarded from chat: {message.forward_from_chat.id}, message_id: {message.forward_from_message_id}")
    
    @dp.message(lambda message: message.text and not message.text.startswith('/'))
    async def text_message_id_handler(message: Message):
        """Обработчик текстовых сообщений для получения message_id"""
        # Проверяем, что это пересланное сообщение из канала
        if message.forward_from_chat and message.forward_from_chat.id == -1002554754176:
            message_id = message.message_id
            
            # Получаем информацию о пересланном сообщении
            forward_info = f"• Канал: {message.forward_from_chat.title}\n"
            forward_info += f"• ID канала: `{message.forward_from_chat.id}`\n"
            
            await message.answer(
                f"📝 Текстовое сообщение из канала получено!\n\n"
                f"📋 Информация:\n"
                f"• Message ID: {message_id}\n"
                f"• Текст: {message.text[:100]}{'...' if len(message.text) > 100 else ''}\n\n"
                f"{forward_info}\n"
                f"💡 Как использовать:\n"
                f"Скопируйте message_id и замените в коде бота."
            )
            print(f"Text message_id: {message_id}")  # Также выводим в консоль
    
    # Интерактивные обработчики для пошагового показа БаЦзы
    @dp.callback_query(lambda c: c.data.startswith("personality_desc_"))
    async def show_personality_description(callback_query, state: FSMContext):
        """Показать описание элемента личности"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            personality = bazi_data['personality']
            
            element_text = (
                f"🌟 *Ваш элемент личности:*\n\n"
                f"{personality['description']}\n\n"
                f"{formulations.get_formulation('results', 'superpower_question')}"
            )
            
            keyboard_element = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да, расскажите!", callback_data=f"show_superpower_{user_id}")],
                [InlineKeyboardButton(text="🔘 Сразу подсказку на месяц", callback_data=f"show_advice_{user_id}")],
            ])
            
            # Отправляем фото для типа личности
            personality_photos = {
                "Дерево_ян": "AgACAgIAAxkBAAICd2jOqHLJ5RvRNnXlkf7yMj5SDJ6mAAIa9zEbC2hwSmfIIQx_Gg_lAQADAgADeQADNgQ",
                "Дерево_инь": "AgACAgIAAxkBAAICf2jOqPKtdkPLwTsSCEPP1dbI8p4JAAIk9zEbC2hwSgZ7CVUq-bu_AQADAgADeQADNgQ",
                "Огонь_ян": "AgACAgIAAxkBAAICg2jOqR0lpPUNsRc9aZ1eRx5xD62HAAIU9zEbC2hwSjRlCpK45g7PAQADAgADeQADNgQ",
                "Огонь_инь": "AgACAgIAAxkBAAICh2jOqUVWgX8B7J1oqi-5wTJqN0TlAAId9zEbC2hwSrpstvM_lFILAQADAgADeQADNgQ",
                "Земля_ян": "AgACAgIAAxkBAAICi2jOqcPowNutDmTEszvqPLLnasbvAAIV9zEbC2hwSuSEMH7hkO9zAQADAgADeQADNgQ",
                "Земля_инь": "AgACAgIAAxkBAAICj2jOqe6718D5tDap5sa9YNBADv9jAAIZ9zEbC2hwSpm8J_CeRpcVAQADAgADeQADNgQ",
                "Металл_ян": "AgACAgIAAxkBAAICk2jOqjk0G_GkpaOWOO7mAbf_MG1pAAIb9zEbC2hwSnWxIFI1iKZkAQADAgADeQADNgQ",
                "Металл_инь": "AgACAgIAAxkBAAICmGjOqlfxlfIEPbBzIZx1QI9cQ7PSAAIX9zEbC2hwSlA1WZiuwiFmAQADAgADeQADNgQ",
                "Вода_ян": "AgACAgIAAxkBAAICnGjOqoe190sNelZ-U2WHFZRX4ogjAAIW9zEbC2hwSkq2YYVkoAeqAQADAgADeQADNgQ",
                "Вода_инь": "AgACAgIAAxkBAAICoGjOqp_B8YBmN-SsMyBoYzAkP58JAAIc9zEbC2hwShWVj1YYRq1tAQADAgADeQADNgQ"
            }
            
            # Формируем ключ для поиска фото
            element_key = f"{bazi_data['element']}_{bazi_data['polarity'].lower()}"
            
            # Отправляем фото с текстом как caption
            photo_id = personality_photos.get(element_key)
            if photo_id:
                try:
                    await callback_query.message.answer_photo(
                        photo=photo_id,
                        caption=element_text,
                        reply_markup=keyboard_element,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"Ошибка при отправке фото: {e}")
                    # Fallback - отправляем текст отдельно
                    await callback_query.message.answer(
                        element_text,
                        reply_markup=keyboard_element,
                        parse_mode='Markdown'
                    )
            else:
                print(f"Фото для {element_key} не найдено")
                # Fallback - отправляем текст отдельно
                await callback_query.message.answer(element_text, reply_markup=keyboard_element, parse_mode='Markdown')
            
        except Exception as e:
            await callback_query.message.answer("❌ Ошибка при загрузке данных.")
    
    @dp.callback_query(lambda c: c.data.startswith("show_superpower_"))
    async def show_superpower(callback_query, state: FSMContext):
        """Показать суперсилы личности"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            personality = bazi_data['personality']
            
            superpower_text = (
                f"✨ *Ваша суперсила:*\n\n"
                f"{personality['superpower']}"
            )
            
            await callback_query.message.answer(superpower_text, parse_mode='Markdown')
            
            # Отдельным сообщением вопрос о знаменитостях
            celebrities_question = formulations.get_formulation('results', 'celebrities_question')
            
            keyboard_celebrities = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да!", callback_data=f"celebrities_yes_{user_id}")],
                [InlineKeyboardButton(text="🔘 Ну их, давай дальше про меня", callback_data=f"celebrities_no_{user_id}")],
            ])
            
            await callback_query.message.answer(celebrities_question, reply_markup=keyboard_celebrities, parse_mode='Markdown')
            
        except Exception as e:
            await callback_query.message.answer("❌ Ошибка при загрузке данных.")
    
    @dp.callback_query(lambda c: c.data.startswith("show_traits_"))
    async def show_traits(callback_query, state: FSMContext):
        """Показать вопрос о совете на месяц"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            step3_text = "Хотите получить совет на месяц?"
            
            keyboard3 = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да, дайте совет!", callback_data=f"show_advice_{user_id}")],
            ])
            
            await callback_query.message.answer(step3_text, reply_markup=keyboard3, parse_mode='Markdown')
            
        except Exception as e:
            await callback_query.message.answer("❌ Ошибка при загрузке данных.")
    
    @dp.callback_query(lambda c: c.data.startswith("show_advice_"))
    async def show_advice(callback_query, state: FSMContext):
        """Показать совет на месяц"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            
            step4_text = f"{bazi_data['monthly_advice']}\n\n{formulations.get_formulation('results', 'year_question')}"
            
            keyboard4 = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да, покажите!", callback_data=f"show_2025_{user_id}")],
            ])
            
            await callback_query.message.answer(step4_text, reply_markup=keyboard4, parse_mode='Markdown')
            
        except Exception as e:
            await callback_query.message.answer("❌ Ошибка при загрузке данных.")
    
    @dp.callback_query(lambda c: c.data.startswith("show_2025_"))
    async def show_2025_summary(callback_query, state: FSMContext):
        """Показать резюме 2025 года"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            
            # Показываем только резюме 2025 года без кнопки и завершающего текста
            step5_text = f"{bazi_data['summary_2025']}"
            
            await callback_query.message.answer(step5_text, parse_mode='Markdown')
            
            # Через секунду отправляем дополнительное сообщение
            import asyncio
            await asyncio.sleep(8)
            
            additional_text = formulations.get_formulation('completion', 'additional_text')
            
            await callback_query.message.answer(additional_text, parse_mode='Markdown')
            await asyncio.sleep(5)
            # Следующим сообщением вопрос с кнопками
            question_text = formulations.get_formulation('results', 'energy_question')
            
            keyboard_question = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да, хочу узнать", callback_data=f"show_energy_{user_id}")],
                [InlineKeyboardButton(text="🔘 Может быть позже", callback_data=f"maybe_later_{user_id}")],
            ])
            
            await callback_query.message.answer(question_text, reply_markup=keyboard_question, parse_mode='Markdown')
            
        except Exception as e:
            await callback_query.message.answer("❌ Ошибка при загрузке данных.")
    
    @dp.callback_query(lambda c: c.data.startswith("show_energy_"))
    async def show_energy_info(callback_query, state: FSMContext):
        """Показать информацию об основных энергиях"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("❌ Данные не найдены. Попробуйте создать карту заново.")
            return
        
        try:
            bazi_data = eval(user_data['bazi_data'])
            
            energy_text = formulations.get_formulation('energy_section', 'main_energy')
            
            await callback_query.message.answer(energy_text, parse_mode='Markdown')
            
            # Отправляем голосовое сообщение из канала
            # Определяем file_id голосового сообщения по типу личности
            element = bazi_data['element']
            polarity = bazi_data['polarity']
            
            # File IDs для всех элементов (включая Металл - по 1 ГС)
            file_ids = {
                'Дерево_Ян': 'AwACAgIAAxkBAAIBSmjKyz2RZWI25IChKGGWgEIt2ujzAALHYwACXfIgSLk2e9DtcEw7NgQ',
                'Дерево_Инь': "AwACAgIAAxkBAAIBWGjK1ZFZf5ZFm0p7DVQ6QlLqXnweAALPYwACXfIgSEZZxIwa_tHENgQ",
                'Огонь_Ян': "AwACAgIAAxkBAAIBWmjK1fSagweyJcHm4CRJ8N3warY-AALXYwACXfIgSHASvr77PzMKNgQ",
                'Огонь_Инь': "AwACAgIAAxkBAAIBW2jK1fR-n1dYSzHVCiRzzC1hbxiMAALiYwACXfIgSNDsh6LNpDqONgQ",
                'Земля_Ян': "AwACAgIAAxkBAAIBXmjK2JUGdVyEt6hgwa1ecKLVFViYAALtYwACXfIgSPDDWyTUxx76NgQ",  
                'Земля_Инь': "AwACAgIAAxkBAAIBX2jK2JV_iTJUw8onVFwWQgp1CHUTAALnYwACXfIgSEVEoCxMhMiUNgQ",  
                'Металл_Ян': "AwACAgIAAxkBAAIBYmjK2MewquafQMDLYn91in4vJ1nsAAIDZAACXfIgSOY1-2hlJlFRNgQ",  # Один ГС для Металл Ян
                'Металл_Инь': "AwACAgIAAxkBAAIBZGjK2Mdsg9rZMSWRqSGUfzDexas0AAITZAACXfIgSNSNUeO1bLm3NgQ",  # Один ГС для Металл Инь
                'Вода_Ян': "AwACAgIAAxkBAAIBbmjK2czZUWajPXuxPOudJxDRRjzwAAIbZAACXfIgSGI7jo2Fg4g9NgQ",  # Замените на реальный
                'Вода_Инь': "AwACAgIAAxkBAAIBb2jK2czNMRzhxG5CQZTLNtylvid1AAIhZAACXfIgSB5snQdlplPONgQ",  # Замените на реальный
            }
            
            file_key = f"{element}_{polarity}"
            file_id = file_ids.get(file_key, "AwACAgIAAxkBAAIBSmjKyz2RZWI25IChKGGWgEIt2ujzAALHYwACXfIgSLk2e9DtcEw7NgQ")  # По умолчанию
            
            await callback_query.message.answer_voice(
                voice=file_id,
                caption=f"🎵 Голосовое сообщение для {element} {polarity}"
            )
            
            # Через 2 секунды отправляем дополнительное сообщение
            import asyncio
            await asyncio.sleep(2)
            
            additional_text = formulations.get_formulation('energy_section', 'promo_text')
            
            await callback_query.message.answer(additional_text, parse_mode='Markdown')
            
            # Следующим сообщением вопрос с кнопками
            question_text = formulations.get_formulation('energy_section', 'continue_question')
            
            keyboard_question = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔘 Да", callback_data=f"continue_after_voice_{user_id}")],
                [InlineKeyboardButton(text="🔘 Может быть позже", callback_data=f"maybe_later_{user_id}")],
            ])
            
            await callback_query.message.answer(question_text, reply_markup=keyboard_question, parse_mode='Markdown')
                
        except Exception as e:
            # Если не удалось отправить голосовое сообщение
            await callback_query.message.answer(
                f"🎵 Ошибка при отправке голосового сообщения: {str(e)}\n"
                f"Вы можете послушать его в нашем канале: https://t.me/+_pXXwzoRTs4zMjRi"
            )
    
    @dp.callback_query(lambda c: c.data.startswith("continue_after_voice_"))
    async def continue_after_voice_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Да' после голосового сообщения"""
        await callback_query.answer()
        
        # Получаем данные пользователя
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("Ошибка: данные БаЦзы не найдены. Начните заново с /start")
            return
        
        bazi_data = eval(user_data['bazi_data'])
        
        # Получаем годовую энергию
        year_element = bazi_data['element']
        year_polarity = bazi_data['polarity']
        
        # Определяем вторую годовую энергию (та же полярность)
        second_polarity = year_polarity
        
        continue_text = formulations.get_formulation('energy_section', 'second_energy')
        
        await callback_query.message.answer(continue_text, parse_mode='Markdown')
        
        # Отправляем голосовое сообщение для второй энергии
        # Пользователь добавит свои File ID
        file_ids = {
            "Дерево_Ян": "AwACAgIAAxkBAAIBb2jK2czNMRzhxG5CQZTLNtylvid1AAIhZAACXfIgSB5snQdlplPONgQ",
            "Дерево_Инь": "AwACAgIAAxkBAAIBbmjK2czZUWajPXuxPOudJxDRRjzwAAIbZAACXfIgSGI7jo2Fg4g9NgQ",
            "Огонь_Ян": "AwACAgIAAxkBAAIBWGjK1ZFZf5ZFm0p7DVQ6QlLqXnweAALPYwACXfIgSEZZxIwa_tHENgQ",
            "Огонь_Инь": "AwACAgIAAxkBAAIBSmjKyz2RZWI25IChKGGWgEIt2ujzAALHYwACXfIgSLk2e9DtcEw7NgQ",
            "Земля_Ян": "AwACAgIAAxkBAAIBW2jK1fR-n1dYSzHVCiRzzC1hbxiMAALiYwACXfIgSNDsh6LNpDqONgQ",
            "Земля_Инь": "AwACAgIAAxkBAAIBWmjK1fSagweyJcHm4CRJ8N3warY-AALXYwACXfIgSHASvr77PzMKNgQ",
            "Металл_Ян": "AwACAgIAAxkBAAIBXmjK2JUGdVyEt6hgwa1ecKLVFViYAALtYwACXfIgSPDDWyTUxx76NgQ",
            "Металл_Инь": "AwACAgIAAxkBAAIBX2jK2JV_iTJUw8onVFwWQgp1CHUTAALnYwACXfIgSEVEoCxMhMiUNgQ",
            "Вода_Ян": "AwACAgIAAxkBAAIBZGjK2Mdsg9rZMSWRqSGUfzDexas0AAITZAACXfIgSNSNUeO1bLm3NgQ",
            "Вода_Инь": "AwACAgIAAxkBAAIBYmjK2MewquafQMDLYn91in4vJ1nsAAIDZAACXfIgSOY1-2hlJlFRNgQ"
        }
        
        file_key = f"{year_element}_{second_polarity}"
        file_id = file_ids.get(file_key, "AwACAgIAAxkBAAIBSmjKyz2RZWI25IChKGGWgEIt2ujzAALHYwACXfIgSLk2e9DtcEw7NgQ")
        
        await callback_query.message.answer_voice(
            voice=file_id,
            caption=f"🎵 Голосовое сообщение для {year_element} {second_polarity}"
        )
        
        # Для Воды отправляем дополнительное голосовое сообщение
        if year_element == "Вода":
            # Получаем второй file_id для Воды
            water_second_file_ids = {
                "Вода_Ян": "AwACAgIAAxkBAAIBY2jK2MeJdSRa0YLUG5YI1TKE7MvaAAINZAACXfIgSHRNrjzrDPpcNgQ",  # Замените на второй file_id для Воды Ян
                "Вода_Инь": "AwACAgIAAxkBAAIBY2jK2MeJdSRa0YLUG5YI1TKE7MvaAAINZAACXfIgSHRNrjzrDPpcNgQ"  # Замените на второй file_id для Воды Инь
            }
            
            second_file_id = water_second_file_ids.get(file_key, file_id)
            
            await callback_query.message.answer_voice(
                voice=second_file_id,
                caption=f"🎵 Второе голосовое сообщение для {year_element} {second_polarity}"
            )
        
        # Промежуточное сообщение
        await asyncio.sleep(1)
        
        reminder_text = (
            "✨ *Помни: это только фрагменты прогноза.*\n\n"
            "Ты сейчас получаешь подсказки по элементу личности (твой личный «знак»).\n"
            "Но можно проанализировать ещё много факторов карты БаЦзы."
        )
        
        await callback_query.message.answer(reminder_text, parse_mode='Markdown')
        
        # Через секунду вопрос о впечатлениях
        await asyncio.sleep(1)
        
        impression_text = formulations.get_formulation('energy_section', 'impression_question')
        
        keyboard_impression = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да, круто", callback_data=f"impression_good_{user_id}")],
            [InlineKeyboardButton(text="🔘 Нет", callback_data=f"impression_bad_{user_id}")],
        ])
        
        await callback_query.message.answer(impression_text, reply_markup=keyboard_impression, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("impression_good_") or c.data.startswith("impression_bad_"))
    async def impression_response_handler(callback_query, state: FSMContext):
        """Обработчик кнопок 'Да, круто' и 'Нет'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Новый единый текст для обоих ответов
        response_text = (
            "Да, Элемент личности — это только вершина айсберга. Под ним скрыт целый мир энергий. "
            "Может посмотрим, что у тебя в глубине?\n\n"
            "Ведь мы - целый коктейль энергий 🍸!\n"
            "Ба-цзы — это как твой личный рецепт: интеллект, щепотка самовыражения, капля власти и горсть денег. 🧉 "
            "Хочешь увидеть свою уникальную пропорцию, заглянуть глубже в свою карту Ба-цзы?"
        )
        
        keyboard_response = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Хочу персональный разбор", callback_data=f"personal_analysis_{user_id}")],
            [InlineKeyboardButton(text="🔘 Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔘 Забронировать участие в Космический 2026 и получить Астропрогноз", url="https://www.yuliyaskiba.com/yourcosmos2026")]
        ])
        
        await callback_query.message.answer(response_text, reply_markup=keyboard_response, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("personal_analysis_"))
    async def personal_analysis_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Хочу персональный разбор'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        consultation_text = (
            "Даже если вы никогда не интересовались астрологией, натальными картами или Фэншуй, но хотите, "
            "чтобы Вам рассказали о Вас: «Вас настоящем» и «Вас будущем», а также получить подсказки по важным "
            "«открытым» жизненным вопросам, будь то отношения или работа, — такая консультация точно сможет помочь.\n\n"
            "БаЦзы знает о Вас больше, чем Вы сами и помогает понять, где ваши настоящие суперсилы и как включать их в нужный момент.\n"
            "Показывает короткие пути к целям и предупреждает о ямах на дороге.\n"
            "Исследует тайны Вашей удачи."
        )
        
        keyboard_consultation = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Варианты консультаций и стоимость", callback_data=f"consultation_types_{user_id}")],
            [InlineKeyboardButton(text="✅ Ба-цзы. Что это и для чего?", callback_data=f"consultation_what_{user_id}")],
            [InlineKeyboardButton(text="✅ Какие потребности закрывает", callback_data=f"consultation_needs_{user_id}")],
            [InlineKeyboardButton(text="✅ Чем может существенно помочь", callback_data=f"consultation_help_{user_id}")],
            [InlineKeyboardButton(text="✅ Для чего чаще всего используется", callback_data=f"consultation_usage_{user_id}")],
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")]
        ])
        
        await callback_query.message.answer(consultation_text, reply_markup=keyboard_consultation, parse_mode='Markdown')
    
    # Обработчики для детальной информации о консультациях
    @dp.callback_query(lambda c: c.data.startswith("consultation_types_"))
    async def consultation_types_handler(callback_query, state: FSMContext):
        """Варианты консультаций и стоимость"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        types_text = (
            "💰 *Варианты консультаций и стоимость*\n\n"
            "🔮 *Фундаментальная консультация Ба-цзы*\n\n"
            "Помогает познакомиться глубже с собой, понять свои способности, таланты и уникальность. "
            "Увидеть пространство возможностей в текущий жизненный период и выбрать эффективную персональную стратегию!\n\n"
            "• от 150 евро/7290 грн.\n\n"
            "📅 *Общая годовая консультация*\n\n"
            "Данная консультация - навигатор в персональных энергиях и тенденциях года. "
            "Вы определите личную годовую стратегию и проложите карту успеха 2026. "
            "Помогает сфокусироваться на наиболее потенциальных направлениях и не тратить силы на слабые зоны.\n\n"
            "• от 280 евро/13500 грн.\n\n"
            "✨ *Расширенная годовая консультация*\n\n"
            "Эта консультация — ваш Навигатор персональных энергий и тенденций года, а также отдельно каждого месяца. "
            "Позволяет распланировать, когда и что вы будете делать, чтобы у вас все складывалось более легко и эффективно, "
            "используя благоприятные энергии месяца для достижения своих годовых целей.\n\n"
            "• от 300 евро/14490 грн.\n\n"
            "🌟 *Годовое сопровождение*\n\n"
            "Это КОМПЛЕКСНОЕ АСТРОЛОГИЧЕСКОЕ СОПРОВОЖДЕНИЕ, аналитика потенциала Вашего времени и энергий на целый год. "
            "Включает в себя расширенную годовую консультацию в первый месяц после старта сопровождения, "
            "а также формат ежемесячных рекомендаций, календарей энергий, подборки важных дат и обсуждение обратной связи.\n\n"
            "• от 700 евро/33810 грн.\n\n"
            "📝 Забронируйте время консультации, указав правильный электронный адрес, чтобы мы могли с Вами связаться, "
            "или нажмите на кнопку *Задать вопрос* ниже, для уточнения любых деталей."
        )
        
        keyboard_types = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="❓ Задать вопрос", url="https://t.me/Yulia_Skiba")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(types_text, reply_markup=keyboard_types, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_what_"))
    async def consultation_what_handler(callback_query, state: FSMContext):
        """Ба-цзы. Что это и для чего?"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        what_text = (
            "🔮 *Ба-цзы. Что это и для чего?*\n\n"
            "БаЦзы (八字) — это древнекитайская система астрологии, которая анализирует личность и судьбу человека "
            "на основе даты и времени рождения.\n\n"
            "**Для чего используется:**\n"
            "• Понимание своей личности и характера\n"
            "• Определение сильных сторон и талантов\n"
            "• Прогнозирование жизненных периодов\n"
            "• Выбор оптимального времени для важных решений\n"
            "• Совместимость в отношениях\n"
            "• Карьерные рекомендации"
        )
        
        keyboard_what = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(what_text, reply_markup=keyboard_what, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_needs_"))
    async def consultation_needs_handler(callback_query, state: FSMContext):
        """Какие потребности закрывает"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        needs_text = (
            "🎯 *Какие потребности закрывает*\n\n"
            "**Личностные потребности:**\n"
            "• Понимание себя и своих мотивов\n"
            "• Принятие своих особенностей\n"
            "• Развитие сильных сторон\n"
            "• Работа с ограничениями\n\n"
            "**Жизненные потребности:**\n"
            "• Выбор правильного направления в жизни\n"
            "• Понимание жизненных циклов\n"
            "• Оптимизация времени и энергии\n"
            "• Принятие важных решений\n\n"
            "**Отношенческие потребности:**\n"
            "• Понимание совместимости с партнерами\n"
            "• Улучшение коммуникации\n"
            "• Решение конфликтов в семье"
        )
        
        keyboard_needs = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(needs_text, reply_markup=keyboard_needs, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_help_"))
    async def consultation_help_handler(callback_query, state: FSMContext):
        """Чем может существенно помочь"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        help_text = (
            "💪 *Чем может существенно помочь*\n\n"
            "**В карьере:**\n"
            "• Выбор подходящей профессии\n"
            "• Понимание своих талантов\n"
            "• Оптимальное время для смены работы\n"
            "• Развитие лидерских качеств\n\n"
            "**В отношениях:**\n"
            "• Понимание совместимости с партнерами\n"
            "• Улучшение семейных отношений\n"
            "• Решение конфликтов\n"
            "• Понимание потребностей близких\n\n"
            "**В здоровье:**\n"
            "• Понимание уязвимых систем организма\n"
            "• Выбор оптимального времени для лечения\n"
            "• Профилактика заболеваний\n"
            "• Управление стрессом"
        )
        
        keyboard_help = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(help_text, reply_markup=keyboard_help, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_usage_"))
    async def consultation_usage_handler(callback_query, state: FSMContext):
        """Для чего чаще всего используется"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        usage_text = (
            "📊 *Для чего чаще всего используется анализ БаЦзы*\n\n"
            "**Популярные случаи использования:**\n"
            "• Выбор времени для важных событий (свадьба, переезд, смена работы)\n"
            "• Понимание отношений с детьми и партнерами\n"
            "• Карьерное планирование и развитие\n"
            "• Решение семейных конфликтов\n"
            "• Понимание своих эмоциональных реакций\n"
            "• Выбор подходящего образования для детей\n"
            "• Планирование беременности и воспитания\n"
            "• Понимание жизненных кризисов и их преодоление"
        )
        
        keyboard_usage = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(usage_text, reply_markup=keyboard_usage, parse_mode='Markdown')
    
    # Обработчики для подробной информации о консультациях
    @dp.callback_query(lambda c: c.data.startswith("consultation_individual_details_"))
    async def consultation_individual_details_handler(callback_query, state: FSMContext):
        """Подробная информация об индивидуальной консультации"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        details_text = (
            "🔮 *Подробно об индивидуальной консультации*\n\n"
            "**Что включает консультация:**\n"
            "• Полный анализ всех 4 столпов БаЦзы (год, месяц, день, час)\n"
            "• Определение ваших сильных сторон и талантов\n"
            "• Анализ совместимости в отношениях\n"
            "• Рекомендации по карьере и финансам\n"
            "• Прогноз на ближайшие 2-3 года\n"
            "• Ответы на все ваши вопросы\n\n"
            "**Как проходит:**\n"
            "• Онлайн через Zoom или очно в офисе\n"
            "• Длительность: 60-90 минут\n"
            "• Запись консультации предоставляется\n"
            "• Письменный отчет в течение 3 дней\n\n"
            "**Результат:**\n"
            "• Понимание своих возможностей\n"
            "• План действий на ближайшие годы\n"
            "• Рекомендации по важным решениям"
        )
        
        keyboard_details = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Записаться на консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"consultation_individual_{user_id}")],
        ])
        
        await callback_query.message.answer(details_text, reply_markup=keyboard_details, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_cosmic_details_"))
    async def consultation_cosmic_details_handler(callback_query, state: FSMContext):
        """Подробная информация о программе Космический-2026"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        details_text = (
            "🚀 *Подробно о программе «Космический-2026»*\n\n"
            "**Что включает программа:**\n"
            "• Детальный прогноз на весь 2026 год\n"
            "• Благоприятные периоды для важных решений\n"
            "• Карьерные возможности и риски\n"
            "• Личные отношения и здоровье\n"
            "• Рекомендации по месяцам\n\n"
            "**Формат программы:**\n"
            "• 3 месяца интенсивной работы\n"
            "• Еженедельные групповые встречи\n"
            "• Персональные консультации\n"
            "• Доступ к закрытому чату\n"
            "• Материалы для самостоятельного изучения\n\n"
            "**Результат:**\n"
            "• Полное понимание своего года\n"
            "• План действий на каждый месяц\n"
            "• Поддержка сообщества единомышленников"
        )
        
        keyboard_details = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Записаться на программу", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"consultation_cosmic_{user_id}")],
        ])
        
        await callback_query.message.answer(details_text, reply_markup=keyboard_details, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_learn_details_"))
    async def consultation_learn_details_handler(callback_query, state: FSMContext):
        """Подробная информация об обучении анализу БаЦзы"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        details_text = (
            "📚 *Подробно об обучении анализу БаЦзы*\n\n"
            "**Что включает курс:**\n"
            "• Основы системы БаЦзы и 5 элементов\n"
            "• Как читать карты рождения\n"
            "• Анализ элементов и их взаимодействие\n"
            "• Практические упражнения с реальными кейсами\n"
            "• Разбор карт знаменитостей\n"
            "• Техники консультирования\n\n"
            "**Формат обучения:**\n"
            "• 6 недель онлайн-курса\n"
            "• Еженедельные видео-уроки\n"
            "• Практические задания\n"
            "• Обратная связь от преподавателя\n"
            "• Сертификат по окончании\n\n"
            "**Результат:**\n"
            "• Самостоятельный анализ карт БаЦзы\n"
            "• Возможность консультировать других\n"
            "• Глубокое понимание системы БаЦзы"
        )
        
        keyboard_details = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Записаться на обучение", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"consultation_learn_{user_id}")],
        ])
        
        await callback_query.message.answer(details_text, reply_markup=keyboard_details, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("detailed_analysis_"))
    async def detailed_analysis_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Хочу подробный разбор'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        analysis_text = formulations.get_formulation('analysis', 'full_analysis_offer')
        
        keyboard_full_analysis = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Хочу полный разбор", callback_data=f"full_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(analysis_text, reply_markup=keyboard_full_analysis, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("full_analysis_"))
    async def full_analysis_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Хочу полный разбор'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Получаем информацию о консультациях
        consultation_data = notion_client.get_consultation_info()
        consultation_message = notion_client.format_consultation_message(consultation_data)
        
        # Создаем кнопки для записи
        keyboard_book = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Записаться на консультацию", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="🔘 Узнать больше о БаЦзы", callback_data=f"learn_more_{user_id}")],
        ])
        
        await callback_query.message.answer(consultation_message, reply_markup=keyboard_book, parse_mode='Markdown')
        
    
    @dp.callback_query(lambda c: c.data.startswith("celebrities_yes_"))
    async def celebrities_yes_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Да!' для знаменитостей"""
        await callback_query.answer()
        
        # Получаем данные пользователя
        user_id = callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data.get('bazi_data'):
            await callback_query.message.answer("Ошибка: данные БаЦзы не найдены. Начните заново с /start")
            return
        
        bazi_data = eval(user_data['bazi_data'])
        
        # Получаем элемент личности
        day_stem_element = bazi_data['element']
        day_stem_polarity = bazi_data['polarity']
        
        # Отладочная информация
        print(f"Debug: element={day_stem_element}, polarity={day_stem_polarity}")
        
        # Словарь с примерами знаменитостей из таблицы
        celebrities_examples = {
            "Дерево_ян": "🌍 Примеры: Нельсон Мандела, Илон Маск, Тина Кароль, Катя Сильченко",
            "Дерево_инь": "🌍 Примеры: Джулия Робертс, Николь Кидман, Джек Ма, Монатик, Бред Питт, Валерий Залужный, Ярослава Гресь",
            "Огонь_ян": "🌍 Примеры: Опра Уинфри, Уилл Смит, Александр Усик, Лена Борисова",
            "Огонь_инь": "🌍 Примеры: Мэрил Стрип, Джон Леннон, Владимир Зеленский, Дмитрий Кулеба, Вера Брежнева, Дарья Квиткова",
            "Земля_ян": "🌍 Примеры: Уоррен Баффет, Хилари Клинтон, Лорен Санчес, Лена Перминова, Наталья Могилевская",
            "Земля_инь": "🌍 Примеры: Далай-лама XIV, Одри Хепбёрн, Барак Обама, Дональд Трамп, Богдан Ханенко, Кейт Миддлтон, Юлия Тимошенко, Анна Алхим",
            "Металл_ян": "🌍 Примеры: Стив Джобс, Брюс Ли, Наталья Гоций, Джефф Безос, Елизавета II",
            "Металл_инь": "🌍 Примеры: Принцесса Диана, Анжелина Джоли, Александр Маккуин, Диего Марадонна, Уинстон Черчилль, Мария Склодовская-Кюри, Мерилин Монро, Вуди Аллен, Сергей Притула",
            "Вода_ян": "🌍 Примеры: Авраам Линкольн, Рианна, Алена Гудкова, Маша Ефросинина",
            "Вода_инь": "🌍 Примеры: Махатма Ганди, Мать Тереза, Джонни Депп, Рокфеллер, Пикассо, Мерил Стрип, Анастасия Каменских, Ольга Сумская"
        }
        
        
        element_key = f"{day_stem_element}_{day_stem_polarity.lower()}"
        print(f"Debug: element_key={element_key}")
        celebrities_text = celebrities_examples.get(element_key, f"Примеры знаменитостей не найдены для {element_key}")
        
        # Отправляем картинку для типа личности
        personality_images = {
            "Дерево_ян": [
                "AgACAgIAAxkBAAIGOWkQYCGfH0Cr5hPBqQJhVgeRmXBtAAJNDGsb502ASH-qmJoaj8gAAQEAAwIAA3kAAzYE"
            ],
            "Дерево_инь": [
                "AgACAgIAAxkBAAIGP2kQYGSbk-R76cKZnerbChBQ01b_AAJXDGsb502ASHDkPbgXRlqlAQADAgADeQADNgQ"
            ],
            "Огонь_ян": [
                "AgACAgIAAxkBAAIGQ2kQYKPzZ6Q-eFVY24yCkWzGlODOAAKADGsb502ASNlF8DNAInvSAQADAgADeQADNgQ"
            ],
            "Огонь_инь": [
                "AgACAgIAAxkBAAIGO2kQYD_wPiS0-MeGi6prdlSX-d6NAAJODGsb502ASNwYEPNA7D4kAQADAgADeQADNgQ"
            ],
            "Земля_ян": [
                "AgACAgIAAxkBAAIGPWkQYFfTR8tpgwNw5hp-2TsjQCWBAAJPDGsb502ASOolXTFumOlRAQADAgADeQADNgQ"
            ],
            "Земля_инь": [
                "AgACAgIAAxkBAAIGQWkQYHh2cRDXAgF1fyAvOrTpeESKAAJvDGsb502ASHQkE-MqZ7faAQADAgADeQADNgQ"
            ],
            "Металл_ян": [
                "AgACAgIAAxkBAAIGRWkQYLSk5qMtYWyaSXlgc5dr1cZnAAKCDGsb502ASPbL1I-3ixFDAQADAgADeQADNgQ"
            ],
            "Металл_инь": [
                "AgACAgIAAxkBAAIGN2kQYAOXvuiCGXgXu-VkDNaRg9AgAAJMDGsb502ASBXojH8-Ub4TAQADAgADeQADNgQ"
            ],
            "Вода_ян": [
                "AgACAgIAAxkBAAICm2jOqofiJRFlLKavdipCt94d_OyNAAIg9zEbC2hwSnvaNs7RpEYKAQADAgADeQADNgQ"
            ],
            "Вода_инь": [
                "AgACAgIAAxkBAAICn2jOqp-XVt9yRNHwtZvRYjmlOGBwAAIh9zEbC2hwSmsB5s8mEK8SAQADAgADeQADNgQ"
            ]
        }
        
        images = personality_images.get(element_key, [])
        if images:
            try:
                # Отправляем картинку с примерами знаменитостей как caption
                await callback_query.message.answer_photo(
                    photo=images[0], 
                    caption=celebrities_text
                )
            except Exception as e:
                await callback_query.message.answer(f"Ошибка при отправке картинки: {str(e)}")
                # Fallback - отправляем текст отдельно
                await callback_query.message.answer(celebrities_text)
        else:
            await callback_query.message.answer("Картинка для вашего типа личности не найдена")
            # Fallback - отправляем текст отдельно
            await callback_query.message.answer(celebrities_text)
        
        # Отдельным сообщением вопрос о совете
        advice_question = "Хотите получить совет на месяц?"
        
        keyboard_advice = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да, дайте совет!", callback_data=f"show_advice_{user_id}")],
        ])
        
        await callback_query.message.answer(advice_question, reply_markup=keyboard_advice, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("celebrities_no_"))
    async def celebrities_no_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Ну их, давай дальше про меня'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        continue_text = "Понятно! Продолжаем с вашим анализом..."
        await callback_query.message.answer(continue_text, parse_mode='Markdown')
    
        # Сразу переходим к предложению совета на месяц, как и в ветке с показом примеров
        advice_question = "Хотите получить совет на месяц?"
        keyboard_advice = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да, дайте совет!", callback_data=f"show_advice_{user_id}")],
        ])
        await callback_query.message.answer(advice_question, reply_markup=keyboard_advice, parse_mode='Markdown')
    
    
    @dp.callback_query(lambda c: c.data.startswith("maybe_later_"))
    async def maybe_later_handler(callback_query, state: FSMContext):
        """Обработчик кнопки 'Может быть позже'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        later_text = formulations.get_formulation('completion', 'maybe_later')
        
        keyboard_later = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Что еще возможно?", callback_data=f"video_anna_{user_id}")],
        ])
        
        await callback_query.message.answer(later_text, reply_markup=keyboard_later, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "finish_")
    async def finish_interaction(callback_query, state: FSMContext):
        """Завершение взаимодействия"""
        await callback_query.answer()
        
        finish_text = formulations.get_formulation('completion', 'thank_you')
        
        await callback_query.message.answer(finish_text, parse_mode='Markdown')
    
    # Обработчики для консультаций
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_options_"))
    async def consultation_options_handler(callback_query, state: FSMContext):
        """Показать варианты консультаций"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Получаем информацию о консультациях
        consultation_data = notion_client.get_consultation_info()
        consultation_message = notion_client.format_consultation_message(consultation_data)
        
        # Создаем кнопки для записи
        keyboard_book = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Записаться на консультацию", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"detailed_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(consultation_message, reply_markup=keyboard_book, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("learn_more_"))
    async def learn_more_handler(callback_query, state: FSMContext):
        """Показать информацию о БаЦзы"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        learn_more_text = (
            "Хочешь, расскажу, на каком языке с тобой разговаривать, чтобы ты точно сказал \"Да\". "
            "Как в книге \"Пять языков любви\" у каждого свой язык чувств, так и в Ба-цзы у каждого элемента личности— "
            "свой язык общения. Хочешь узнать какой твой?"
        )
        
        keyboard_learn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да", callback_data=f"language_communication_{user_id}")],
            [InlineKeyboardButton(text="🔘 Может быть позже", callback_data=f"maybe_later_{user_id}")],
            [InlineKeyboardButton(text="🔘 Что еще возможно?", callback_data=f"video_anna_{user_id}")],
        ])
        
        await callback_query.message.answer(learn_more_text, reply_markup=keyboard_learn, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("language_communication_"))
    async def language_communication_handler(callback_query, state: FSMContext):
        """Показать язык общения для элемента личности пользователя"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Получаем данные пользователя из базы данных
        user_data = db.get_user(user_id)
        if not user_data or 'bazi_data' not in user_data or not user_data['bazi_data']:
            await callback_query.message.answer("Ошибка: данные пользователя не найдены. Пожалуйста, создайте карту БаЦзы заново.")
            return
        
        bazi_data = eval(user_data['bazi_data'])
        element = bazi_data['element']
        polarity = bazi_data['polarity']
        
        # Общее введение
        intro_text = (
            "Мы часто говорим: «Он меня не понимает» или «Мы словно на разных языках».\n"
            "В Ба-цзы есть простой ответ: мы действительно говорим на разных «языках энергии».\n\n"
            "Каждый элемент личности имеет свой тип восприятия окружающих и стиль коммуникации.\n"
            "Если подобрать «ключ» — общение становится лёгким, а результат предсказуемым.\n\n"
            "А значит отношения с близкими, любимыми, детьми и начальниками или подчиненными - ЛЕГЧЕ! "
            "Сейчас загружу твой язык общения."
        )
        
        await callback_query.message.answer(intro_text, parse_mode='Markdown')
        
        # Пауза для чтения
        await asyncio.sleep(3)
        
        # Определяем язык общения для конкретного элемента и полярности
        language_messages = {
            "Дерево_Ян": "🌳 **Дерево Ян** — «С тобой следует говорить открыто, прямо и честно — Ты \"топор\" видишь издалека».",
            "Дерево_Инь": "🌱 **Дерево Инь** — «Тебя нужно увлекать метафорой, романтикой и ты раскроешься и расцветешь».",
            "Огонь_Ян": "🔥 **Огонь Ян** — «Тебя нужно вдохновить, и ты \"включишь\" все вокруг. Однако договариваться с тобой нужно очень быстро, пока ты \"горишь\" идеей».",
            "Огонь_Инь": "🔥 **Огонь Инь** — «Комплимент + эмоция! = твоя формула согласия».",
            "Земля_Ян": "⛰ **Земля Ян** — «Факты, логика, спокойный тон, многочисленные доводы — ключ к доверию. Но без давления, повышения голоса и эмоциональности».",
            "Земля_Инь": "🏞 **Земля Инь** — «С тобой следует говорить Душевно, Тепло и по-человечески — и ты - союзник».",
            "Металл_Ян": "⚔️ **Металл Ян** — «С тобой следует говорить Чётко, коротко, фактами. Ты любишь без воды и сантиментов, которые тебя только раздражают».",
            "Металл_Инь": "💎 **Металл Инь** — «Ты слышишь, когда до тебя доносят информацию Структурно и красиво. Ты ценишь стиль слов и \"фигуры\" речи».",
            "Вода_Ян": "🌊 **Вода Ян** — «Лучший способ общения с тобой - Говорить о смыслах, глубоко, философски — и ты наполнишься идеями и мотивацией».",
            "Вода_Инь": "💧 **Вода Инь** — «Лучший способ общения с тобой - Легкая непринужденная беседа, где есть место чувствам, где есть Намёк и Загадка. Недосказанность, чувственность, возможность не ставить точку и не решать все сразу — твой любимый язык»."
        }
        
        element_key = f"{element}_{polarity}"
        language_message = language_messages.get(element_key, "Язык общения для вашего элемента не найден.")
        
        await callback_query.message.answer(language_message, parse_mode='Markdown')
        
        # Пауза для чтения языка общения
        await asyncio.sleep(2)
        
        # Предложение продолжить
        continue_text = (
            "«Теперь ты знаешь свой язык общения по Ба-цзы 🔮\n"
            "Хочешь пойти дальше?»"
        )
        
        keyboard_continue = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Разобрать подробно мои энергии — хочу консультацию с мастером", callback_data=f"personal_analysis_{user_id}")],
            # [InlineKeyboardButton(text="🔘 Научиться читать людей — хочу уметь понимать любого за 5 минут", url="https://your-landing-page.com")],  # Временно отключено - лендинг не готов
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"video_anna_{user_id}")],
            [InlineKeyboardButton(text="🔘 Поделиться Ботом — пусть друзья тоже узнают свой язык общения!", callback_data="share_bot")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"personal_analysis_{user_id}")],
        ])
        
        await callback_query.message.answer(continue_text, reply_markup=keyboard_continue, parse_mode='Markdown')
    
    # Обработчики для видео-цепочки
    # ВАЖНО: более специфичные обработчики должны быть ПЕРЕД общими
    @dp.callback_query(lambda c: c.data.startswith("video_anna_play_"))
    async def video_anna_play_handler(callback_query, state: FSMContext):
        """Отправка видео Анны Алхим"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # File ID видео Анны Алхим
        video_file_id = "BAACAgIAAxkBAAIE9GkHW69NKXFrH8P5GH4w5Sc3xR8cAALmSgACJUJoSUfk4ZxQGLAMNgQ"
        
        try:
            # Отправляем видео напрямую через file_id
            await callback_query.message.bot.send_video(
                chat_id=user_id,
                video=video_file_id,
                caption="📹 Видео разбор даты рождения Анны Алхим"
            )
            
            # Показываем кнопку продолжения
            keyboard_continue = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Зарегистрироваться в Космический 2026", url="https://www.yuliyaskiba.com/yourcosmos2026")],
                [InlineKeyboardButton(text="🔘 Что еще возможно?", callback_data=f"video_trump_{user_id}")],
            ])
            await callback_query.message.answer("Зарегистрироваться в Космический 2026!!!", reply_markup=keyboard_continue)
        except Exception as e:
            # Если не удалось отправить, отправляем ссылку
            error_msg = f"Ошибка при отправке видео: {str(e)}"
            print(error_msg)  # Для отладки
            
            await callback_query.message.answer(
                "📹 Видео: https://t.me/c/2554754176/30\n\n"
                "💡 Если видео не отображается, перейдите по ссылке."
            )
            
            # Предлагаем продолжить
            keyboard_continue = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Зарегистрироваться в Космический 2026", url="https://www.yuliyaskiba.com/yourcosmos2026")],
                [InlineKeyboardButton(text="🔘 Что еще возможно?", callback_data=f"video_trump_{user_id}")],
            ])
            await callback_query.message.answer("Зарегистрироваться в Космический 2026!!!", reply_markup=keyboard_continue)
    
    @dp.callback_query(lambda c: c.data.startswith("video_anna_"))
    async def video_anna_handler(callback_query, state: FSMContext):
        """Видео с разбором Анны Алхим"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        anna_text = (
            "Ба-цзы — это не только про характер человека и стиль общения. "
            "Ба-цзы отлично разбирается в Ваших чувствах и мотивах. "
            "Посмотрим короткое видео на примере даты рождения Анны Алхим, "
            "которую разбирала после когда-то нашумевшего подкаста?"
        )
        
        # Отправляем текст с кнопками
        keyboard_anna = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да", callback_data=f"video_anna_play_{user_id}")],
            [InlineKeyboardButton(text="🔘 Что еще возможно?", callback_data=f"video_trump_{user_id}")],
        ])
        
        await callback_query.message.answer(anna_text, reply_markup=keyboard_anna, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("video_trump_") and not c.data.startswith("video_trump_play_"))
    async def video_trump_handler(callback_query, state: FSMContext):
        """Видео с разбором Трампа и Харрис"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Первое сообщение без кнопок
        intro_text = (
            "Ба-цзы - целая карта возможностей:\n"
            "🔹 показывает, когда действовать, а когда лучше ждать,\n"
            "🔹 когда твой потенциал роста,\n"
            "🔹 и какие события могут проявиться в жизни."
        )
        
        await callback_query.message.answer(intro_text, parse_mode='Markdown')
        
        # Пауза 2 секунды
        await asyncio.sleep(2)
        
        # Второе сообщение с вопросом и кнопками
        question_text = (
            "Посмотрим, Что бы узнал Дональд Трамп или Камала Харрис, "
            "если пришли ко мне на консультацию перед выборами?"
        )
        
        keyboard_trump = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да", callback_data=f"video_trump_play_{user_id}")],
            [InlineKeyboardButton(text="🔘 Что еще можно?", callback_data=f"video_bezos_{user_id}")],
        ])
        
        await callback_query.message.answer(question_text, reply_markup=keyboard_trump, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("video_trump_play_"))
    async def video_trump_play_handler(callback_query, state: FSMContext):
        """Отправка видео Трампа/Харрис"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # File ID видео Трампа/Харрис
        video_file_id = "BAACAgIAAxkBAAIE9mkHXFe4AQOO2ZRcq_KXR2_NxWxWAALRhAACFWOwSvhAtcm2WGMRNgQ"
        
        try:
            # Отправляем видео напрямую через file_id
            await callback_query.message.bot.send_video(
                chat_id=user_id,
                video=video_file_id,
                caption="📹 Видео разбор: Что бы узнал Дональд Трамп или Камала Харрис перед выборами?"
            )
        except Exception as e:
            # Если не удалось отправить, отправляем ссылку
            error_msg = f"Ошибка при отправке видео: {str(e)}"
            print(error_msg)  # Для отладки

            await callback_query.message.answer(
                "📹 Видео: https://t.me/c/2554754176/31\n\n"
                "💡 Если видео не отображается, перейдите по ссылке."
            )
        
        # Финальные варианты после видео
        keyboard_final = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Зарегистрироваться в Космический 2026", url="https://www.yuliyaskiba.com/yourcosmos2026")],
            [InlineKeyboardButton(text="🔘 Разобрать подробно мои энергии — хочу консультацию с мастером", callback_data=f"personal_analysis_{user_id}")],
            # [InlineKeyboardButton(text="🔘 Научиться читать людей — хочу уметь понимать любого за 5 минут", url="https://your-landing-page.com")],  # Временно отключено - лендинг не готов
            [InlineKeyboardButton(text="🔘 Поделиться Ботом — пусть друзья тоже узнают информацию о себе!", callback_data="share_bot")],
            [InlineKeyboardButton(text="🔘 Посмотреть еще что-то", callback_data=f"video_bezos_{user_id}")],
        ])
        await callback_query.message.answer("Зарегистрироваться в Космический 2026!!!", reply_markup=keyboard_final)
    
    @dp.callback_query(lambda c: c.data.startswith("video_bezos_play_"))
    async def video_bezos_play_handler(callback_query, state: FSMContext):
        """Отправка фото Безоса"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # File ID фото Безоса
        photo_file_id = "AgACAgIAAxkBAAIE-GkHXSk2OKOy52hdJr4ukU4BprxyAAIN_TEbCiw4SETTg96ax59TAQADAgADeQADNgQ"
        
        try:
            # Отправляем фото
            await callback_query.message.bot.send_photo(
                chat_id=user_id,
                photo=photo_file_id,
                caption="📹 Что говорит Ба-цзы о миллиардах и свадьбе Джеффа Безоса?\n\nКак карта рождения может подсказать, когда наступает время для больших денег или личных перемен?"
            )
        except Exception as e:
            # Если не удалось отправить, отправляем ссылку
            error_msg = f"Ошибка при отправке фото: {str(e)}"
            print(error_msg)  # Для отладки
            
            await callback_query.message.answer(
                "📹 Медиа: https://t.me/c/2554754176/33\n\n"
                "💡 Если медиа не отображается, перейдите по ссылке."
            )
        
        # Варианты после медиа
        keyboard_continue = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Зарегистрироваться в Космический 2026", url="https://www.yuliyaskiba.com/yourcosmos2026")],
            [InlineKeyboardButton(text="🔘 Разобрать подробно мои энергии — хочу консультацию с мастером", callback_data=f"personal_analysis_{user_id}")],
            # [InlineKeyboardButton(text="🔘 Научиться читать людей — хочу уметь понимать любого за 5 минут", url="https://your-landing-page.com")],  # Временно отключено - лендинг не готов
            [InlineKeyboardButton(text="🔘 Поделиться Ботом — пусть друзья тоже узнают информацию о себе!", callback_data="share_bot")],
            [InlineKeyboardButton(text="🔘 Посмотреть еще что-то", callback_data=f"video_bazi_{user_id}")],
        ])
        await callback_query.message.answer("Зарегистрироваться в Космический 2026!!!", reply_markup=keyboard_continue)
    
    @dp.callback_query(lambda c: c.data.startswith("video_bezos_") and not c.data.startswith("video_bezos_play_"))
    async def video_bezos_handler(callback_query, state: FSMContext):
        """Видео с разбором Безоса"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        bezos_text = (
            "Что говорит Ба-цзы о миллиардах и свадьбе Джеффа Безоса?\n\n"
            "Как карта рождения может подсказать, когда наступает время для больших денег или личных перемен?"
        )
        
        keyboard_bezos = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да", callback_data=f"video_bezos_play_{user_id}")],
            [InlineKeyboardButton(text="🔘 Посмотреть еще что-то", callback_data=f"video_bazi_{user_id}")],
        ])
        
        await callback_query.message.answer(bezos_text, reply_markup=keyboard_bezos, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("video_bazi_"))
    async def video_bazi_handler(callback_query, state: FSMContext):
        """Видео о том, что такое Ба-цзы"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        bazi_text = (
            "Посмотри 3-х минутное видео о том, что такое Ба-цзы"
        )
        
        keyboard_bazi = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Посмотреть видео", url="https://youtube.com/watch?si=21z_vWircn-juc4N&v=C-372XhBoiw&feature=youtu.be")],
            [InlineKeyboardButton(text="🔘 Посмотреть еще что-то", callback_data=f"final_options_{user_id}")],
        ])
        
        await callback_query.message.answer(bazi_text, reply_markup=keyboard_bazi, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("final_options_"))
    async def final_options_handler(callback_query, state: FSMContext):
        """Финальные варианты после просмотра видео"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        # Финальные варианты
        keyboard_final = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Зарегистрироваться в Космический 2026", url="https://www.yuliyaskiba.com/yourcosmos2026")],
            [InlineKeyboardButton(text="🔘 Разобрать подробно мои энергии — хочу консультацию с мастером", callback_data=f"personal_analysis_{user_id}")],
            # [InlineKeyboardButton(text="🔘 Научиться читать людей — хочу уметь понимать любого за 5 минут", url="https://your-landing-page.com")],  # Временно отключено - лендинг не готов
            [InlineKeyboardButton(text="🔘 Поделиться Ботом — пусть друзья тоже узнают информацию о себе!", callback_data="share_bot")],
            [InlineKeyboardButton(text="🔘 Посмотреть еще что-то", callback_data="no_more_content")],
        ])
        
        await callback_query.message.answer("Зарегистрироваться в Космический 2026!!!", reply_markup=keyboard_final)
    
    @dp.callback_query(lambda c: c.data == "no_more_content")
    async def no_more_content_handler(callback_query, state: FSMContext):
        """Сообщение, когда больше нет контента для просмотра"""
        await callback_query.answer()
        await callback_query.message.answer(
            "Пока это всё, что есть! Но мы постоянно работаем над новым интересным контентом. "
            "Скоро здесь появится ещё больше увлекательной информации о Ба-цзы! Следите за обновлениями 😉"
        )
    
    
    
    # Обработчики главного меню
    @dp.callback_query(lambda c: c.data == "menu_forecasts")
    async def menu_forecasts_handler(callback_query, state: FSMContext):
        """Раздел 'Твои Прогнозы'"""
        await callback_query.answer()
        
        forecasts_text = (
            "🔮 *Твои Прогнозы*\n\n"
            "Здесь вы можете получить персональные прогнозы и рекомендации:\n\n"
            "• 📅 **Прогноз на год** — что ждет вас в 2025 году\n"
            "• 🌙 **Ежемесячные советы** — рекомендации на каждый месяц\n"
            "• ⭐ **Благоприятные периоды** — когда лучше принимать важные решения\n"
            "• 💼 **Карьерные возможности** — перспективы в работе\n"
            "• ❤️ **Личные отношения** — прогнозы в любви и дружбе\n\n"
            "Для получения прогнозов создайте свою карту БаЦзы!"
        )
        
        keyboard_forecasts = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Создать карту БаЦзы", callback_data="start_new")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(forecasts_text, reply_markup=keyboard_forecasts, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_interesting")
    async def menu_interesting_handler(callback_query, state: FSMContext):
        """Раздел 'Интересное'"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        interesting_text = (
            "📚 *Интересное*\n\n"
            "Узнайте больше о Ба-цзы и сохраните все полезное в одном месте:\n\n"
            "• 🔤 **Язык общения** — ваша персональная ветка с текстами и видео\n"
            "• 🎥 **Анна Алхим** — короткий видео-разбор\n"
            "• 🎥 **Трамп / Харрис** — видео перед выборами\n"
            "• 🖼 **Джефф Безос** — про миллиарды и свадьбу\n"
            "• ▶️ **Видео о Ба-цзы** — 3 минуты\n"
            "• 🌟 **Знаменитости** — другие примеры\n\n"
            "Также здесь собраны материалы из вкладок консультаций:\n"
            "• 🔮 **Ба-цзы: что это и для чего**\n"
            "• 🎯 **Какие потребности закрывает**\n"
            "• 💪 **Чем может существенно помочь**\n"
            "• 📊 **Для чего чаще всего используется**\n\n"
            "И быстродоступные ссылки:\n"
            "• 🚀 **Космический-2026** — регистрация\n"
            "• 💬 **Консультации: варианты и стоимость**\n"
            "• 📞 **Забронировать консультацию** или **Задать вопрос**"
        )
        
        keyboard_interesting = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔤 Язык общения", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🎥 Анна Алхим", callback_data=f"video_anna_{user_id}")],
            [InlineKeyboardButton(text="🎥 Трамп / Харрис", callback_data=f"video_trump_{user_id}")],
            [InlineKeyboardButton(text="🖼 Джефф Безос", callback_data=f"video_bezos_{user_id}")],
            [InlineKeyboardButton(text="▶️ Видео о Ба-цзы", callback_data=f"video_bazi_{user_id}")],
            [InlineKeyboardButton(text="🌟 Знаменитости — ещё примеры", callback_data="interesting_celebrities")],
            [InlineKeyboardButton(text="🔮 Ба-цзы: что это и для чего", callback_data=f"consultation_what_{user_id}")],
            [InlineKeyboardButton(text="🎯 Какие потребности закрывает", callback_data=f"consultation_needs_{user_id}")],
            [InlineKeyboardButton(text="💪 Чем может существенно помочь", callback_data=f"consultation_help_{user_id}")],
            [InlineKeyboardButton(text="📊 Для чего чаще всего используется", callback_data=f"consultation_usage_{user_id}")],
            [InlineKeyboardButton(text="🚀 Космический-2026 — регистрация", url="https://www.yuliyaskiba.com/yourcosmos2026")],
            [InlineKeyboardButton(text="💬 Консультации: варианты и стоимость", callback_data=f"consultation_types_{user_id}")],
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="❓ Задать вопрос", url="https://t.me/Yulia_Skiba")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(interesting_text, reply_markup=keyboard_interesting, parse_mode='Markdown')

    # Раздел «Интересное»: обработчики кнопок
    @dp.callback_query(lambda c: c.data == "interesting_videos")
    async def interesting_videos_handler(callback_query, state: FSMContext):
        """Переход к обучающим видео — запускаем цепочку с Анной Алхим"""
        await callback_query.answer()
        user_id = callback_query.from_user.id
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Смотреть пример: Анна Алхим", callback_data=f"video_anna_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_interesting")],
        ])
        await callback_query.message.answer(
            "Выберите видео:", reply_markup=keyboard
        )

    @dp.callback_query(lambda c: c.data == "interesting_articles")
    async def interesting_articles_handler(callback_query, state: FSMContext):
        """Статьи и кейсы — краткая заглушка с приглашением"""
        await callback_query.answer()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_interesting")],
        ])
        await callback_query.message.answer(
            "Скоро здесь будут разборы и кейсы. А пока можно посмотреть видео-примеры.",
            reply_markup=keyboard,
        )

    @dp.callback_query(lambda c: c.data == "interesting_celebrities")
    async def interesting_celebrities_handler(callback_query, state: FSMContext):
        """Выбор примеров знаменитостей — ведём в существующие сценарии видео"""
        await callback_query.answer()
        user_id = callback_query.from_user.id
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Анна Алхим", callback_data=f"video_anna_{user_id}")],
            [InlineKeyboardButton(text="Дональд Трамп / Камала Харрис", callback_data=f"video_trump_{user_id}")],
            [InlineKeyboardButton(text="Джефф Безос", callback_data=f"video_bezos_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_interesting")],
        ])
        await callback_query.message.answer(
            "Выберите пример знаменитости:", reply_markup=keyboard
        )

    @dp.callback_query(lambda c: c.data == "interesting_compatibility")
    async def interesting_compatibility_handler(callback_query, state: FSMContext):
        """Короткое описание про совместимость + CTA"""
        await callback_query.answer()
        user_id = callback_query.from_user.id
        text = (
            "Совместимость в Ба-цзы показывает, как энергии людей взаимодействуют — где легко, а где лучше прояснить ожидания.\n\n"
            "Хочешь, подскажу по твоим энергиям?"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Получить совет на месяц", callback_data=f"show_advice_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_interesting")],
        ])
        await callback_query.message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_consultations")
    async def menu_consultations_handler(callback_query, state: FSMContext):
        """Раздел 'Консультации' - сразу показывает варианты и стоимость"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        consultations_text = (
            "💰 *Варианты консультаций и стоимость*\n\n"
            "🔮 *Фундаментальная консультация Ба-цзы*\n\n"
            "Помогает познакомиться глубже с собой, понять свои способности, таланты и уникальность. "
            "Увидеть пространство возможностей в текущий жизненный период и выбрать эффективную персональную стратегию!\n\n"
            "• от 150 евро/7290 грн.\n\n"
            "📅 *Общая годовая консультация*\n\n"
            "Данная консультация - навигатор в персональных энергиях и тенденциях года. "
            "Вы определите личную годовую стратегию и проложите карту успеха 2026. "
            "Помогает сфокусироваться на наиболее потенциальных направлениях и не тратить силы на слабые зоны.\n\n"
            "• от 280 евро/13500 грн.\n\n"
            "✨ *Расширенная годовая консультация*\n\n"
            "Эта консультация — ваш Навигатор персональных энергий и тенденций года, а также отдельно каждого месяца. "
            "Позволяет распланировать, когда и что вы будете делать, чтобы у вас все складывалось более легко и эффективно, "
            "используя благоприятные энергии месяца для достижения своих годовых целей.\n\n"
            "• от 300 евро/14490 грн.\n\n"
            "🌟 *Годовое сопровождение*\n\n"
            "Это КОМПЛЕКСНОЕ АСТРОЛОГИЧЕСКОЕ СОПРОВОЖДЕНИЕ, аналитика потенциала Вашего времени и энергий на целый год. "
            "Включает в себя расширенную годовую консультацию в первый месяц после старта сопровождения, "
            "а также формат ежемесячных рекомендаций, календарей энергий, подборки важных дат и обсуждение обратной связи.\n\n"
            "• от 700 евро/33810 грн.\n\n"
            "📝 Забронируйте время консультации, указав правильный электронный адрес, чтобы мы могли с Вами связаться, "
            "или нажмите на кнопку *Задать вопрос* ниже, для уточнения любых деталей."
        )
        
        keyboard_consultations = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Забронировать консультацию", url="https://calendly.com/kiburo8899/meet-with-me")],
            [InlineKeyboardButton(text="❓ Задать вопрос", url="https://t.me/Yulia_Skiba")],
            [InlineKeyboardButton(text="✨ Узнать больше о Ба-цзы", callback_data=f"learn_more_{user_id}")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(consultations_text, reply_markup=keyboard_consultations, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_programs")
    async def menu_programs_handler(callback_query, state: FSMContext):
        """Раздел 'Программы' - регистрация в Космический-2026"""
        await callback_query.answer()
        
        programs_text = (
            "📋 *Программы*\n\n"
            "🚀 *Программа «Космический-2026»*\n\n"
            "Узнайте прогнозы на следующий год для себя и получите персональный астропрогноз.\n\n"
            "Зарегистрируйтесь прямо сейчас!"
        )
        
        keyboard_programs = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Зарегистрироваться в программе «Космический-2026»", url="https://www.yuliyaskiba.com/yourcosmos2026")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(programs_text, reply_markup=keyboard_programs, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_about")
    async def menu_about_handler(callback_query, state: FSMContext):
        """Раздел 'Про меня'"""
        await callback_query.answer()
        
        about_text = (
            "👤 *Про меня*\n\n"
            "**Юлия Скиба** — мастер БаЦзы и астролог\n\n"
            "• 🎓 **Образование:** Сертифицированный специалист по китайской астрологии\n"
            "• ⭐ **Опыт:** Более 10 лет практики\n"
            "• 👥 **Клиенты:** Помогла более 5000 человек\n"
            "• 🏆 **Достижения:** Автор уникальных методик анализа\n\n"
            "**Мой подход:**\n"
            "• Индивидуальный анализ каждой карты\n"
            "• Практические рекомендации для жизни\n"
            "• Простое объяснение сложных концепций\n"
            "• Поддержка на пути к целям\n\n"
            "**Связь со мной:**\n"
            "• 📱 Telegram: @твойник\n"
            "• 📧 Email: info@example.com\n"
            "• 🌐 Сайт: www.example.com"
        )
        
        keyboard_about = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Связаться", url="https://t.me/Yulia_Skiba")],
            [InlineKeyboardButton(text="🔘 Хочу консультацию", callback_data=f"consultation_options_{callback_query.from_user.id}")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(about_text, reply_markup=keyboard_about, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_question")
    async def menu_question_handler(callback_query, state: FSMContext):
        """Раздел 'Задать вопрос'"""
        await callback_query.answer()
        
        question_text = (
            "❓ *Задать вопрос*\n\n"
            "Есть вопросы о БаЦзы или нужна помощь? Я всегда готова ответить!\n\n"
            "**Частые вопросы:**\n"
            "• Как работает система БаЦзы?\n"
            "• Можно ли изменить судьбу?\n"
            "• Как выбрать лучшее время для важных дел?\n"
            "• Что делать, если не знаю точное время рождения?\n"
            "• Как БаЦзы может помочь в карьере?\n\n"
            "**Способы связи:**\n"
            "• 💬 Написать в Telegram\n"
            "• 📞 Позвонить для срочных вопросов\n"
            "• 📧 Отправить email с подробным описанием"
        )
        
        keyboard_question = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать в Telegram", url="https://t.me/Yulia_Skiba")],
            [InlineKeyboardButton(text="📞 Позвонить", callback_data="question_call")],
            [InlineKeyboardButton(text="📧 Email", callback_data="question_email")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(question_text, reply_markup=keyboard_question, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "menu_main")
    async def menu_main_handler(callback_query, state: FSMContext):
        """Возврат в главное меню"""
        await callback_query.answer()
        
        menu_text = (
            "🏠 *Главное меню*\n\n"
            "Выберите интересующий вас раздел:"
        )
        
        keyboard_menu = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Твои Прогнозы", callback_data="menu_forecasts")],
            [InlineKeyboardButton(text="📚 Интересное", callback_data="menu_interesting")],
            [InlineKeyboardButton(text="💬 Консультации", callback_data="menu_consultations")],
            [InlineKeyboardButton(text="📋 Программы", callback_data="menu_programs")],
            [InlineKeyboardButton(text="👤 Про меня", callback_data="menu_about")],
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu_question")],
            [InlineKeyboardButton(text="🔘 Создать карту БаЦзы", callback_data="start_new")],
            [InlineKeyboardButton(text="📤 Поделись ботом", callback_data="share_bot")],
        ])
        
        await callback_query.message.answer(menu_text, reply_markup=keyboard_menu, parse_mode='Markdown')
    
    # Обработчики консультаций
    @dp.callback_query(lambda c: c.data.startswith("consultation_individual_"))
    async def consultation_individual_handler(callback_query, state: FSMContext):
        """Индивидуальная консультация"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        individual_text = (
            "🔮 *Индивидуальная консультация*\n\n"
            "**Что включает:**\n"
            "• Полный анализ вашей карты БаЦзы\n"
            "• Определение сильных сторон и талантов\n"
            "• Рекомендации по карьере и отношениям\n"
            "• Прогноз на ближайшие годы\n"
            "• Ответы на ваши вопросы\n\n"
            "**Длительность:** 60-90 минут\n"
            "**Формат:** Онлайн или очно\n"
            "**Результат:** Персональный план развития"
        )
        
        keyboard_individual = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Записаться на консультацию", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"consultation_individual_details_{user_id}")],
            [InlineKeyboardButton(text="🔙 К консультациям", callback_data="menu_consultations")],
        ])
        
        await callback_query.message.answer(individual_text, reply_markup=keyboard_individual, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_cosmic_"))
    async def consultation_cosmic_handler(callback_query, state: FSMContext):
        """Программа «Космический-2026»"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        cosmic_text = (
            "🚀 *Программа «Космический-2026»*\n\n"
            "**Что включает:**\n"
            "• Детальный прогноз на 2026 год\n"
            "• Благоприятные периоды для важных решений\n"
            "• Карьерные возможности и риски\n"
            "• Личные отношения и здоровье\n"
            "• Рекомендации по месяцам\n\n"
            "**Формат:** Групповая программа с персональными прогнозами\n"
            "**Длительность:** 3 месяца\n"
            "**Результат:** Полное понимание своего года"
        )
        
        keyboard_cosmic = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Записаться на программу", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"consultation_cosmic_details_{user_id}")],
            [InlineKeyboardButton(text="🔙 К консультациям", callback_data="menu_consultations")],
        ])
        
        await callback_query.message.answer(cosmic_text, reply_markup=keyboard_cosmic, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data.startswith("consultation_learn_"))
    async def consultation_learn_handler(callback_query, state: FSMContext):
        """Обучиться анализу БаЦзы"""
        await callback_query.answer()
        
        user_id = callback_query.from_user.id
        
        learn_text = (
            "📚 *Обучиться анализу БаЦзы*\n\n"
            "**Что включает:**\n"
            "• Основы системы БаЦзы\n"
            "• Как читать карты рождения\n"
            "• Анализ элементов и их взаимодействие\n"
            "• Практические упражнения\n"
            "• Разбор реальных кейсов\n\n"
            "**Формат:** Онлайн-курс с практикой\n"
            "**Длительность:** 6 недель\n"
            "**Результат:** Самостоятельный анализ карт БаЦзы"
        )
        
        keyboard_learn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Записаться на обучение", url="https://t.me/твойник")],
            [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"consultation_learn_details_{user_id}")],
            [InlineKeyboardButton(text="🔙 К консультациям", callback_data="menu_consultations")],
        ])
        
        await callback_query.message.answer(learn_text, reply_markup=keyboard_learn, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "share_bot")
    async def share_bot_handler(callback_query, state: FSMContext):
        """Поделись ботом с друзьями"""
        await callback_query.answer()
        
        share_text = (
            "📤 *Поделись ботом с друзьями*\n\n"
            "Помогите близким узнать больше о себе и получить персональные прогнозы!\n\n"
            "**Что получат ваши друзья:**\n"
            "• 🔮 Персональную карту БаЦзы\n"
            "• 📅 Прогнозы на год и месяц\n"
            "• 💼 Рекомендации по карьере\n"
            "• ❤️ Советы по отношениям\n"
            "• 🎯 Понимание своих талантов\n\n"
            "**Как поделиться:**\n"
            "• Скопируйте ссылку на бота\n"
            "• Отправьте другу в Telegram\n"
            "• Или поделитесь через кнопку ниже"
        )
        
        keyboard_share = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", url="https://t.me/KiByro_bot?start=share")],
            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_link")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")],
        ])
        
        await callback_query.message.answer(share_text, reply_markup=keyboard_share, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "copy_link")
    async def copy_link_handler(callback_query, state: FSMContext):
        """Скопировать ссылку на бота"""
        await callback_query.answer()
        
        bot_link = "https://t.me/KiByro_bot?start=share"
        
        copy_text = (
            f"🔗 *Ссылка на бота:*\n\n"
            f"`{bot_link}`\n\n"
            f"**Как использовать:**\n"
            f"• Скопируйте ссылку выше\n"
            f"• Отправьте другу в Telegram\n"
            f"• Или поделитесь через кнопку 'Поделиться'"
        )
        
        keyboard_copy = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={bot_link}&text=🔮%20Узнай%20свою%20карту%20БаЦзы%20и%20получи%20персональные%20прогнозы!")],
            [InlineKeyboardButton(text="🔙 К поделиться", callback_data="share_bot")],
        ])
        
        await callback_query.message.answer(copy_text, reply_markup=keyboard_copy, parse_mode='Markdown')
    
    @dp.callback_query(lambda c: c.data == "start_new")
    async def start_new_handler(callback_query, state: FSMContext):
        """Начать создание новой карты"""
        await callback_query.answer()
        
        welcome_text = (
            "👋 «Здравствуйте! Я — ассистент Юлии Скибы и ваш персональный помощник по БаЦзы. "
            "Хотите узнать больше о Себе и получить полезные рекомендации?»"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Да, хочу", callback_data="yes_want")],
        ])
        
        await callback_query.message.answer(welcome_text, reply_markup=keyboard)
        await state.set_state(UserStates.waiting_for_choice)

def _validate_date(date_str: str) -> bool:
    """Простая валидация даты"""
    try:
        parts = date_str.split('.')
        if len(parts) != 3:
            return False
        
        day, month, year = parts
        day = int(day)
        month = int(month)
        year = int(year)
        
        if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
            return False
        
        return True
    except:
        return False

def _validate_time(time_str: str) -> bool:
    """Простая валидация времени"""
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return False
        
        hour, minute = parts
        hour = int(hour)
        minute = int(minute)
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False
        
        return True
    except:
        return False

async def _calculate_and_send_bazi(message: Message, birth_date: str, birth_time: str, birth_city: str):
    """Расчет и отправка результата БаЦзы"""
    try:
        # Рассчитываем БаЦзы
        result = bazi_calc.calculate_bazi(birth_date, birth_time, birth_city)
        
        # Сохраняем результат в базе данных
        user_id = message.from_user.id
        db.save_bazi_data(user_id, str(result))
        
        # Отправляем результат пошагово
        await _send_bazi_result_step_by_step(message, result)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при расчете БаЦзы: {str(e)}\n\n"
            "Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )

async def _send_bazi_result_step_by_step(message: Message, result: Dict):
    """Пошаговая отправка результата БаЦзы"""
    user_id = message.from_user.id
    
    # Шаг 1: Основная информация
    step1_text = (
        f"{formulations.get_formulation('results', 'card_ready')}\n\n"
        f"📅 Дата рождения: {result['birth_date']}\n"
        f"🕐 Время рождения: {result['birth_time']}\n"
        f"🏙️ Место рождения: {result['birth_city']}\n\n"
        f"🌟 *Элемент личности: {result['element']} {result['polarity']} {result['personality']['emoji']}*\n"
        f"🐲 *Животное года: {result['year_animal']}*\n\n"
        f"{formulations.get_formulation('results', 'personality_question')}"
    )
    
    keyboard1 = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔘 Да, расскажите!", callback_data=f"personality_desc_{user_id}")],
        [InlineKeyboardButton(text="🔘 Сразу подсказку на месяц", callback_data=f"show_advice_{user_id}")],
    ])
    
    await message.answer(step1_text, reply_markup=keyboard1, parse_mode='Markdown')
