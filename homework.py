import os
import time
import logging

import requests
from telegram import Bot
from telegram.error import BadRequest
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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    env_vars = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(env_vars)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Bot sent message to Telegram')
    except BadRequest as error:
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

    if response.status_code != 200:
        message = (
            f'Endpoint {ENDPOINT} unavailable. '
            f'Status code: {response.status_code}'
        )
        raise ConnectionError(message)

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        message = 'The data must be of the dict type'
        raise TypeError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'The data must be of the list type'
        raise TypeError(message)
    if not response.get('homeworks'):
        message = 'The "homework" key not found'
        raise KeyError(message)
    if not response.get('current_date'):
        message = 'The "current_date" key not found'
        raise KeyError(message)
    if response.get('current_date') is None:
        message = 'The "current_date" value not found'
        raise ValueError(message)
    if not isinstance(response.get('current_date'), int):
        message = 'The data must be of the int type'
        raise TypeError(message)

    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус из информации о конкретной домашней работы."""
    if 'homework_name' not in homework:
        message = 'The "homework_name" is missing'
        raise KeyError(message)
    if 'status' not in homework:
        message = 'The "status" is missing'
        raise KeyError(message)
    if homework.get('status') not in HOMEWORK_VERDICTS:
        message = 'Status unknown or missing'
        raise ValueError(message)

    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[homework.get('status')]

    return (
        'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Required environment variables are missing')
        SystemExit()

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = {'from_date': int(time.time())}
    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message is not previous_message:
                    send_message(bot, message)
                    timestamp = {'from_date': response.get('current_date')}
                    previous_message = message
            else:
                logging.debug('Status not updated')

        except Exception as error:
            msg = f'Сбой в работе программы: {error}'
            print(msg)
            logging.error(msg)
            send_message(bot, msg)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    logging.basicConfig(
        filename='homework.log',
        filemode='w',
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
    )

    main()
