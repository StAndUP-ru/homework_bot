import logging
import os
import sys
import time
from datetime import datetime

import requests
import telegram
from dotenv import load_dotenv

import exceptions as ex

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
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
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в чат: {error}')


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
        if response.status_code != 200:
            raise ex.EndpointRequestException('Эндпоинт не доступен"')
        response = response.json()
        logger.info(f'Ответ API получен: {response}')
        return response
    except Exception:
        raise ex.EndpointRequestException('Ошибка при запросе к API')


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверка ответа API')
    homeworks = response['homeworks'][0]
    if isinstance(homeworks, dict):
        return homeworks
    elif not isinstance(homeworks, dict):
        logger.error('Тип запроса не список')
        raise TypeError('Тип запроса не список')
    else:
        logger.error('Отсутствие ожидаемых ключей в ответе API')
        raise ex.ApiResponseKeys('Отсутствие ожидаемых'
                                 + 'ключей в ответе API')


def parse_status(homework):
    """Извлекает и статус и название работы."""
    logger.info('Извлечение информации о работе')
    try:
        homework_name = homework.get('homework_name')
    except Exception:
        massage = 'Не указано название урока'
        logger.error(massage)
        raise KeyError(massage)
    try:
        homework_status = homework.get('status')
    except Exception:
        massage = 'Не указано статуса работы'
        logger.error(massage)
        raise KeyError(massage)
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except Exception:
        massage = 'Не известный статус работы'
        logger.error(massage)
        raise ex.UnknownStatusException(massage)
    logger.info('Получен статус работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


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
                if response.get('homeworks') == []:
                    current_timestamp = int(time.time())
                    logger.info(f'Статус работы '
                                f'c {last_timestamp} не изменился')
                    time.sleep(RETRY_TIME)
                    continue
                if response.get('homeworks') != []:
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
