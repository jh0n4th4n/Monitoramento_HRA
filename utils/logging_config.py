# utils/logging_config.py

import logging
import os

def configurar_logging():
    logger = logging.getLogger("monitoramento")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    os.makedirs("logs", exist_ok=True)

    fh = logging.FileHandler("logs/app.log", encoding="utf-8")
    ch = logging.StreamHandler()

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
