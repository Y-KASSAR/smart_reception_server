import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_dir:str= "logs" , log_level: str = "DEBUG") -> None:
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger("smart_reception")
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

    if logger.handlers:
        return

    file_handler =RotatingFileHandler(
        filename= log_path/ "smart_reception.log",
        maxBytes=10*1024*1024, #10 MB
        backupCount= 30,
        encoding="utf-8"
        )

    file_handler.setLevel(logging.DEBUG)

    console_handler =logging.StreamHandler()
    console_handler.setLevel(logging.INFO)


    formatter = logging.Formatter(
        " %(asctime)s|%(name)s|%(levelname)-8s|%(module)s:%(lineno)d|%(message)s",
        datefmt=" %Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging system initialized")

def get_logger(module_name:str)-> logging.Logger:

    return logging.getLogger(f"smart_reception.{module_name}")