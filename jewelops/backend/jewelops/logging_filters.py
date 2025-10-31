import logging

class EnsureExtraFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # If the log call didn't include extra={...}, record won't have .extra
        if not hasattr(record, "extra"):
            record.extra = {}
        return True