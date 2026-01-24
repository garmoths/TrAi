import logging

from utils import logger as mylogger


def test_get_logger_and_setup(tmp_path):
    # Ensure setup_logging populates handlers
    mylogger.setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.handlers

    lg = mylogger.get_logger("tests.logger")
    assert isinstance(lg, logging.Logger)
