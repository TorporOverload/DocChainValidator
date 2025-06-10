
import threading
import time
from queue import Queue, Empty
import logging
from blockchain import Blockchain

logger = logging.getLogger(__name__)

class BlockMiningWorker:
    """
     Manages a background thread for mining blocks and adding them to the blockchain.
    """
    def __init__(self, blockchain: Blockchain):
        """
        Initializes the BlockMiningWorker.

        Args:
            blockchain: The blockchain instance to which new blocks will be added.
        """
        self.blockchain = blockchain
        self.task_queue = Queue()
        self.working = False
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._mine_blocks, daemon=True)
        self._current_task_interrupt = threading.Event()
        
        # Start the worker thread
        self._worker_thread.start()
        logger.info("BlockMiningWorker initialized and thread started.")

    def add_document_task(self, tasks: list[dict]) -> None:
        """Adds a new document (a list of page-mining tasks) to the queue."""
        self.task_queue.put(tasks)
        logger.info(f"Added document task to queue. Queue size: {self.task_queue.qsize()}")

    def interrupt_current_task(self) -> None:
        """
        Signals the worker to interrupt the current mining task.
        This is typically called when a new block is received from the network.
        """
        if self.working:
            logger.info("Interrupting current mining task.")
            self._current_task_interrupt.set()

    def _mine_blocks(self) -> None:
        """
        The main loop for the mining worker thread.
        Continuously checks the queue for new document tasks and mines all their blocks.
        """
        while not self._stop_event.is_set():
            # First, check if the node is busy syncing the chain
            if (hasattr(self.blockchain, 'node') and
                self.blockchain.node and
                hasattr(self.blockchain.node, 'connection_manager') and
                self.blockchain.node.connection_manager.sync_in_progress):
                if self.working:
                    logger.info("Blockchain sync in progress. Pausing mining worker.")
                    self.working = False
                time.sleep(5)
                continue

            # Periodically check if the worker has tasks to process
            try:
                document_tasks = self.task_queue.get_nowait()
            except Empty:        
                time.sleep(1)
                continue
            
            # wait until the worker can get the network lock.
            logger.info("Task found in queue. Actively trying to acquire network mining lock...")
            lock_acquired = False
            while not lock_acquired and not self._stop_event.is_set():
                if hasattr(self.blockchain, 'node') and self.blockchain.node:
                    lock_acquired = self.blockchain.node.request_mining_lock()
                    if not lock_acquired:
                        time.sleep(5) # Wait for 5 seconds before retrying
                else: # Standalone mode
                    lock_acquired = True

            # If the node was stopped while waiting for the lock, re-queue the task and exit.
            if not lock_acquired:
                self.add_document_task(document_tasks)
                continue

            # Lock acquired, begin mining
            try:
                self.working = True
                self._current_task_interrupt.clear()
                
                doc_title = document_tasks[0]['data'].get('title', 'Unknown Document')
                logger.info(f"Lock acquired. Started mining document: '{doc_title}' with {len(document_tasks)} pages.")

                for i, task in enumerate(document_tasks):
                    if self._current_task_interrupt.is_set():
                        logger.warning("Mining task interrupted by network event.")
                        remaining_tasks = document_tasks[i:]
                        self.add_document_task(remaining_tasks)
                        break

                    newly_mined_block = self.blockchain.add_block(
                        data=task['data'], signature=task['signature'], stop_event=self._current_task_interrupt
                    )

                    if newly_mined_block is None:
                        logger.error(f"Failed to mine page {task['data'].get('page', i)} of document '{doc_title}'.")
                        if self._current_task_interrupt.is_set():
                            remaining_tasks = document_tasks[i:]
                            self.add_document_task(remaining_tasks)
                        break
            finally:
                self.working = False
                if lock_acquired and hasattr(self.blockchain, 'node') and self.blockchain.node:
                    with self.blockchain.node.connection_manager.network_mining_lock:
                        logger.info(f"Releasing and broadcasting finish for mining lock.")
                        self.blockchain.node.connection_manager.release_mining_lock()
                        self.blockchain.node.broadcast_mining_finish()
    
    def stop(self) -> None:
        """
        Stops the mining worker thread gracefully.
        """
        logger.info("Stopping mining worker...")
        self._stop_event.set()
        self._worker_thread.join()
        logger.info("Mining worker stopped.")