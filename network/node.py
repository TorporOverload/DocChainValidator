"""Main blockchain node implementation."""
import hashlib
import threading
import socket
import time
from typing import Any, Optional
from blockchain import Block, Blockchain

from .config import logger, CHUNK_SIZE, MAX_BLOCKS, SOCKET_TIMEOUT
from .connection import ConnectionManager
from .protocol import send_message, receive_message
from .sync import (
    handle_blocks, handle_new_block
)

class BlockchainNode:
    """P2P node implementation for the blockchain network."""
    
    def __init__(self, host: str, port: int, blockchain: Blockchain):
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
        
        # Generate peer_id from host:port
        self.peer_id = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()
        
        # Initialize connection manager
        self.connection_manager = ConnectionManager(self)
        
    def start(self) -> None:
        """Start the blockchain node server"""
        logger.info(f"Starting node on {self.host}:{self.port}")        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Test if port is available
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((self.host, self.port))
            test_socket.close()
            
            if result == 0:
                raise Exception(f"Port {self.port} is already in use")
                
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            raise
        
        # Start network threads
        threading.Thread(target=self._listen_for_connections, daemon=True).start()
        threading.Thread(target=self.connection_manager.ping_peers, daemon=True).start()
        threading.Thread(target=self.connection_manager.retry_connections, daemon=True).start()
        
        logger.info(f"Node started on {self.host}:{self.port}")
        
        # Connect to known peers
        for peer_id, (host, port) in list(self.connection_manager.peers.items()):
            if peer_id not in self.connection_manager.connected_sockets:
                self.connection_manager.connect_to_peer(host, port)
                
    def stop(self) -> None:
        """Stop the blockchain node server"""
        logger.info("Stopping blockchain node")
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.connection_manager.close_all_connections()
        self.connection_manager.save_peers()

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

    def _handle_peer_connection(self, sock: socket.socket, peer_id: str) -> None:
        """Handle messages from a connected peer."""
        logger.info(f"Starting message handler for peer {peer_id}")
        self.connection_manager.update_connection_state(peer_id, 'connected')
        
        try:
            while self.running:
                try:
                    # Set a timeout for receiving messages
                    sock.settimeout(SOCKET_TIMEOUT)
                    
                    # Get the next message
                    message = receive_message(sock)
                    
                    msg_type = message.get('type', '').lower()
                    payload = message.get('payload', {})
                    
                    if peer_id not in self.connection_manager.connected_sockets:
                        logger.warning(f"Peer {peer_id} no longer in connected_sockets during message processing.")
                        return

                    # Handle different message types
                    if msg_type == 'ping':
                        response = {
                            'type': 'PONG',
                            'payload': {
                                'chain_height': len(self.blockchain.chain),
                                'latest_hash': self.blockchain.get_latest_block().current_hash
                            }
                        }
                        send_message(sock, response)
                    elif msg_type == 'get_blocks':
                        self._handle_get_blocks(sock, payload, peer_id)
                    elif msg_type == 'blocks':
                        handle_blocks(sock, self.blockchain, payload, peer_id)
                    elif msg_type == 'new_block':
                        handle_new_block(self.blockchain, payload, peer_id, 
                                     self.connection_manager.broadcast_to_peers)
                    elif msg_type == 'pong':
                        logger.debug(f"Received PONG from {peer_id[:8]}")
                        with self.blockchain.lock:
                            our_height = len(self.blockchain.chain)
                            our_hash = self.blockchain.get_latest_block().current_hash

                        peer_height = payload.get("chain_height", 0)
                        peer_hash = payload.get("latest_hash", "")

                        # Scenario 1: Peer has a longer chain.
                        if peer_height > our_height:
                            logger.info(f"PONG from {peer_id[:8]} shows they have a longer chain. Requesting sync.")
                            self.connection_manager._initiate_sync_if_needed(sock, peer_id, peer_height)

                        # Scenario 2: Same height, but different blocks (a fork).
                        elif peer_height == our_height and peer_hash != our_hash:
                            logger.info(f"PONG from {peer_id[:8]} shows a fork at the same height. Requesting sync.")
                            self.connection_manager._initiate_sync_if_needed(sock, peer_id, peer_height)
                    else:
                        if msg_type:
                            logger.warning(f"Unknown message type '{msg_type}' from peer {peer_id}")
                except socket.timeout:
                    # No data received within timeout, check if still running
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
