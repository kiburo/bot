from datetime import datetime
from typing import Optional, Tuple
import re

def validate_date(date_str: str) -> Tuple[bool, Optional[datetime]]:
    """
    Валидация даты в формате дд.мм.гггг
    
    Args:
        date_str: Строка с датой
        
    Returns:
        Tuple[bool, Optional[datetime]]: (валидна ли дата, объект datetime или None)
    """
    try:
        # Проверяем формат
        if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
            return False, None
        
        day, month, year = date_str.split('.')
        day, month, year = int(day), int(month), int(year)
        
        # Проверяем диапазоны
        if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2024):
            return False, None
        
        # Создаем объект datetime
        date_obj = datetime(year, month, day)
        
        return True, date_obj
        
    except ValueError:
        return False, None

def validate_time(time_str: str) -> Tuple[bool, Optional[Tuple[int, int]]]:
    """
    Валидация времени в формате чч:мм
    
    Args:
        time_str: Строка с временем
        
    Returns:
        Tuple[bool, Optional[Tuple[int, int]]]: (валидно ли время, (час, минута) или None)
    """
    try:
        # Проверяем формат
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            return False, None
        
        hour, minute = time_str.split(':')
        hour, minute = int(hour), int(minute)
        
        # Проверяем диапазоны
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False, None
        
        return True, (hour, minute)
        
    except ValueError:
        return False, None

def format_bazi_result(bazi_data: dict) -> str:
    """
    Форматирование результата БаЦзы для отправки пользователю
    
    Args:
        bazi_data: Данные БаЦзы карты
        
    Returns:
        str: Отформатированная строка
    """
    personality = bazi_data['personality_type']
    traits_text = '\n'.join([f"• {trait}" for trait in personality['traits']])
    
    # Добавляем информацию о животном года
    year_animal = bazi_data.get('year_animal', '')
    
    return (
        f"✨ *Ваша БаЦзы карта готова!*\n\n"
        f"📅 Дата рождения: {bazi_data['birth_info']['date']}\n"
        f"🕐 Время рождения: {bazi_data['birth_info']['time']}\n"
        f"🏙️ Место рождения: {bazi_data['birth_info']['city']}\n\n"
        f"🔮 *Ваш элемент личности: {personality['element']} {personality['emoji']}*\n"
        f"🐲 *Животное года: {year_animal}*\n\n"
        f"📊 *Характеристики:*\n"
        f"{traits_text}\n\n"
        f"💡 *Совет на месяц:*\n"
        f"{bazi_data['monthly_advice']}\n\n"
        f"🌟 *Резюме 2025 года:*\n"
        f"{bazi_data['summary_2025']}"
    )
