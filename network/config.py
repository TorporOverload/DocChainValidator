"""Network configuration and constants."""
import os
from logging_config import logging


logger: 'logging.Logger' = logging.getLogger("network")


PEERS_FILE: str = os.path.join("data", "network", "peers.json")
SOCKET_TIMEOUT: int = 30
PING_INTERVAL: int = 25
RETRY_INTERVAL: int = 60
CHUNK_SIZE: int = 50
MAX_BLOCKS: int = 1000
MAGIC_NUMBER: bytes = b"6022h@1nV@116@t0r"
MAGIC_NUMBER_LEN: int = len(MAGIC_NUMBER)
LENGTH_PREFIX_LEN: int = 4
MAX_ALLOWED_PAYLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB size
MAX_REWIND_DEPTH = 2000
MAX_RETRIES = 3  
RETRY_DELAY = 120 
MINING_LOCK_TIMEOUT: int = 600