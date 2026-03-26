import requests
import re
import logging
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Отключаем лишние логи
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

# ТОКЕН бота
TOKEN = "8741099594:AAEYZbQuWC3Y6eO7u7QCqrTZyJi-T1MEKwA"

# Заголовки для имитации браузера
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Только видео и аудио форматы
VIDEO_EXTENSIONS = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'm3u8', 'ts', 'webm', 'm4v', '3gp']
AUDIO_EXTENSIONS = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'opus', 'wma', 'amr']

# Все форматы в одном списке
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

# Регулярное выражение для поиска видео и аудио
MEDIA_PATTERN = r'https?://[^\s"\'<>]+\.(' + '|'.join(MEDIA_EXTENSIONS) + r')(?:\?[^\s"\'<>]*)?'


def get_media_type(extension: str) -> str:
    """Определяет тип медиа (видео или аудио)"""
    extension = extension.lower()
    if extension in VIDEO_EXTENSIONS:
        return 'video'
    elif extension in AUDIO_EXTENSIONS:
        return 'audio'
    return 'other'


def get_emoji(media_type: str) -> str:
    """Возвращает эмодзи для типа медиа"""
    return '🎬' if media_type == 'video' else '🎵'


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🎬 Отправь мне ссылку на страницу, и я найду:\n\n"
        "🎬 Видео: MP4, AVI, MKV, MOV, FLV, WEBM, M3U8\n"
        "🎵 Аудио: MP3, WAV, OGG, FLAC, M4A, AAC, OPUS\n\n"
        "Просто отправь ссылку — я найду всё!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📖 Инструкция:\n\n"
        "1. Найди страницу с видео или аудио\n"
        "2. Скопируй ссылку из адресной строки\n"
        "3. Отправь ссылку мне\n"
        "4. Я найду все медиа-файлы на странице\n\n"
        "🔍 Поддерживаемые форматы:\n"
        f"🎬 Видео: {', '.join(VIDEO_EXTENSIONS)}\n"
        f"🎵 Аудио: {', '.join(AUDIO_EXTENSIONS)}"
    )


def extract_media_links(html: str, page_url: str) -> list:
    """Извлекает ссылки на видео и аудио из HTML"""
    links = []

    soup = BeautifulSoup(html, 'html.parser')

    # Теги video и audio с src
    for tag in soup.find_all(['video', 'audio']):
        if tag.get('src'):
            links.append(tag['src'])
        if tag.get('currentSrc'):
            links.append(tag['currentSrc'])

    # Теги source
    for source in soup.find_all('source'):
        if source.get('src'):
            links.append(source['src'])

    # Регулярное выражение для поиска ссылок
    for match in re.finditer(MEDIA_PATTERN, html):
        links.append(match.group(0))

    # Обрабатываем относительные ссылки
    base_url = '/'.join(page_url.split('/')[:3])
    full_links = []
    for link in links:
        if link.startswith('//'):
            full_links.append('https:' + link)
        elif link.startswith('/'):
            full_links.append(base_url + link)
        elif link.startswith('http'):
            full_links.append(link)
        else:
            full_links.append(base_url + '/' + link)

    # Убираем дубликаты
    return list(set(full_links))


def filter_by_type(links: list) -> dict:
    """Сортирует ссылки по типам (видео/аудио)"""
    result = {'video': [], 'audio': []}

    for link in links:
        ext = link.split('.')[-1].split('?')[0].lower()
        media_type = get_media_type(ext)
        if media_type in result:
            result[media_type].append(link)

    return result


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ссылок"""
    url = update.message.text.strip()

    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Это не похоже на ссылку. Отправь URL, начинающийся с http:// или https://")
        return

    await update.message.reply_text("🔍 Ищу видео и аудио на странице... Подожди немного.")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        all_links = extract_media_links(response.text, url)
        sorted_links = filter_by_type(all_links)

        total_count = len(sorted_links['video']) + len(sorted_links['audio'])

        if total_count == 0:
            await update.message.reply_text(
                "😕 Не удалось найти видео или аудио.\n\n"
                "Попробуй:\n"
                "1. Открыть страницу в браузере\n"
                "2. Нажать F12 → Network → Media\n"
                "3. Перезагрузить страницу и запустить воспроизведение\n"
                "4. Кликнуть правой кнопкой по файлу → Open in new tab → сохранить"
            )
            return

        # Отправляем статистику
        stats = []
        if sorted_links['video']:
            stats.append(f"🎬 Видео: {len(sorted_links['video'])}")
        if sorted_links['audio']:
            stats.append(f"🎵 Аудио: {len(sorted_links['audio'])}")

        await update.message.reply_text(f"✅ Найдено файлов: {total_count}\n\n" + "\n".join(stats))

        # Отправляем видео
        if sorted_links['video']:
            await update.message.reply_text(f"🎬 ВИДЕО ({len(sorted_links['video'])}):")
            for link in sorted_links['video'][:15]:
                await update.message.reply_text(f"🎬 {link}")
            if len(sorted_links['video']) > 15:
                await update.message.reply_text(f"... и ещё {len(sorted_links['video']) - 15} видео")

        # Отправляем аудио
        if sorted_links['audio']:
            await update.message.reply_text(f"🎵 АУДИО ({len(sorted_links['audio'])}):")
            for link in sorted_links['audio'][:15]:
                await update.message.reply_text(f"🎵 {link}")
            if len(sorted_links['audio']) > 15:
                await update.message.reply_text(f"... и ещё {len(sorted_links['audio']) - 15} аудио")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏰ Таймаут. Сайт долго отвечает, попробуй позже.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке страницы. Проверь ссылку.")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуй другую ссылку.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")


def main():
    """Запуск бота"""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_error_handler(error_handler)

    print("🤖 Бот запущен... Ищет только видео и аудио")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
