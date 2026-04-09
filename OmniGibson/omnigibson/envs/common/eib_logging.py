import logging
import os


def make_episode_logger(log_path):
    """Create a logger that writes to both a file and stdout."""
    logger = logging.getLogger(f"episode.{os.path.basename(log_path)}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, mode="w")
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(sh)
    return logger
