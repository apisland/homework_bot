class HTTPStatusCodeError(Exception):
    """Пользовательское исключение."""

    def __init__(self, status_code) -> None:
        """."""
        super().__init__(status_code)
        self.status_code = status_code

    def __str__(self) -> str:
        """Сообщение об ошибке."""
        return f'Ошибка {self.status_code}'
