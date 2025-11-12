import requests
import re
from datetime import datetime
from typing import Dict, Optional
import json

class MingliBaziCalculator:
    """Интеграция с калькулятором БаЦзы mingli.ru"""
    
    def __init__(self):
        self.base_url = "https://www.mingli.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Словарь китайских иероглифов и их элементов
        self.heavenly_stems = {
            '甲': {'element': 'Дерево', 'polarity': 'Ян', 'name': 'Цзя'},
            '乙': {'element': 'Дерево', 'polarity': 'Инь', 'name': 'И'},
            '丙': {'element': 'Огонь', 'polarity': 'Ян', 'name': 'Бин'},
            '丁': {'element': 'Огонь', 'polarity': 'Инь', 'name': 'Дин'},
            '戊': {'element': 'Земля', 'polarity': 'Ян', 'name': 'У'},
            '己': {'element': 'Земля', 'polarity': 'Инь', 'name': 'Цзи'},
            '庚': {'element': 'Металл', 'polarity': 'Ян', 'name': 'Гэн'},
            '辛': {'element': 'Металл', 'polarity': 'Инь', 'name': 'Син'},
            '壬': {'element': 'Вода', 'polarity': 'Ян', 'name': 'Жэнь'},
            '癸': {'element': 'Вода', 'polarity': 'Инь', 'name': 'Гуй'}
        }
        
        # Словарь земных ветвей и животных
        self.earthly_branches = {
            '子': {'animal': 'Крыса', 'element': 'Вода'},
            '丑': {'animal': 'Бык', 'element': 'Земля'},
            '寅': {'animal': 'Тигр', 'element': 'Дерево'},
            '卯': {'animal': 'Кролик', 'element': 'Дерево'},
            '辰': {'animal': 'Дракон', 'element': 'Земля'},
            '巳': {'animal': 'Змея', 'element': 'Огонь'},
            '午': {'animal': 'Лошадь', 'element': 'Огонь'},
            '未': {'animal': 'Коза', 'element': 'Земля'},
            '申': {'animal': 'Обезьяна', 'element': 'Металл'},
            '酉': {'animal': 'Петух', 'element': 'Металл'},
            '戌': {'animal': 'Собака', 'element': 'Земля'},
            '亥': {'animal': 'Свинья', 'element': 'Вода'}
        }
    
    def calculate_bazi(self, birth_date: str, birth_time: str, birth_city: str, 
                      gender: str = "Жен") -> Dict:
        """
        Расчет БаЦзы через калькулятор mingli.ru
        
        Args:
            birth_date: Дата в формате дд.мм.гггг
            birth_time: Время в формате чч:мм
            birth_city: Город рождения
            gender: Пол (Муж/Жен)
        
        Returns:
            Dict с данными БаЦзы карты
        """
        try:
            # Парсим дату
            day, month, year = birth_date.split('.')
            
            # Подготавливаем данные для отправки
            form_data = {
                'name': '',  # Имя не обязательно
                'sex': gender,
                'place': birth_city,
                'year': year,
                'month': month,
                'day': day,
                'hour': birth_time.split(':')[0],
                'minute': birth_time.split(':')[1]
            }
            
            # Отправляем запрос
            response = self.session.post(self.base_url, data=form_data)
            
            if response.status_code == 200:
                # Парсим результат
                bazi_data = self._parse_response(response.text, birth_date)
                return bazi_data
            else:
                raise Exception(f"Ошибка сервера: {response.status_code}")
                
        except Exception as e:
            # Если не удалось получить данные с сайта, используем упрощенный расчет
            return self._fallback_calculation(birth_date, birth_time, birth_city)
    
    def _parse_response(self, html_content: str, birth_date: str) -> Dict:
        """Парсинг HTML ответа от калькулятора mingli.ru"""
        try:
            # Извлекаем данные из HTML
            # Ищем элемент личности из колонки ДЕНЬ (верхняя клетка)
            
            element = "Земля"  # По умолчанию
            polarity = "Инь"   # По умолчанию
            day_stem_char = ""
            
            # Улучшенный поиск колонки ДЕНЬ - ищем таблицу БаЦзы
            # Ищем паттерн таблицы с колонками ЧАС, ДЕНЬ, МЕСЯЦ, ГОД
            table_pattern = r'(?:ЧАС|ДЕНЬ|МЕСЯЦ|ГОД).*?(?:ЧАС|ДЕНЬ|МЕСЯЦ|ГОД).*?(?:ЧАС|ДЕНЬ|МЕСЯЦ|ГОД).*?(?:ЧАС|ДЕНЬ|МЕСЯЦ|ГОД)'
            table_match = re.search(table_pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if table_match:
                table_content = table_match.group(0)
                # Ищем первую ячейку в колонке ДЕНЬ
                day_column_pattern = r'ДЕНЬ.*?([甲-癸]).*?(?:Инь|Ян)\s+(Огонь|Дерево|Земля|Металл|Вода)'
                day_match = re.search(day_column_pattern, table_content, re.IGNORECASE)
                
                if day_match:
                    day_stem_char = day_match.group(1)
                    polarity_text = day_match.group(2)
                    
                    # Определяем полярность
                    polarity_pattern = rf'{day_stem_char}.*?((?:Инь|Ян))\s+(Огонь|Дерево|Земля|Металл|Вода)'
                    polarity_match = re.search(polarity_pattern, table_content, re.IGNORECASE)
                    
                    if polarity_match:
                        polarity = polarity_match.group(1)
                        element = polarity_match.group(2)
                    else:
                        # Используем данные из словаря
                        if day_stem_char in self.heavenly_stems:
                            element = self.heavenly_stems[day_stem_char]['element']
                            polarity = self.heavenly_stems[day_stem_char]['polarity']
            
            # Если не нашли через таблицу, используем старый метод
            if not day_stem_char:
                for char, data in self.heavenly_stems.items():
                    if char in html_content:
                        # Проверяем, что это именно колонка ДЕНЬ
                        day_patterns = [
                            rf'ДЕНЬ.*?{char}',
                            rf'{char}.*?ДЕНЬ',
                            rf'День.*?{char}',
                            rf'{char}.*?День'
                        ]
                        
                        for pattern in day_patterns:
                            if re.search(pattern, html_content, re.IGNORECASE | re.DOTALL):
                                element = data['element']
                                polarity = data['polarity']
                                day_stem_char = char
                                break
                        
                        if day_stem_char:
                            break
            
            # Если не нашли по иероглифам, ищем по тексту
            if not day_stem_char:
                day_element_patterns = [
                    r'ДЕНЬ.*?(\w+)\s+(Огонь|Дерево|Земля|Металл|Вода)',
                    r'День.*?(\w+)\s+(Огонь|Дерево|Земля|Металл|Вода)',
                    r'Инь\s+(Огонь|Дерево|Земля|Металл|Вода)',
                    r'Ян\s+(Огонь|Дерево|Земля|Металл|Вода)',
                    r'(\w+)\s+(Огонь|Дерево|Земля|Металл|Вода).*?ДЕНЬ',
                    r'Элемент личности.*?(\w+)'
                ]
                
                for pattern in day_element_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        if len(match.groups()) >= 2:
                            polarity = match.group(1) if match.group(1) in ['Инь', 'Ян'] else polarity
                            element = match.group(2) if match.group(2) in ['Огонь', 'Дерево', 'Земля', 'Металл', 'Вода'] else match.group(1)
                        else:
                            element = match.group(1)
                        break
            
            # Ищем животное года
            animal = "Свинья"  # По умолчанию
            year_branch_char = ""
            
            # Сначала ищем по китайским иероглифам
            for char, data in self.earthly_branches.items():
                if char in html_content:
                    # Проверяем, что это именно колонка ГОД
                    year_patterns = [
                        rf'ГОД.*?{char}',
                        rf'{char}.*?ГОД',
                        rf'Год.*?{char}',
                        rf'{char}.*?Год'
                    ]
                    
                    for pattern in year_patterns:
                        if re.search(pattern, html_content, re.IGNORECASE | re.DOTALL):
                            animal = data['animal']
                            year_branch_char = char
                            break
                    
                    if year_branch_char:
                        break
            
            # Если не нашли по иероглифам, ищем по тексту
            if not year_branch_char:
                animal_patterns = [
                    r'(\w+)\s*🐭|🐂|🐅|🐰|🐲|🐍|🐴|🐐|🐒|🐓|🐕|🐷',
                    r'(Крыса|Бык|Тигр|Кролик|Дракон|Змея|Лошадь|Коза|Обезьяна|Петух|Собака|Свинья)',
                    r'Год.*?(\w+)'
                ]
                
                for pattern in animal_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        animal = match.group(1)
                        break
            
            # Если все еще не нашли, используем расчет по году
            if animal == "Свинья" and not year_branch_char:
                # Извлекаем год из HTML или используем переданный год
                year_match = re.search(r'(\d{4})', html_content)
                if year_match:
                    year_int = int(year_match.group(1))
                    animal = self._get_year_animal(year_int)
                else:
                    # Используем год из даты рождения
                    day, month, year = birth_date.split('.')
                    year_int = int(year)
                    animal = self._get_year_animal(year_int)
            
            # Определяем характеристики на основе элемента и полярности
            from advice_generator import get_element_description, generate_monthly_advice, generate_summary_2025
            
            element_desc = get_element_description(element, polarity)
            personality = {
                'element': element,
                'polarity': polarity,
                'emoji': element_desc['emoji'],
                'metaphor': element_desc['metaphor'],
                'description': element_desc['description'],
                'superpower': element_desc['superpower'],
                'traits': self._get_personality_by_element(element)['traits']
            }
            
            return {
                'personality_type': personality,
                'year_animal': animal,
                'day_element': element,
                'day_polarity': polarity,
                'day_stem_char': day_stem_char,
                'year_branch_char': year_branch_char,
                'monthly_advice': generate_monthly_advice(element, polarity),
                'summary_2025': generate_summary_2025(element, polarity),
                'birth_info': {
                    'date': birth_date,
                    'time': birth_time,
                    'city': birth_city
                },
                'source': 'mingli_calculator'
            }
            
        except Exception as e:
            raise Exception(f"Ошибка парсинга: {str(e)}")
    
    def _get_personality_by_element(self, element: str) -> Dict:
        """Получение характеристик личности по элементу"""
        element_map = {
            'Дерево': {
                'element': 'Дерево',
                'emoji': '🌳',
                'traits': ['Творчество', 'Рост', 'Лидерство', 'Инновации', 'Гибкость']
            },
            'Огонь': {
                'element': 'Огонь', 
                'emoji': '🔥',
                'traits': ['Энергия', 'Страсть', 'Лидерство', 'Амбиции', 'Мотивация']
            },
            'Земля': {
                'element': 'Земля',
                'emoji': '🌍', 
                'traits': ['Стабильность', 'Надежность', 'Практичность', 'Терпение', 'Забота']
            },
            'Металл': {
                'element': 'Металл',
                'emoji': '⚡',
                'traits': ['Структура', 'Дисциплина', 'Анализ', 'Точность', 'Организованность']
            },
            'Вода': {
                'element': 'Вода',
                'emoji': '💧',
                'traits': ['Мудрость', 'Интуиция', 'Адаптивность', 'Глубина', 'Чувствительность']
            }
        }
        
        return element_map.get(element, element_map['Земля'])
    
    def _generate_advice(self, element: str) -> str:
        """Генерация совета на месяц"""
        advice_map = {
            'Дерево': "Сосредоточьтесь на росте и развитии. Время для новых начинаний и творческих проектов.",
            'Огонь': "Проявляйте активность и энергию. Время для реализации планов и достижения целей.",
            'Земля': "Сосредоточьтесь на стабильности и практичности. Время для укрепления основ.",
            'Металл': "Проявляйте дисциплину и организованность. Время для структурирования и планирования.",
            'Вода': "Используйте интуицию и мудрость. Время для глубокого анализа и стратегического планирования."
        }
        
        return advice_map.get(element, advice_map['Земля'])
    
    def _generate_summary(self, element: str) -> str:
        """Генерация резюме 2025 года"""
        summary_map = {
            'Дерево': "2025 год благоприятен для роста и инноваций. Новые возможности в творческих сферах.",
            'Огонь': "2025 год принесет энергию и страсть. Время для активных действий и достижения целей.",
            'Земля': "2025 год будет стабильным и надежным. Время для долгосрочного планирования.",
            'Металл': "2025 год будет структурированным. Время для достижения целей и систематизации.",
            'Вода': "2025 год будет глубоким и мудрым. Время для стратегического планирования."
        }
        
        return summary_map.get(element, summary_map['Земля'])
    
    def _get_year_animal(self, year: int) -> str:
        """Определение животного года по китайскому календарю"""
        # Китайский календарь начинается с 1900 года (Крыса)
        # Каждый год соответствует одному из 12 животных
        animals = [
            'Крыса', 'Бык', 'Тигр', 'Кролик', 'Дракон', 'Змея',
            'Лошадь', 'Коза', 'Обезьяна', 'Петух', 'Собака', 'Свинья'
        ]
        
        # Вычисляем индекс животного
        # 1900 год = Крыса (индекс 0)
        animal_index = (year - 1900) % 12
        return animals[animal_index]
    
    def _fallback_calculation(self, birth_date: str, birth_time: str, birth_city: str) -> Dict:
        """Резервный расчет при недоступности профессионального калькулятора"""
        # Простой расчет по дате рождения
        day, month, year = birth_date.split('.')
        
        # Простое определение элемента по году рождения
        year_int = int(year)
        element_map = {
            0: 'Металл', 1: 'Металл',
            2: 'Вода', 3: 'Вода',
            4: 'Дерево', 5: 'Дерево',
            6: 'Огонь', 7: 'Огонь',
            8: 'Земля', 9: 'Земля'
        }
        
        element = element_map.get(year_int % 10, 'Земля')
        
        # Правильное определение животного года по китайскому календарю
        year_animal = self._get_year_animal(year_int)
        
        # Используем новый генератор советов
        from advice_generator import get_element_description, generate_monthly_advice, generate_summary_2025
        
        element_desc = get_element_description(element, 'Инь')
        personality = {
            'element': element,
            'polarity': 'Инь',
            'emoji': element_desc['emoji'],
            'metaphor': element_desc['metaphor'],
            'description': element_desc['description'],
            'superpower': element_desc['superpower'],
            'traits': self._get_personality_by_element(element)['traits']
        }
        
        return {
            'personality_type': personality,
            'year_animal': year_animal,
            'day_element': element,
            'day_polarity': 'Инь',
            'monthly_advice': generate_monthly_advice(element, 'Инь'),
            'summary_2025': generate_summary_2025(element, 'Инь'),
            'birth_info': {
                'date': birth_date,
                'time': birth_time,
                'city': birth_city
            },
            'source': 'fallback_calculation'
        }
    
    def calculate_without_time(self, birth_date: str, birth_city: str, gender: str = "Жен") -> Dict:
        """
        Расчет БаЦзы без времени рождения (только по дате)
        Использует полдень как время по умолчанию
        """
        return self.calculate_bazi(birth_date, "12:00", birth_city, gender)
