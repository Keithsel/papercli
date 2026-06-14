import logging
from papercli.db import DEFAULT_DB

logger = logging.getLogger("papercli")


def setup_logging() -> None:
    log_dir = DEFAULT_DB.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "papers.log"

    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.propagate = False
