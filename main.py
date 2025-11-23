# main.py
import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from config import BOT_TOKEN
from vision import YandexVision
from analyzer import CompositionAnalyzer
from database import AlloyDatabase
from keyboards import get_main_keyboard, get_analysis_keyboard

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация компонентов
vision = YandexVision()
analyzer = CompositionAnalyzer()
database = AlloyDatabase("alloys_database.json")

def start(update: Update, context: CallbackContext):
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
    update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

def handle_photo(update: Update, context: CallbackContext):
    try:
        # Скачиваем фото
        photo_file = update.message.photo[-1].get_file()
        file_path = f"images/{update.update_id}.jpg"
        
        os.makedirs("images", exist_ok=True)
        photo_file.download(file_path)
        
        update.message.reply_text("🔄 Обрабатываю изображение...")
        print(f"📷 Получено фото: {file_path}")
        
        # Распознаем текст
        text = vision.extract_text_from_image(file_path)
        print(f"📝 Распознанный текст: {text}")
        
        if not text:
            update.message.reply_text("❌ Не удалось распознать текст на изображении")
            return
        
        # Парсим состав
        composition = analyzer.parse_composition(text)
        
        # Анализируем и отправляем результат
        send_analysis_result(update, composition)
        
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        update.message.reply_text("❌ Ошибка при обработке изображения")

def handle_text(update: Update, context: CallbackContext):
    """Обрабатывает все текстовые сообщения"""
    text = update.message.text
    print(f"📝 Получен текст: {text}")
    
    # Сначала проверяем команды меню
    if handle_menu_commands(update, text):
        return
    
    # Если не команда, пытаемся распарсить как химический состав
    composition = analyzer.parse_composition(text)
    
    if composition:
        send_analysis_result(update, composition)
    else:
        update.message.reply_text(
            "❌ Не удалось найти химический состав.\n\n"
            "Попробуйте в формате:\n"
            "• Cu 75.45%, Ni 12.50%, Zn 9.76%\n"
            "• Cu: 62.59, Zn: 33.41\n"
            "• Cu 62.59 Zn 33.41 Pb 1.71\n\n"
            "Или используйте кнопки меню 👇",
            reply_markup=get_main_keyboard()
        )

def handle_menu_commands(update, text):
    """Обрабатывает команды меню, возвращает True если команда обработана"""
    if text == "📸 Анализировать фото":
        update.message.reply_text("Отправьте фото с анализом состава металла")
        return True
    elif text == "ℹ️ Помощь":
        help_command(update, None)
        return True
    elif text == "📊 Пример анализа":
        show_example(update)
        return True
    elif text == "🔍 База сплавов":
        show_alloys_database(update)
        return True
    elif text == "🔄 Новый анализ":
        update.message.reply_text("Отправьте фото или состав текстом для анализа", reply_markup=get_main_keyboard())
        return True
    elif text == "🏠 Главное меню":
        start(update, None)
        return True
    return False

def send_analysis_result(update, composition):
    """Отправляет результат анализа"""
    if not composition:
        update.message.reply_text(
            "❌ Не удалось определить химический состав.\n\n"
            "Проверьте формат данных и попробуйте снова."
        )
        return
    
    # Анализируем
    analysis = analyzer.analyze_composition(composition)
    matches = database.find_matching_alloys(composition)
    
    # ФИЛЬТРУЕМ результаты для релевантных сплавов
    matches = analyzer.filter_relevant_alloys(composition, matches)
    
    # Формируем ответ
    response = format_analysis_response(composition, analysis, matches)
    update.message.reply_text(response, reply_markup=get_analysis_keyboard(), parse_mode='Markdown')

def format_analysis_response(composition, analysis, matches):
    """Форматирует ответ с результатами анализа"""
    response = "🔬 *Результаты анализа*\n\n"
    
    # Основное описание
    response += f"{analysis['description']}\n\n"
    
    # Детальный состав
    response += "*📊 Подробный состав:*\n"
    element_descriptions = analyzer.get_element_descriptions(composition)
    for desc in element_descriptions:
        response += f"{desc}\n"
    
    # Применение
    if analysis['possible_applications']:
        response += f"\n*💼 Возможное применение:*\n"
        apps = analysis['possible_applications']
        for i, app in enumerate(apps[:4], 1):
            response += f"{i}. {app}\n"
    
    # Подходящие сплавы
    if matches:
        response += f"\n*🎯 Вероятные марки сплавов:*\n"
        for i, match in enumerate(matches, 1):
            response += f"{i}. *{match['name']}* (совпадение {match['score']*100:.1f}%)\n"
    else:
        response += "\n*❓ Подходящие марки сплавов не найдены*\n"
        response += "*💡 Совет:* Проверьте правильность введенных данных или используйте кнопку 'База сплавов' для ручного поиска\n"
    
    # Итог
    if analysis['main_element']:
        main_elem = analysis['main_element'][0]
        response += f"\n*💎 Простыми словами:* это {main_elem}-основной сплав"
        if main_elem == 'Cu':
            response += " с хорошей электропроводностью и коррозионной стойкостью"
        elif main_elem == 'Al':
            response += " легкий и прочный"
        elif main_elem == 'Ti':
            response += " прочный и коррозионностойкий"
        elif main_elem == 'Fe':
            response += " прочный и надежный"
        elif main_elem == 'Ni':
            response += " коррозионностойкий и жаропрочный"
        response += ". Подходит для применения в указанных областях.\n"
    
    # Проверка данных
    if analysis['recommendations']:
        response += f"\n*📈 Проверка:* {analysis['recommendations'][0]}"
    
    return response

def help_command(update: Update, context: CallbackContext):
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
Cu, Zn, Pb, Fe, Al, Ni, Sn, Ti, Si, C, Mn, Cr, Mg, Ag, Au и другие

*🔍 База сплавов:*
Используйте кнопку 'База сплавов' для просмотра всех доступных марок
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def show_example(update: Update):
    example_text = """
📋 *Пример анализа:*

*Если отправить текст:* `Cu 75.45%, Ni 12.50%, Zn 9.76%`

*Результат:*
Этот сплав состоит в основном из **меди (Cu)** — 75.45%, что делает его похожим на латунь или медно-никелевый сплав.

*📊 Подробный состав:*
• Cu — 75.45%: **медь** — основа сплава, обеспечивает электропроводность и пластичность
• Ni — 12.50%: **никель** — придаёт прочность и устойчивость к коррозии
• Zn — 9.76%: **цинк** — улучшает литейные свойства, снижает стоимость

*💼 Возможное применение:*
1. ювелирные изделия
2. монеты
3. химическое оборудование
4. морская техника

*🎯 Вероятные марки:*
1. Мельхиор МН19
2. Нейзильбер МНЦ15-20
    """
    update.message.reply_text(example_text, parse_mode='Markdown')

def show_alloys_database(update: Update):
    database_info = """
📚 *База сплавов в системе:*

*Медные сплавы:*
• Латуни (Л63, Л68, Л80, ЛС59-1)
• Бронзы (БрОФ, БрА, БрК)  
• Медно-никелевые (Мельхиор, Нейзильбер)

*Алюминиевые сплавы:*
• Деформируемые (Д1, Д16, АМг)
• Литейные (АК, АЛ)

*Титановые сплавы:*
• ВТ1-0, ВТ5, ВТ6, ВТ8

*Стали:*
• Конструкционные (Ст3, 20, 45, 40Х)
• Нержавеющие (12Х18Н10Т, 95Х18)
• Инструментальные (У7-У12, Р6М5)

*И многие другие категории...*

*💡 Для поиска конкретного сплава отправьте его химический состав!*
    """
    update.message.reply_text(database_info, parse_mode='Markdown')

def main():
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # Обработчики команд
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        
        # Обработчики сообщений
        dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))
        dispatcher.add_handler(MessageHandler(Filters.text, handle_text))
        
        print("🤖 Бот запускается...")
        updater.start_polling()
        print("✅ Бот успешно запущен и готов к работе!")
        updater.idle()
        
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
