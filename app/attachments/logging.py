import logging

from .content import redact_image_payloads


class ImagePayloadFilter(logging.Filter):
    """Redact provider payload arguments before logging formats them."""

    def filter(self, record):
        record.msg = redact_image_payloads(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_image_payloads(value) for value in record.args)
        elif record.args:
            record.args = redact_image_payloads(record.args)
        return True
