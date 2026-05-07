import logging
import sys
import io

def get_logger(name: str) -> logging.Logger:
    """
    Creates and configures a centralized structured logger.
    Forces UTF-8 output so emoji/unicode log messages work on Windows cp1252 terminals.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Wrap stdout in a UTF-8 writer — prevents UnicodeEncodeError on Windows
        utf8_stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
        handler = logging.StreamHandler(utf8_stdout)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
