# logging_setup.py
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def setup_logger():
    logger = logging.getLogger("polymarket_bot")
    logger.setLevel(logging.INFO)  # or DEBUG when needed

    if logger.handlers:  # avoid adding handlers twice
        return logger

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
    ch.setFormatter(ch_formatter)

    # Rotating file handler (1 file per day, keep 7 days)
    fh = TimedRotatingFileHandler(
        LOG_DIR / "bot.log", when="midnight", backupCount=7, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] "
        " %(message)s"
    )
    fh.setFormatter(fh_formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger
