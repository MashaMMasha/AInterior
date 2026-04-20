import random
from typing import List, Dict

# Mock responses для чата
MOCK_RESPONSES = [
    "Я вижу, вы хотите создать интерьер. Давайте начнем с описания вашего видения!",
    "Отличная идея! Какой стиль вам нравится - современный, классический или минимализм?",
    "Я могу помочь вам с расстановкой мебели. Расскажите больше о размерах комнаты.",
    "Интересно! Давайте добавим {item} в вашу сцену. Какой цвет предпочитаете?",
    "Я понимаю, что вам нужно. Могу предложить несколько вариантов расстановки мебели.",
    "Отличный выбор! Это будет прекрасно смотреться в вашем интерьере.",
]

FURNITURE_SUGGESTIONS = {
    "диван": ["современный серый диван", "классический кожаный диван", "угловой диван"],
    "стол": ["обеденный стол на 6 персон", "журнальный столик", "рабочий стол"],
    "кресло": ["кресло-качалка", "офисное кресло", "мягкое кресло"],
    "шкаф": ["платяной шкаф", "книжный шкаф", "шкаф-купе"],
}


def get_mock_response(user_message: str) -> str:
    """Генерирует mock ответ на основе сообщения пользователя"""
    user_lower = user_message.lower()
    
    # Если пользователь спрашивает про мебель
    for furniture, suggestions in FURNITURE_SUGGESTIONS.items():
        if furniture in user_lower:
            suggestion = random.choice(suggestions)
            return f"Я вижу, вам интересен {furniture}. Могу предложить: {suggestion}. Хотите добавить его в сцену?"
    
    # Если пользователь упоминает цвет
    if any(color in user_lower for color in ["белый", "черный", "серый", "синий", "красный", "зеленый"]):
        return "Отличный выбор цвета! Это будет гармонично смотреться в интерьере."
    
    # Если пользователь спрашивает про стиль
    if "стиль" in user_lower or "дизайн" in user_lower:
        styles = ["современный", "минимализм", "скандинавский", "лофт", "классический"]
        suggested_style = random.choice(styles)
        return f"Рекомендую рассмотреть {suggested_style} стиль. Он сейчас очень популярен!"
    
    # Если пользователь просит помощи
    if "помощь" in user_lower or "как" in user_lower or "?" in user_message:
        return "Конечно, помогу! Я могу создать 3D-сцену, подобрать мебель или дать советы по дизайну. Просто опишите, что вы хотите."
    
    # Если пользователь благодарит
    if "спасибо" in user_lower or "благодар" in user_lower:
        return "Всегда рад помочь! Если будут еще вопросы - обращайтесь."
    
    # Дефолтный ответ
    response = random.choice(MOCK_RESPONSES)
    return response.format(item=random.choice(list(FURNITURE_SUGGESTIONS.keys())))


def parse_intent(user_message: str) -> Dict:
    """Парсит намерение пользователя (mock)"""
    user_lower = user_message.lower()
    
    intent = {
        "action": "chat",
        "entities": {},
        "confidence": 0.8
    }
    
    # Определяем действие
    if "создай" in user_lower or "сгенерируй" in user_lower:
        intent["action"] = "generate"
    elif "добавь" in user_lower or "поставь" in user_lower:
        intent["action"] = "add_furniture"
    elif "удали" in user_lower or "убери" in user_lower:
        intent["action"] = "remove"
    elif "расставь" in user_lower or "расположи" in user_lower:
        intent["action"] = "arrange"
    
    # Извлекаем упоминания мебели
    furniture_found = []
    for furniture in FURNITURE_SUGGESTIONS.keys():
        if furniture in user_lower:
            furniture_found.append(furniture)
    
    if furniture_found:
        intent["entities"]["furniture"] = furniture_found
    
    # Извлекаем цвета
    colors = ["белый", "черный", "серый", "синий", "красный", "зеленый", "желтый", "коричневый"]
    color_found = [color for color in colors if color in user_lower]
    if color_found:
        intent["entities"]["color"] = color_found[0]
    
    # Извлекаем стили
    styles = ["современный", "минимализм", "скандинавский", "лофт", "классический"]
    style_found = [style for style in styles if style in user_lower]
    if style_found:
        intent["entities"]["style"] = style_found[0]
    
    return intent
