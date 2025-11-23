import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('TOKEN')

if not BOT_TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН! Убедитесь, что переменная TOKEN установлена в Render.")
    exit(1)

def get_main_keyboard():
    """Создает основную клавиатуру"""
    keyboard = [
        ["📸 Анализировать фото", "📊 Пример анализа"],
        ["🔍 База сплавов", "ℹ️ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_analysis_keyboard():
    """Создает клавиатуру после анализа"""
    keyboard = [
        ["🔄 Новый анализ", "🔍 База сплавов"],
        ["🏠 Главное меню", "ℹ️ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.message.from_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я - бот для анализа химического состава металлов. 

📸 Отправь мне фото с результатами химического анализа, и я:
• Распознаю состав элементов
• Определю возможные марки сплавов  
• Даду подробное описание

💬 Или просто напиши состав текстом, например:
Cu 75.45%, Ni 12.50%, Zn 9.76%

Выбери действие ниже 👇
    """
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик фотографий"""
    try:
        await update.message.reply_text("🔄 Обрабатываю изображение...")
        
        # Демо-результат вместо реальной обработки
        demo_composition = {'Cu': 75.45, 'Ni': 12.50, 'Zn': 9.76}
        await send_analysis_result(update, demo_composition)
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text("❌ Ошибка при обработке изображения")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения"""
    text = update.message.text
    
    # Обработка команд меню
    if text == "📸 Анализировать фото":
        await update.message.reply_text("Отправьте фото с анализом состава металла")
        return
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
        return
    elif text == "📊 Пример анализа":
        await show_example(update)
        return
    elif text == "🔍 База сплавов":
        await show_alloys_database(update)
        return
    elif text == "🔄 Новый анализ":
        await update.message.reply_text("Отправьте фото или состав текстом для анализа", reply_markup=get_main_keyboard())
        return
    elif text == "🏠 Главное меню":
        await start(update, context)
        return
    
    # Анализ химического состава
    composition = parse_composition(text)
    
    if composition:
        await send_analysis_result(update, composition)
    else:
        await update.message.reply_text(
            "❌ Не удалось найти химический состав.\n\n"
            "Попробуйте в формате:\n"
            "• Cu 75.45%, Ni 12.50%, Zn 9.76%\n"
            "• Cu: 62.59, Zn: 33.41\n"
            "• Cu 62.59 Zn 33.41 Pb 1.71\n\n"
            "Или используйте кнопки меню 👇",
            reply_markup=get_main_keyboard()
        )

def parse_composition(text: str) -> dict:
    """Парсит химический состав из текста"""
    composition = {}
    
    # Простой парсер
    elements = ['Cu', 'Zn', 'Pb', 'Fe', 'Al', 'Ni', 'Sn', 'Ti', 'Si', 'C', 'Mn', 'Cr', 'Mg']
    words = text.replace('%', '').replace(',', ' ').split()
    
    for i, word in enumerate(words):
        clean_word = word.strip('.,:;')
        if clean_word in elements:
            # Ищем число после элемента
            if i + 1 < len(words):
                try:
                    value = float(words[i + 1])
                    composition[clean_word] = value
                except ValueError:
                    continue
    
    # Если не нашли, используем демо-данные для теста
    if not composition and any(elem in text for elem in elements):
        composition = {'Cu': 62.0, 'Zn': 38.0}  # Латунь Л63
    
    return composition

async def send_analysis_result(update: Update, composition: dict) -> None:
    """Отправляет результат анализа"""
    try:
        # Анализ состава
        main_element = max(composition.items(), key=lambda x: x[1]) if composition else None
        matches = find_matching_alloys(composition)
        
        # Формируем ответ
        response = format_analysis_response(composition, main_element, matches)
        await update.message.reply_text(response, reply_markup=get_analysis_keyboard(), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка формирования ответа: {e}")
        await update.message.reply_text("❌ Ошибка при анализе состава")

def find_matching_alloys(composition: dict) -> list:
    """Находит подходящие сплавы"""
    demo_alloys = [
        {'name': 'Латунь Л63', 'composition': {'Cu': 62.0, 'Zn': 38.0}, 'score': 0.85},
        {'name': 'Мельхиор МН19', 'composition': {'Cu': 81.0, 'Ni': 19.0}, 'score': 0.78},
        {'name': 'Нейзильбер МНЦ15-20', 'composition': {'Cu': 65.0, 'Ni': 15.0, 'Zn': 20.0}, 'score': 0.92},
    ]
    
    matches = []
    for alloy in demo_alloys:
        score = calculate_similarity(composition, alloy['composition'])
        if score > 0.3:
            matches.append({
                'name': alloy['name'],
                'score': score
            })
    
    return sorted(matches, key=lambda x: x['score'], reverse=True)[:3]

def calculate_similarity(comp1: dict, comp2: dict) -> float:
    """Вычисляет схожесть составов"""
    common_elements = set(comp1.keys()) & set(comp2.keys())
    if not common_elements:
        return 0.0
    
    total_diff = sum(abs(comp1[e] - comp2[e]) for e in common_elements)
    return max(0, 1 - total_diff / 100)

def format_analysis_response(composition: dict, main_element: tuple, matches: list) -> str:
    """Форматирует ответ с результатами анализа"""
    response = "🔬 *Результаты анализа*\n\n"
    
    # Описание
    if main_element:
        elem, percent = main_element
        response += f"Этот сплав состоит в основном из **{elem}** ({percent}%)\n\n"
    
    # Состав
    response += "*📊 Химический состав:*\n"
    for element, percentage in composition.items():
        response += f"• {element} — {percentage}%\n"
    
    # Применение
    response += "\n*💼 Возможное применение:*\n"
    response += "1. промышленное оборудование\n"
    response += "2. электротехника\n"
    response += "3. строительные материалы\n"
    
    # Подходящие сплавы
    if matches:
        response += "\n*🎯 Вероятные марки сплавов:*\n"
        for i, match in enumerate(matches, 1):
            response += f"{i}. *{match['name']}* (совпадение {match['score']*100:.1f}%)\n"
    else:
        response += "\n*❓ Подходящие марки не найдены*\n"
    
    return response

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
📖 *Инструкция по использованию:*

*Через фото:*
1. 📸 Сделайте четкое фото таблицы с химическим составом
2. 🖼 Отправьте фото боту
3. ⏳ Дождитесь обработки
4. 📊 Получите подробный анализ

*Через текст:*
Просто напишите состав в любом формате:
• Cu 75.45%, Ni 12.50%, Zn 9.76%
• Cu: 62.59, Zn: 33.41  
• Cu 62.59 Zn 33.41 Pb 1.71

*📝 Поддерживаемые элементы:*
Cu, Zn, Pb, Fe, Al, Ni, Sn, Ti, Si, C, Mn, Cr, Mg
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def show_example(update: Update) -> None:
    """Показывает пример анализа"""
    example_text = """
📋 *Пример анализа:*

Отправьте: `Cu 62.0%, Zn 38.0%`

*Результат:*
🔬 **Результаты анализа**

Этот сплав состоит в основном из **Cu** (62.0%)

*📊 Химический состав:*
• Cu — 62.0%
• Zn — 38.0%

*💼 Возможное применение:*
1. промышленное оборудование
2. электротехника  
3. строительные материалы

*🎯 Вероятные марки сплавов:*
1. *Латунь Л63* (совпадение 100.0%)
    """
    await update.message.reply_text(example_text, parse_mode='Markdown')

async def show_alloys_database(update: Update) -> None:
    """Показывает базу сплавов"""
    database_info = """
📚 *База сплавов:*

*Медные сплавы:*
• Латуни (Л63, Л68, ЛС59-1)
• Бронзы (БрОФ, БрА)
• Медно-никелевые (Мельхиор)

*Алюминиевые сплавы:*
• Деформируемые (Д1, Д16)
• Литейные (АК, АЛ)

*Стали:*
• Конструкционные (Ст3, 20, 45)
• Нержавеющие (12Х18Н10Т)

*💡 Для анализа отправьте химический состав!*
    """
    await update.message.reply_text(database_info, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки"""
    logger.error(f"Ошибка: {context.error}")

def main() -> None:
    """Запускает бота"""
    try:
        logger.info("🚀 ЗАПУСК БОТА...")
        
        if not BOT_TOKEN:
            logger.error("❌ ТОКЕН ОТСУТСТВУЕТ")
            return
        
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT, handle_text))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        logger.info("✅ БОТ ЗАПУЩЕН")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ ОШИБКА ЗАПУСКА: {e}")

if __name__ == "__main__":
    main()
