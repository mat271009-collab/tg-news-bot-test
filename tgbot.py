import telebot
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
import os
import schedule
import time as t
from datetime import datetime, timezone, timedelta

# Настройки
BOT_TOKEN = "8483154121:AAGKUf5QXQ5eD5wGbZH2o-MfHfQ6apgCPI4"
CHANNEL_ID = "@testovyikanalk"
MOSCOW_TZ = timezone(timedelta(hours=3))  # UTC+3 для Москвы
BOT_START_TIME = datetime.now(MOSCOW_TZ)
print(f"🕒 Бот запущен в (МСК): {BOT_START_TIME}")


bot = telebot.TeleBot(BOT_TOKEN)


def get_news_from_site():
    """Парсит новости с сайта"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
    }
    url = 'https://www.securitylab.ru/news/'

    try:
        r = requests.get(url=url, headers=headers)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "lxml")
        articles_cards = soup.find_all("a", class_="article-card")

        news_list = []
        for article in articles_cards:
            try:
                article_title = article.find("h2", class_="article-card-title").text.strip()
                article_desc = article.find("p").text.strip()
                article_url = f'https://www.securitylab.ru{article.get("href")}'

                article_date_time = article.find("time").get("datetime")

                # Парсим дату и добавляем Московскую временную зону (UTC+3)
                date_from_iso = datetime.fromisoformat(article_date_time)
                if date_from_iso.tzinfo is None:
                    # Если нет временной зоны - добавляем Московскую
                    date_from_iso = date_from_iso.replace(tzinfo=MOSCOW_TZ)

                date_time_str = date_from_iso.strftime("%Y-%m-%d %H:%M:%S")

                news_list.append({
                    "title": article_title,
                    "description": article_desc,
                    "url": article_url,
                    "date": date_time_str,
                    "date_obj": date_from_iso  # С правильной временной зоной
                })

                # ДЛЯ ОТЛАДКИ - выводим даты
                print(f"📰 Новость: {date_from_iso} | {article_title[:30]}...")

            except Exception as e:
                print(f"Ошибка при обработке статьи: {e}")
                continue

        return news_list
    except Exception as e:
        print(f"Ошибка при парсинге: {e}")
        return []


def format_news_message(news_item):
    """Форматирует новость для отправки"""
    message = f"<b>{news_item['title']}</b>\n\n"
    message += f"{news_item['description']}\n\n"
    message += f"📅 {news_item['date']}\n"
    message += f"🔗 <a href='{news_item['url']}'>Читать полностью</a>"
    return message


def send_news_to_channel():
    """Отправляет только новости, вышедшие ПОСЛЕ запуска бота"""
    try:
        # Получаем текущие новости с сайта
        current_news = get_news_from_site()

        if not current_news:
            print("Не удалось получить новости")
            return

        # Загружаем уже отправленные новости
        sent_news = load_sent_news()

        # Находим НОВЫЕ новости (которые еще не отправлялись И вышли после запуска бота)
        new_news = []

        print(f"⏰ Время запуска бота: {BOT_START_TIME}")

        for news in current_news:
            news_id = news['url'].split('/')[-1].replace('.php', '')

            # Получаем дату новости как объект datetime с временной зоной
            news_date = news['date_obj']

            # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ - посмотрим что сравниваем
            print(
                f"🔍 Проверка новости: {news_date} > {BOT_START_TIME} = {news_date > BOT_START_TIME} | {news['title'][:30]}...")

            # Проверяем две условия:
            # 1. Новость еще не отправлялась
            # 2. Новость вышла ПОСЛЕ запуска бота
            if news_id not in sent_news and news_date > BOT_START_TIME:
                new_news.append(news)
                print(f"✅ Будет отправлена: {news['title'][:40]}...")

        if not new_news:
            print("📭 Новых новостей после запуска бота нет")
            return

        print(f"🎯 Найдено {len(new_news)} новостей после запуска бота")

        # Сортируем от старых к новым и отправляем
        new_news.sort(key=lambda x: x['date_obj'])

        # Отправляем в правильном порядке
        for news in new_news:
            try:
                news_id = news['url'].split('/')[-1].replace('.php', '')

                message = format_news_message(news)
                bot.send_message(
                    CHANNEL_ID,
                    message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                print(f"📤 Отправлена новость: {news['title'][:50]}...")

                # Добавляем в отправленные
                sent_news[news_id] = news
                save_sent_news(sent_news)

                # Пауза между отправками (15 минут = 900 секунд)
                print(f"⏳ Ожидание 15 минут до следующей отправки...")
                time.sleep(420)  # 15 минут

            except Exception as e:
                print(f"❌ Ошибка при отправке: {e}")

    except Exception as e:
        print(f"💥 Общая ошибка: {e}")


def load_sent_news():
    """Загружает историю отправленных новостей"""
    try:
        with open('sent_news.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_sent_news(sent_news):
    """Сохраняет историю отправленных новостей"""
    with open('sent_news.json', 'w', encoding='utf-8') as file:
        json.dump(sent_news, file, indent=4, ensure_ascii=False)


def check_updates():
    """Проверяет обновления каждые 30 минут"""
    print(f"Проверка новостей в {datetime.now()}")
    send_news_to_channel()


# Команды для бота
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "Бот для парсинга новостей запущен!")


@bot.message_handler(commands=['news'])
def news_command(message):
    """Ручная проверка новостей"""
    send_news_to_channel()
    bot.send_message(message.chat.id, "Новости проверены и отправлены в канал!")


@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика отправленных новостей"""
    sent_news = load_sent_news()
    bot.send_message(message.chat.id, f"Отправлено новостей: {len(sent_news)}")


# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен на сервере")

    # Первая проверка сразу при запуске
    print("🔍 Первая проверка новостей...")
    send_news_to_channel()

    # Бесконечный цикл с интервалом 30 минут
    while True:
        try:
            time.sleep(1800)  # Ждем 30 минут (1800 секунд)
            print(f"🕒 Проверка новостей в {datetime.now()}")
            send_news_to_channel()
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(300)  # Ждем 5 минут при ошибке
