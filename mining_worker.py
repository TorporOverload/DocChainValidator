import queue
import threading
import time
import logging
from typing import Any
from logging_config import setup_logging
setup_logging()
mining_logger = logging.getLogger("mining_worker")

class BlockMiningWorker:
    """
    Manages a background thread for mining blocks and adding them to the blockchain.
    """
    def __init__(self, blockchain_instance: Any) -> None:
        self.blockchain = blockchain_instance
        self.task_queue: queue.Queue[tuple[Any, Any]] = queue.Queue()
        self.working: bool = False  # True if there are tasks or a task is being processed
        self.thread: threading.Thread = threading.Thread(target=self._worker_loop, daemon=True)
        mining_logger.info("Starting mining worker thread.")
        self.thread.start()
        
    def add_block_task(self, data: Any, signature: Any) -> None:
        """Add a block to the mining queue."""
        self.task_queue.put((data, signature))
        self.working = True  # Signal that there's work to do
        mining_logger.info(f"Block mining task added to queue. Queue size: {self.task_queue.qsize()}")
        
    def wait_for_completion(self) -> None:
        """Wait for all mining tasks to complete."""
        mining_logger.info("Waiting for all mining tasks to complete...")
        while not self.task_queue.empty() or self.working:
            mining_logger.debug(f"Waiting... Queue size: {self.task_queue.qsize()}, Working: {self.working}")
            time.sleep(0.1)
        mining_logger.info("All mining tasks completed.")
            
    def _worker_loop(self) -> None:
        """Main worker loop for mining blocks."""
        while True:
            try:
                # Wait for a task.
                data, signature = self.task_queue.get(timeout=1)
                self.working = True
                mining_logger.info("Mining worker picked up a new task from the queue.")
                mining_logger.debug(f"Mining data: {data}, signature: {signature}")
                try:
                    self.blockchain.add_block(data=data, signature=signature)
                    mining_logger.info("Block successfully mined and added to blockchain.")
                except Exception as e:
                    mining_logger.error(f"Error while mining/adding block: {e}")
                self.task_queue.task_done()
                if self.task_queue.empty():
                    self.working = False
                    mining_logger.info("Mining worker queue is now empty. Worker is idle.")
                else:
                    mining_logger.debug(f"Mining worker queue size after task: {self.task_queue.qsize()}")
            except queue.Empty:
                if self.task_queue.empty():
                    if self.working:
                        mining_logger.info("Mining worker found queue empty. Worker is idle.")
                    self.working = False
                continue
            except Exception as e:
                mining_logger.error(f"Unexpected error in mining worker: {e}")
                self.working = False