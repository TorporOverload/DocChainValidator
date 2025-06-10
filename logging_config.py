import logging
import os

LOG_PATH = "data/logs"

def setup_logging():
    """Sets up the logging configuration for the application."""

    # Create logs directory if it doesn't exist
    os.makedirs(LOG_PATH, exist_ok=True)

    # Clear all existing handlers to prevent duplication
    logging.getLogger().handlers.clear()

    # set up the root logger for console output only
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Create a console handler for user-facing output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only show WARNING and above on the console
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # App log will be for unexpected errors and misc logs not caught by specific loggers
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    
    app_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "app.log"))
    app_log_handler.setLevel(logging.INFO)
    app_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app_log_handler.setFormatter(app_log_formatter)
    app_logger.addHandler(app_log_handler)

    # Creates a dedicated network log file handler
    # captures DEBUG and above, but only for the 'network' logger
    network_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "network.log"))
    network_log_handler.setLevel(logging.DEBUG)
    network_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    network_log_handler.setFormatter(network_log_formatter)
      # Attach this handler ONLY to the 'network' logger
    network_logger = logging.getLogger("network")
    network_logger.setLevel(logging.DEBUG)
    network_logger.handlers.clear()  # Clear any existing handlers
    network_logger.addHandler(network_log_handler)
    network_logger.propagate = False 

    # Create a dedicated blockchain log file handler
    blockchain_logger = logging.getLogger("blockchain")
    blockchain_logger.setLevel(logging.INFO)
    blockchain_logger.handlers.clear()  # Clear any existing handlers
    
    blockchain_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "blockchain.log"))
    blockchain_log_handler.setLevel(logging.INFO)
    blockchain_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    blockchain_log_handler.setFormatter(blockchain_log_formatter)
    blockchain_logger.addHandler(blockchain_log_handler)
    blockchain_logger.propagate = False

    # Mining worker file handler
    mining_log_path = os.path.join(LOG_PATH, "mining_worker.log")
    mining_handler = logging.FileHandler(mining_log_path, encoding="utf-8")
    mining_handler.setLevel(logging.INFO)
    mining_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    mining_handler.setFormatter(mining_formatter)    # Set up mining_worker logger
    mining_logger = logging.getLogger("mining_worker")
    mining_logger.setLevel(logging.INFO)
    mining_logger.handlers.clear()  # Clear any existing handlers
    mining_logger.addHandler(mining_handler)
    mining_logger.propagate = False  # Prevent propagation to root logger
