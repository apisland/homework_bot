import logging
import os
import sys
import time
import requests
from http import HTTPStatus

from telegram import Bot, TelegramError

from exceptions import HTTPStatusCodeError

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[logging.FileHandler('main.log',
                                  encoding='utf-8', mode='w'),
              logging.StreamHandler(sys.stdout)])

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
N_SEC_WEEK = 604800
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
        logging.info(f'Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except TelegramError:
        logging.error(f'Ошибка отправки в чат {TELEGRAM_CHAT_ID}: {message}')


def get_api_answer(current_timestamp):
    """делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    params = {'from_date': current_timestamp}
    try:
        homework_units = requests.get(ENDPOINT, headers=HEADERS,
                                      params=params)
    except ConnectionError as e:
        logging.error(f'Сбой в работе программы: Я.Практикум недоступен: {e}')
    if homework_units.status_code != HTTPStatus.OK:
        logging.error(f'Ошибка {homework_units.status_code}')
        raise HTTPStatusCodeError
    try:
        return homework_units.json()
    except requests.JSONDecodeError:
        logging.error('Сервер вернул невалидный json')


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
        logging.error('Отсутсвует работа или список работ')
        raise IndexError('Отсутсвует работа или список работ')
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
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'Статус работы {homework_status} неверный')
        raise KeyError(f'Статус работы {homework_status} неверный')
    elif homework_status == 'reviewing':
        verdict = HOMEWORK_STATUSES.get('reviewing')
    elif homework_status == 'rejected':
        verdict = HOMEWORK_STATUSES.get('rejected')
    elif homework_status == 'approved':
        verdict = HOMEWORK_STATUSES.get('approved')
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
    for _ in tokens:
        if _ is None:
            logging.critical(f'Отсутствуют обязательные '
                             f'токены/переменные окружения: {_} '
                             f'Программа принудительно остановлена.')
            return False
    return True


def main():
    """Основная логика работы бота."""
    logging.debug('бот включился')

    if not check_tokens():
        logging.critical('Не обнаружены обязательные токены/переменные')
    else:
        check_tokens()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - N_SEC_WEEK
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response.get('homeworks'):
                send_message(bot, parse_status(response.get('homeworks')[0]))
            if 'current_date' not in response:
                raise KeyError('Текущая дата не обнаружена')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if response is None:
                send_message(bot, message)
        finally:
            return response


if __name__ == '__main__':
    main()
