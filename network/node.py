"""Main blockchain node implementation."""
import hashlib
import threading
import socket
import time
from typing import Any, Optional
from blockchain import Blockchain
from block import Block
from mining_worker import BlockMiningWorker

from .config import logger, CHUNK_SIZE, MAX_BLOCKS, SOCKET_TIMEOUT, MINING_LOCK_TIMEOUT
from .connection import ConnectionManager
from .protocol import send_message, receive_message
from .sync import handle_blocks


class BlockchainNode:
    """P2P node implementation for the blockchain network."""
    def __init__(self, host: str, port: int, blockchain: Blockchain, mining_worker: BlockMiningWorker):
        """Initialize a blockchain node.
        
        Args:
            host: The host to bind to
            port: The port to listen on
            blockchain: The blockchain instance to use
        """
        logger.info(f"Initializing blockchain node on {host}:{port}")
        self.host = host
        self.port = port
        self.blockchain = blockchain
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.protocol_version = 1
        self.mining_worker = mining_worker
        # Generate peer_id from host:port
        self.peer_id = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()
        
        try:
            # Initialize connection manager
            self.connection_manager = ConnectionManager(self)
            if not self.connection_manager:
                raise RuntimeError("Connection manager initialization failed")
        except Exception as e:
            logger.error(f"Failed to initialize connection manager: {e}")
            raise RuntimeError("Connection manager initialization failed") from e
        
    def start(self) -> None:
        """Start the blockchain node server"""
        logger.info(f"Starting node on {self.host}:{self.port}")        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(SOCKET_TIMEOUT)  # Add timeout to server socket
            
            # Test if port is available
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((self.host, self.port))
            test_socket.close()
            
            if result == 0:
                raise Exception(f"Port {self.port} is already in use")
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            logger.info(f"Node binding successful on {self.host}:{self.port}")
            
            # Set running flag before starting threads
            self.running = True
            
            # Start network threads in order of dependency
            threading.Thread(target=self._listen_for_connections, daemon=True).start()
            logger.info("Started connection listener thread")
            
            threading.Thread(target=self.connection_manager.ping_peers, daemon=True).start()
            logger.info("Started peer ping thread")
            
            threading.Thread(target=self.connection_manager.retry_connections, daemon=True).start()
            logger.info("Started connection retry thread")
            
            # Initialize peer connections after node is fully set up
            self.connection_manager.initialize_connections()
            
            logger.info(f"Node fully started and initialized on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            raise
        
    def stop(self) -> None:
        """Stop the blockchain node server"""
        logger.info("Stopping blockchain node")
        self.running = False  # Signal threads to stop
        
        # Close server socket first to stop accepting new connections
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")
        
        # Save state and close existing connections
        try:
            self.connection_manager.close_all_connections()
            self.connection_manager.save_peers()
        except Exception as e:
            logger.error(f"Error during connection cleanup: {e}")
        
        logger.info("Node stopped successfully")

    def _listen_for_connections(self) -> None:
        """Listen for incoming peer connections"""
        logger.info("Starting connection listener")
        while self.running:
            try:
                client_sock: socket.socket
                addr: tuple[str, int]
                client_sock, addr = self.server_socket.accept()
                logger.info(f"New incoming connection from {addr}")
                threading.Thread(
                    target=self.connection_manager.handle_new_connection,
                    args=(client_sock, addr),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")

    def broadcast_new_block(self, block: Block) -> None:
        """Broadcast a new block to all peers"""
        logger.info(f"Broadcasting new block {block.current_hash[:8]}...")
        message: dict[str, Any] = {
            "type": "NEW_BLOCK",
            "payload": {
                "block": block.to_dict()
            }
        }
        self.connection_manager.broadcast_to_peers(message)

    def get_network_stats(self) -> dict[str, Any]:
        """Get current network statistics"""
        stats: dict[str, Any] = {
            "peer_count": len(self.connection_manager.connected_sockets),
            "chain_height": len(self.blockchain.chain),
            "latest_block_hash": self.blockchain.get_latest_block().current_hash,
            "known_peers": len(self.connection_manager.peers),
            "pending_retries": len(self.connection_manager.connection_retries)
        }
        logger.debug(f"Network stats: {stats}")
        return stats
    
    def broadcast_mining_start(self) -> None:
        """Broadcasts that this node has acquired the mining lock."""
        logger.info("Broadcasting MINING_START to peers.")
        message: dict[str, Any] = {"type": "MINING_START", "payload": {}}
        self.connection_manager.broadcast_to_peers(message)

    def broadcast_mining_finish(self) -> None:
        """Broadcasts that this node has finished mining and released the lock."""
        logger.info("Broadcasting MINING_FINISH to peers.")
        message: dict[str, Any] = {"type": "MINING_FINISH", "payload": {}}
        self.connection_manager.broadcast_to_peers(message)

    def request_mining_lock(self) -> bool:
        """Attempts to acquire the network-wide mining lock for this node."""
        with self.connection_manager.network_mining_lock:
            if self.connection_manager.network_mining_in_progress:
                # Lock is already held
                logger.debug(f"Could not acquire mining lock, currently held by peer {self.connection_manager.mining_lock_peer_id[:8]}")
                return False
            
            # Acquire lock for this node
            self.connection_manager.network_mining_in_progress = True
            self.connection_manager.mining_lock_peer_id = self.peer_id
            
            # long-duration timer as a failsafe
            if self.connection_manager.mining_lock_timer:
                self.connection_manager.mining_lock_timer.cancel()
            
            self.connection_manager.mining_lock_timer = threading.Timer(
                MINING_LOCK_TIMEOUT, 
                self.connection_manager.release_mining_lock
            )
            self.connection_manager.mining_lock_timer.start()
            
            # Announce to the network
            self.broadcast_mining_start()
            logger.info(f"Successfully acquired network mining lock with a {MINING_LOCK_TIMEOUT}s timeout.")
            return True

    def _handle_peer_connection(self, sock: socket.socket, peer_id: str) -> None:
        """Handle messages from a connected peer."""
        logger.info(f"Starting message handler for peer {peer_id}")
        self.connection_manager.update_connection_state(peer_id, 'connected')
        
        try:
            while self.running:
                try:
                    message = receive_message(sock)
                    msg_type = message.get('type', '').lower()
                    payload = message.get('payload', {})
                    
                    if peer_id not in self.connection_manager.connected_sockets:
                        logger.warning(f"Peer {peer_id} no longer in connected_sockets during message processing.")
                        return

                    if msg_type == 'ping':
                        with self.blockchain.lock:
                            latest_block = self.blockchain.get_latest_block()
                            chain_height = len(self.blockchain.chain)
                            latest_hash = latest_block.current_hash if latest_block else "0"
                        response = {
                            'type': 'PONG',
                            'payload': {
                                'chain_height': chain_height,
                                'latest_hash': latest_hash
                            }
                        }
                        send_message(sock, response)
                    elif msg_type == 'get_blocks':
                        self._handle_get_blocks(sock, payload, peer_id)
                    elif msg_type == 'blocks':
                        handle_blocks(sock, self.blockchain, payload, peer_id)
                    elif msg_type == 'new_block':
                        self.handle_new_block(payload, peer_id, self.connection_manager.broadcast_to_peers)
                    elif msg_type == 'mining_start':
                        self.connection_manager.acquire_mining_lock_from_peer(peer_id)
                    elif msg_type == 'mining_finish':
                        self.connection_manager.handle_mining_finish(peer_id)
                    elif msg_type == 'pong':
                        logger.debug(f"Received PONG from {peer_id[:8]}")
                        with self.blockchain.lock:
                            our_height = len(self.blockchain.chain)
                            latest_block = self.blockchain.get_latest_block()
                            our_hash = latest_block.current_hash if latest_block else "0"
                            
                        peer_height = payload.get("chain_height", 0)
                        peer_hash = payload.get("latest_hash", "")
                        
                        # Only trigger sync if not already in progress
                        if not self.connection_manager.sync_in_progress:
                            # Scenario 1: Peer has a longer chain.
                            if peer_height > our_height:
                                logger.info(f"PONG from {peer_id[:8]} shows they have a longer chain. Requesting sync.")
                                self.connection_manager._initiate_sync_if_needed(sock, peer_id, peer_height)
                                # Scenario 2: Same height, but different blocks
                            elif peer_height == our_height and peer_hash != our_hash:
                                logger.info(f"PONG from {peer_id[:8]} shows a fork at the same height. Requesting sync.")
                                self.connection_manager._initiate_sync_if_needed(sock, peer_id, peer_height)
                        else:
                            logger.info(f"Sync already in progress. Ignoring PONG-triggered sync for peer {peer_id[:8]}")
                    else:
                        if msg_type:
                            logger.warning(f"Unknown message type '{msg_type}' from peer {peer_id}")
                except socket.timeout:
                    if not self.running:
                        break
                    continue
                except (ConnectionError, IOError, OSError) as e:
                    logger.error(f"Connection error with peer {peer_id} in handler: {e}")
                    break
                except UnicodeDecodeError as e:
                    logger.error(f"UnicodeDecodeError from peer {peer_id}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error handling message from peer {peer_id}: {e}")
                    break
                        
        except Exception as e:
            logger.error(f"Outer connection handler failed for peer {peer_id}: {e}")
        finally:
            self.connection_manager.disconnect_peer(peer_id)

    def _handle_get_blocks(self, sock: socket.socket, payload: dict[str, Any], peer_id: str) -> None:
        """Handle request for blocks."""
        try:
            start_height: int = payload.get('start', 0)
            end_height: int = min(
                start_height + CHUNK_SIZE,
                start_height + MAX_BLOCKS,
                len(self.blockchain.chain)
            )
            with self.blockchain.lock:
                blocks: list[dict[str, Any]] = [
                    block.to_dict() 
                    for block in self.blockchain.chain[start_height:end_height]
                ]
            if blocks:
                send_message(sock, {
                    'type': 'blocks',
                    'payload': {'blocks': blocks}
                })
                logger.info(f"Sent blocks {start_height} to {end_height} to peer {peer_id}")
        except Exception as e:
            logger.error(f"Error handling get_blocks from peer {peer_id}: {str(e)}")

    def connect_to_peer(self, host: str, port: int) -> bool:
        """Connect to a peer node.
        
        Args:
            host: The host to connect to
            port: The port to connect to
        Returns:
            bool: True if connection was successful, False otherwise
        """
        return self.connection_manager.connect_to_peer(host, port)

    @staticmethod
    def hash_peer_id(host: str, port: int) -> str:
        """Generate a unique peer ID from host and port."""
        return hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:16]
    
    def request_complete_chain(self, peer_id: str) -> None:
        """Request the complete blockchain from a peer."""
        if peer_id not in self.connection_manager.connected_sockets:
            logger.error(f"Cannot request complete chain from {peer_id}: not connected")
            return
        
        sock = self.connection_manager.connected_sockets[peer_id]
        request = {
            "type": "GET_BLOCKS",
            "payload": {"start": 0}
        }
        send_message(sock, request)
        logger.info(f"Requested complete chain from peer {peer_id[:8]}")
        
    def handle_new_block(self, payload: dict[str, Any], peer_id: str, broadcast_to_peers: Any) -> None:
        """Handle a new single block announcement from a peer."""
        if not isinstance(payload, dict) or 'block' not in payload:
            logger.error(f"Invalid new block payload from peer {peer_id}")
            return

        block_dict = payload.get('block')
       
        if any(b.current_hash == block_dict.get('current_hash') for b in self.blockchain.chain):
            return

        try:
            new_block = Block.from_dict(block_dict)
            if self.blockchain.is_new_block_valid(new_block, self.blockchain.get_latest_block()):
                logger.info(f"Valid new block #{new_block.index} received. Interrupting local mining if active.")
                
                try:
                    if hasattr(self, 'mining_worker') and self.mining_worker:
                        self.mining_worker.interrupt_current_task()
                except Exception as e:
                    logger.error(f"Error interrupting mining worker: {e}")
                
                self.blockchain.chain.append(new_block)
                self.blockchain.add_block_to_index(new_block)
                self.blockchain.save_chain()
                logger.info(f"Accepted and added new block #{new_block.index} from peer {peer_id}")
                broadcast_to_peers({'type': 'NEW_BLOCK', 'payload': {'block': block_dict}}, exclude_peer=peer_id)
        except Exception as e:
            logger.error(f"Error processing new block from peer {peer_id}: {str(e)}")