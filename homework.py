import logging
import os
import sys
import time
from datetime import datetime
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from telegram.error import NetworkError, TelegramError, TimedOut

import exceptions as ex

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 300
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    # handlers=[logging.FileHandler('bot.log', 'w', 'utf-8')]
)
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет сообщение в TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info('Сообщение отправлено в чат')
    except TimedOut:
        logger.warning('Тайм-аут при отправке сообщения в чат')
    except NetworkError:
        logger.warning('Сетевая ошибка при доступе к серверу телеграм')
        time.sleep(RETRY_TIME / 2)
    except TelegramError as e:
        if "Invalid server response" in str(e):
            logger.error('Сервер выдал неверный ответ')
            time.sleep(RETRY_TIME / 2)
        else:
            raise e


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API. Возвращает ответ API в dict."""
    logger.info('Запрос к эндпоинту API')
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            raise ex.EndpointRequestException('Эндпоинт не доступен"')
        try:
            response = response.json()
        except JSONDecodeError:
            logger.error('Ответ сервера не преобразовался в json')
            raise JSONDecodeError('Ответ сервера не преобразовался в json')
        logger.info(f'Ответ API получен: {response}')
        return response
    except RequestException as e:
        logger.error(e)
        raise SystemExit(e)


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверка ответа API')
    if not response:
        message = 'Сервер вернул пустой массив данных'
        logger.error(message)
        raise Exception(message)
    if not isinstance(response['homeworks'], list):
        message = 'Неправильный тип данных в ответе API'
        logger.error(message)
        raise TypeError(message)
    if not isinstance(response, dict):
        message = 'Неправильный тип данных '
        + 'полученных в ответе API'
        logger.error(message)
        raise TypeError(message)
    else:
        return response['homeworks'][0]


def parse_status(homework):
    """Извлекает из ответа API (словарь) статус и название работы."""
    logger.info('Извлечение информации о работе')
    if isinstance(homework, dict):
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        try:
            verdict = HOMEWORK_STATUSES[homework_status]
        except KeyError:
            massage = 'Неизвестный статус работы'
            logger.error(massage)
            raise KeyError(massage)
        logger.info('Информация о работе получена')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise KeyError('Невозможно извлечь информацию из ответа API')


def check_tokens():
    """Проверка доступности переменных окружения."""
    logger.info('Старт проверки доступности переменных')
    if all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.info('Переменные доступны')
        return True
    else:
        logger.critical('Переменные не доступны')
        return False


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 1
    # int(time.time()) or 1666299600
    last_timestamp = current_timestamp
    error_last = {}

    while True:
        try:
            if check_tokens():
                response = get_api_answer(current_timestamp)
                if not response.get('homeworks'):
                    current_timestamp = int(time.time())
                    logger.info(f'Статус работы '
                                f'c {last_timestamp} не изменился')
                    time.sleep(RETRY_TIME)
                    continue
                date_updated = response['homeworks'][0].get('date_updated')
                last_timestamp = datetime.strptime(
                    date_updated, '%Y-%m-%dT%H:%M:%SZ'
                ).strftime('%Y-%m-%d %H:%M:%S')
                check = check_response(response)
                message = parse_status(check)
                send_message(bot, message)
                current_timestamp = response.get('current_date')
                time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            if message != error_last.get('last_error_message'):
                error_last['last_error_message'] = message
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
