class EndpointRequestException(Exception):
    """Исключение при сбое запроса к эндпоинту API."""


class ApiResponseKeys(Exception):
    """Исключение при отсутствии ожидаемых ключей в ответе API."""


class UnknownStatusException(Exception):
    """Исключение при не известном статусе работы."""


class EnvironmentVariablesException(Exception):
    """Исключение при отсутствии переменных окружения."""
