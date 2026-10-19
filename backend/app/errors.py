"""Errors that main.py turns into HTTP responses with a readable message."""


class ServiceUnavailable(Exception):
    """A feature is not configured or a dependency is down. Answers 503 with `message`."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
