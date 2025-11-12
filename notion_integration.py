"""
Интеграция с Notion API для получения информации о консультациях
"""
import requests
import json
from typing import Dict, List, Optional

class NotionIntegration:
    def __init__(self, notion_token: str = None, database_id: str = None):
        """
        Инициализация интеграции с Notion
        
        Args:
            notion_token: Токен доступа к Notion API
            database_id: ID базы данных Notion с консультациями
        """
        self.notion_token = notion_token
        self.database_id = database_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {notion_token}" if notion_token else "",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def get_consultation_info(self) -> Dict:
        """
        Получение информации о консультациях из Notion
        Возвращает структурированную информацию о типах консультаций
        """
        # Если нет токена, возвращаем статичную информацию
        if not self.notion_token:
            return self._get_static_consultation_info()
        
        try:
            # Запрос к базе данных Notion
            url = f"{self.base_url}/databases/{self.database_id}/query"
            response = requests.post(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_notion_data(data)
            else:
                print(f"Ошибка Notion API: {response.status_code}")
                return self._get_static_consultation_info()
                
        except Exception as e:
            print(f"Ошибка при обращении к Notion: {e}")
            return self._get_static_consultation_info()
    
    def _parse_notion_data(self, notion_data: Dict) -> Dict:
        """
        Парсинг данных из Notion в структурированный формат
        """
        consultations = []
        
        for page in notion_data.get('results', []):
            properties = page.get('properties', {})
            
            consultation = {
                'title': self._extract_text(properties.get('title', {})),
                'description': self._extract_text(properties.get('description', {})),
                'price': self._extract_text(properties.get('price', {})),
                'duration': self._extract_text(properties.get('duration', {})),
                'what_solves': self._extract_text(properties.get('what_solves', {})),
                'for_whom': self._extract_text(properties.get('for_whom', {})),
                'process': self._extract_text(properties.get('process', {})),
                'result': self._extract_text(properties.get('result', {}))
            }
            consultations.append(consultation)
        
        return {
            'consultations': consultations,
            'general_info': self._get_general_consultation_info()
        }
    
    def _extract_text(self, property_data: Dict) -> str:
        """
        Извлечение текста из свойства Notion
        """
        if not property_data:
            return ""
        
        # Обработка разных типов свойств Notion
        if 'rich_text' in property_data:
            return ''.join([text['plain_text'] for text in property_data['rich_text']])
        elif 'title' in property_data:
            return ''.join([text['plain_text'] for text in property_data['title']])
        elif 'select' in property_data:
            return property_data['select'].get('name', '')
        elif 'number' in property_data:
            return str(property_data['number'])
        
        return ""
    
    def _get_static_consultation_info(self) -> Dict:
        """
        Статичная информация о консультациях (fallback)
        """
        return {
            'general_info': {
                'title': 'Консультация БаЦзы',
                'description': (
                    'БаЦзы — это древнекитайская система астрологии, которая анализирует потенциал личности '
                    'и судьбу на основе даты и времени рождения. Консультация поможет понять ваши сильные '
                    'стороны, жизненные периоды и то, куда лучше направить энергию.'
                ),
                'what_closes': (
                    '• Понимание своих сильных сторон и талантов\n'
                    '• Анализ жизненных периодов и возможностей\n'
                    '• Рекомендации по карьере и отношениям\n'
                    '• Понимание совместимости с партнерами\n'
                    '• Планирование важных решений'
                ),
                'most_used_for': (
                    '• Выбор профессии и карьерного пути\n'
                    '• Понимание отношений и совместимости\n'
                    '• Планирование важных жизненных событий\n'
                    '• Работа с личными качествами и развитием\n'
                    '• Принятие сложных решений'
                )
            },
            'consultations': [
                {
                    'title': 'Базовая консультация БаЦзы',
                    'description': 'Анализ основных элементов личности, совместимости и базовых рекомендаций',
                    'price': '5000₽',
                    'duration': '60 минут',
                    'what_solves': 'Понимание основных черт характера и базовых жизненных тенденций',
                    'for_whom': 'Для тех, кто впервые знакомится с БаЦзы',
                    'process': 'Анализ карты рождения, объяснение элементов, базовые рекомендации',
                    'result': 'Понимание своих сильных сторон и основных жизненных направлений'
                },
                {
                    'title': 'Расширенная консультация',
                    'description': 'Детальный анализ всех четырех столпов, жизненных периодов и стратегий',
                    'price': '8000₽',
                    'duration': '90 минут',
                    'what_solves': 'Глубокое понимание жизненных циклов и стратегий развития',
                    'for_whom': 'Для тех, кто хочет детального анализа и планирования',
                    'process': 'Полный анализ карты, жизненные периоды, стратегии на будущее',
                    'result': 'Четкий план действий и понимание жизненных периодов'
                },
                {
                    'title': 'Консультация по отношениям',
                    'description': 'Анализ совместимости партнеров и рекомендации по отношениям',
                    'price': '6000₽',
                    'duration': '75 минут',
                    'what_solves': 'Понимание динамики отношений и совместимости',
                    'for_whom': 'Для пар, которые хотят понять свои отношения',
                    'process': 'Анализ карт обоих партнеров, сравнение элементов, рекомендации',
                    'result': 'Понимание сильных и слабых сторон отношений'
                }
            ]
        }
    
    def _get_general_consultation_info(self) -> Dict:
        """
        Общая информация о консультациях БаЦзы
        """
        return {
            'title': 'Консультация БаЦзы',
            'description': (
                'БаЦзы — это древнекитайская система астрологии, которая анализирует потенциал личности '
                'и судьбу на основе даты и времени рождения. Консультация поможет понять ваши сильные '
                'стороны, жизненные периоды и то, куда лучше направить энергию.'
            ),
            'what_closes': (
                '• Понимание своих сильных сторон и талантов\n'
                '• Анализ жизненных периодов и возможностей\n'
                '• Рекомендации по карьере и отношениям\n'
                '• Понимание совместимости с партнерами\n'
                '• Планирование важных решений'
            ),
            'most_used_for': (
                '• Выбор профессии и карьерного пути\n'
                '• Понимание отношений и совместимости\n'
                '• Планирование важных жизненных событий\n'
                '• Работа с личными качествами и развитием\n'
                '• Принятие сложных решений'
            )
        }
    
    def format_consultation_message(self, consultation_data: Dict) -> str:
        """
        Форматирование информации о консультациях для отправки в Telegram
        """
        general_info = consultation_data.get('general_info', {})
        consultations = consultation_data.get('consultations', [])
        
        message = f"🔮 *{general_info.get('title', 'Консультация БаЦзы')}*\n\n"
        message += f"{general_info.get('description', '')}\n\n"
        
        message += "📋 *Что это закрывает:*\n"
        message += f"{general_info.get('what_closes', '')}\n\n"
        
        message += "🎯 *Чаще всего используется для:*\n"
        message += f"{general_info.get('most_used_for', '')}\n\n"
        
        message += "💼 *Варианты консультаций:*\n\n"
        
        for i, consultation in enumerate(consultations, 1):
            message += f"{i}. *{consultation.get('title', '')}*\n"
            message += f"   💰 {consultation.get('price', '')} | ⏰ {consultation.get('duration', '')}\n"
            message += f"   📝 {consultation.get('description', '')}\n\n"
        
        message += "📞 *Для записи на консультацию:*\n"
        message += "Напишите консультанту @твойник"
        
        return message
    
    def get_consultation_list(self, consultation_data: Dict) -> List[Dict]:
        """
        Получение списка консультаций для создания кнопок
        """
        consultations = consultation_data.get('consultations', [])
        
        consultation_list = []
        for consultation in consultations:
            consultation_list.append({
                'title': consultation.get('title', ''),
                'price': consultation.get('price', ''),
                'duration': consultation.get('duration', ''),
                'description': consultation.get('description', '')
            })
        
        return consultation_list
