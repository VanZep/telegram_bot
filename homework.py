import os
import time
import logging

import requests
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    filename='homework.log',
    filemode='w',
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not bool(PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        logging.critical('Required environment variables are missing')
        SystemExit()


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Bot sent message to Telegram')
    except Exception as error:
        logging.error(f'Error "{error}" when sending a message to Telegram')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )
    except requests.RequestException as error:
        message = f'Error when requesting the API: {error}'
        logging.error(message)

    if response.status_code != 200:
        message = (
            f'Endpoint {ENDPOINT} unavailable. '
            f'Status code: {response.status_code}'
        )
        logging.error(message)
        raise AssertionError(message)

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        message = 'The data must be of the dict type'
        logging.error(message)
        raise TypeError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'The data must be of the list type'
        logging.error(message)
        raise TypeError(message)
    if response.get('homeworks') is None:
        message = 'The "homework" key not found'
        logging.error(message)
        raise KeyError(message)
    if response.get('current_date') is None:
        message = 'The "current_date" key not found'
        logging.error(message)
        raise KeyError(message)

    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус из информации о конкретной домашней работы."""
    if 'homework_name' not in homework:
        message = 'The name of the homework is missing'
        logging.error(message)
        raise KeyError(message)
    if homework.get('status') not in HOMEWORK_VERDICTS:
        message = 'Status unknown or missing'
        logging.error(message)
        raise ValueError(message)

    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[homework.get('status')]

    return (
        'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = {'from_date': int(time.time())}

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logging.debug('Status not updated')

            timestamp = {'from_date': response.get('current_date')}

        except Exception as error:
            msg = f'Сбой в работе программы: {error}'
            logging.error(msg)
            send_message(bot, msg)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
