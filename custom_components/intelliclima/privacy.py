"""Prevent the published client's account/URL/frame logs from reaching handlers."""

import logging


class ClientPrivacyFilter(logging.Filter):
    """Drop verbose records and retain only generic warning/error messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.WARNING:
            return False
        record.msg = "IntelliClima client error details withheld for privacy"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def install_client_privacy_filter() -> None:
    """Install once on the exact emitter used by pyintelliclima 0.5.0."""
    logger = logging.getLogger("pyintelliclima.api")
    if not any(isinstance(item, ClientPrivacyFilter) for item in logger.filters):
        logger.addFilter(ClientPrivacyFilter())
