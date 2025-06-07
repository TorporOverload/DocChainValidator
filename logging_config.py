import logging
import os

LOG_PATH = "data/logs"

def setup_logging():
    """Sets up the logging configuration for the application."""

    # Create logs directory if it doesn't exist
    os.makedirs(LOG_PATH, exist_ok=True)

    # set up the root logger. This will capture all logs from all loggers.
    # It will also allow us to control the log level and handlers globally.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Create a console handler for user-facing output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING) # Only show WARNING and above on the console
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Creates a main application log file handler
    # captures INFO and above from ALL loggers to file
    app_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "app.log"))
    app_log_handler.setLevel(logging.INFO)
    app_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app_log_handler.setFormatter(app_log_formatter)
    root_logger.addHandler(app_log_handler)

    # Creates a dedicated network log file handler
    # captures DEBUG and above, but only for the 'network' logger
    network_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "network.log"))
    network_log_handler.setLevel(logging.DEBUG)
    network_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    network_log_handler.setFormatter(network_log_formatter)
    
    # Attach this handler ONLY to the 'network' logger
    network_logger = logging.getLogger("network")
    network_logger.addHandler(network_log_handler)
    network_logger.propagate = False 

    # 5. Create a dedicated blockchain log file handler
    blockchain_log_handler = logging.FileHandler(os.path.join(LOG_PATH, "blockchain.log"))
    blockchain_log_handler.setLevel(logging.DEBUG)
    blockchain_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    blockchain_log_handler.setFormatter(blockchain_log_formatter)

    blockchain_logger = logging.getLogger("blockchain")
    blockchain_logger.addHandler(blockchain_log_handler)
    blockchain_logger.propagate = False

    # Mining worker file handler
    mining_log_path = os.path.join(LOG_PATH, "mining_worker.log")
    mining_handler = logging.FileHandler(mining_log_path, encoding="utf-8")
    mining_handler.setLevel(logging.INFO)
    mining_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    mining_handler.setFormatter(mining_formatter)

    # Get or create mining_worker logger
    mining_logger = logging.getLogger("mining_worker")
    mining_logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(mining_log_path) for h in mining_logger.handlers):
        mining_logger.addHandler(mining_handler)
