import logging
import os
import sys
import time
import requests
from http import HTTPStatus

from telegram import Bot
from telegram.ext import Updater

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[logging.FileHandler('main.log',
                                  encoding='utf-8', mode='w'),
              logging.StreamHandler(sys.stdout)])

PRACTICUM_TOKEN = os.getenv('PRAKTIKUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщений от бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logging.error('Ошибка отправки в чат {TELEGRAM_CHAT_ID}: {message}')


def get_api_answer(current_timestamp):
    """делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=params)
    except Exception as e:
        logging.error(f'Сбой в работе программы: Я.Практикум недоступен: {e}')
        send_message(f'Сбой в работе программы: Я.Практикум недоступен: {e}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except requests.JSONDecodeError:
        logging.error('Сервер вернул невалидный json')
        send_message('Сервер вернул невалидный json')


def check_response(response):
    """проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ
    (он может быть и пустым), доступный
    в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        raise TypeError('Некорректный ответ API')
    try:
        works_list = response['homeworks']
    except KeyError:
        logging.error('Ошибка по ключу homeworks')
        raise KeyError('Ошибка по ключу homeworks')
    try:
        work = works_list[0]
    except IndexError:
        logging.error('В списке нет работ')
        raise IndexError('В списке нет работ')
    return work


def parse_status(homework):
    """извлекает из информации о конкретной домашней работе.
    статус этой работы. В качестве параметра функция
    получает только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Статус работы "homework_name" неверный')
    if 'status' not in homework:
        raise KeyError('Статус работы "status" неверный')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = ''
    if homework_status is None:
        logging.error(f'Статус работы {homework_status} неверный')
        raise KeyError(f'Статус работы {homework_status} неверный')
    elif homework_status == 'reviewing':
        verdict = 'Работа взята на проверку ревьюером.'
    elif homework_status == 'rejected':
        verdict = 'Работа проверена: у ревьюера есть замечания.'
    elif homework_status == 'approved':
        verdict = 'Работа проверена: ревьюеру всё понравилось. Ура!'
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """проверяет доступность переменных окружения.
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная
    окружения — функция должна вернуть False, иначе — True.
    """
    tokens = [PRACTICUM_TOKEN,
              TELEGRAM_TOKEN,
              TELEGRAM_CHAT_ID]
    for i in tokens:
        if i is None:
            logging.critical(f'Отсутствует обязательная'
                             f'переменная окружения: {i}'
                             f'Программа принудительно остановлена.')
            return False
    return True


def main():
    """Основная логика работы бота."""
    updater = Updater(token=TELEGRAM_TOKEN)
    updater.start_polling()
    updater.idle()
    logging.debug('бот включился')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response.get('homeworks'):
                send_message(parse_status(response.get('homeworks')[0]))
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
