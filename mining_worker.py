import queue
import threading
import time
import logging
from typing import Any
from logging_config import setup_logging
setup_logging()
from blockchain import Blockchain
mining_logger = logging.getLogger("mining_worker")

class BlockMiningWorker:
    """
    Manages a background thread for mining blocks and adding them to the blockchain.
    """
    def __init__(self, blockchain_instance: Blockchain) -> None:
        self.blockchain = blockchain_instance
        self.task_queue: queue.Queue[tuple[Any, Any]] = queue.Queue()
        self.working: bool = False
        self.stop_current_task = threading.Event()
        self.thread: threading.Thread = threading.Thread(target=self._worker_loop, daemon=True)
        mining_logger.info("Starting mining worker thread.")
        self.thread.start()
        
    def add_block_task(self, data: Any, signature: Any) -> None:
        """Add a block to the mining queue."""
        self.stop_current_task.clear()
        self.task_queue.put((data, signature))
        self.working = True
        mining_logger.info(f"Block mining task added to queue. Queue size: {self.task_queue.qsize()}")
        
    # RENAMED and MODIFIED: This no longer clears the queue.
    def interrupt_current_task(self) -> None:
        """Interrupts the current mining task, allowing it to be re-queued."""
        if self.working:
            mining_logger.warning("Interrupting current mining task.")
            self.stop_current_task.set() # Signal the PoW loop to stop
            
    def _worker_loop(self) -> None:
        """Main worker loop for mining blocks."""
        while True:
            try:
                data, signature = self.task_queue.get(timeout=1)
                self.working = True
                self.stop_current_task.clear()
                mining_logger.info("Mining worker picked up a new task from the queue.")
                try:
                    mined_block = self.blockchain.add_block(data=data, signature=signature, stop_event=self.stop_current_task)
                    
                    # NEW LOGIC: Check if mining was interrupted
                    if not mined_block and self.stop_current_task.is_set():
                        mining_logger.info("Mining was interrupted. Re-queueing task to try again later.")
                        # Put the task back in the queue
                        self.task_queue.put((data, signature))
                    elif mined_block:
                         mining_logger.info("Block successfully mined and added to blockchain.")

                except Exception as e:
                    mining_logger.error(f"Error while mining/adding block: {e}")
                
                self.task_queue.task_done()
                if self.task_queue.empty():
                    self.working = False
                    mining_logger.info("Mining worker queue is now empty. Worker is idle.")
            except queue.Empty:
                if self.working:
                    mining_logger.info("Mining worker found queue empty. Worker is idle.")
                self.working = False
                continue
            except Exception as e:
                mining_logger.error(f"Unexpected error in mining worker: {e}")
                self.working = False