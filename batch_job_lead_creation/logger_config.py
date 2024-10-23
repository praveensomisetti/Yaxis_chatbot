import logging
from logging import Logger

def setup_logger() -> Logger:
    """
    Set up and configure the application logger.

    This function creates a logger instance, configures it to output DEBUG level logs, and sets up
    a console handler to display log messages. The log format includes the timestamp, logger name,
    log level, and message.

    Returns:
        Logger: Configured logger instance.
    """
    # Create or get the logger instance
    logger = logging.getLogger("yaxis_chatbot")

    # Set the logging level to DEBUG
    logger.setLevel(logging.DEBUG)

    # Create a console handler to output logs to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Define the logging format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger if it doesn't already have handlers
    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger


# Initialize the logger instance
logger = setup_logger()