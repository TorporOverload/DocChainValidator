"""Connection management for the P2P network."""
import json
import socket
import threading
import time
from typing import TYPE_CHECKING, Any, Optional
import os
from .config import logger, PING_INTERVAL, PEERS_FILE, MAX_RETRIES, RETRY_DELAY, MINING_LOCK_TIMEOUT
from .protocol import send_message

if TYPE_CHECKING:
    from .node import BlockchainNode

class ConnectionManager:
    """Manages P2P connections for a blockchain node."""
    
    def __init__(self, node: 'BlockchainNode'):
        self.node = node
        self.peers: set[str] = self.load_peers()
        self.connected_sockets: dict[str, socket.socket] = {}
        self.connection_states: dict[str, str] = {}
        self.connection_retries: dict[str, int] = {}
        self.lock = threading.Lock()
        self.sync_in_progress = False
        os.makedirs(os.path.dirname(PEERS_FILE), exist_ok=True)
        # Attributes for the network-wide mining lock
        self.network_mining_lock = threading.RLock()  # Changed from Lock to RLock
        self.network_mining_in_progress = False
        self.mining_lock_peer_id: Optional[str] = None
        self.mining_lock_timer: Optional[threading.Timer] = None

    def initialize_connections(self) -> None:
        """Initialize connections to known peers."""
        logger.info("Initializing connections to known peers...")
        for peer_address in list(self.peers):
            host, port_str = peer_address.split(':')
            self.connect_to_peer(host, int(port_str))
        
    def connect_to_peer(self, host: str, port: int) -> bool:
        """Connect to a peer node."""
        peer_address = f"{host}:{port}"
        
        if peer_address == f"{self.node.host}:{self.node.port}":
            logger.debug("Attempted to connect to self, skipping.")
            return False
            
        with self.lock:
            if peer_address in self.connected_sockets:
                logger.info(f"Already connected to {peer_address}")
                return True
                
            if self.connection_retries.get(peer_address, 0) >= MAX_RETRIES:
                logger.warning(f"Max retries reached for {peer_address}. Will not attempt to connect.")
                return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            
            
            # The actual peer_id will be confirmed via a handshake in handle_new_connection
            self.handle_new_connection(sock, (host, port))
            
            logger.info(f"Successfully connected to {peer_address}")
            
            with self.lock:
                self.peers.add(peer_address)
                self.connection_retries.pop(peer_address, None)
                
            return True
            
        except (socket.error, ConnectionRefusedError, OSError) as e:
            logger.error(f"Failed to connect to {peer_address}: {e}")
            with self.lock:
                self.connection_retries[peer_address] = self.connection_retries.get(peer_address, 0) + 1
            return False
            
    def handle_new_connection(self, sock: socket.socket, addr: tuple[str, int]) -> None:
        """Handle a new incoming or outgoing connection."""
        host, port = addr
        peer_address = f"{host}:{port}"

        peer_id = self.node.hash_peer_id(host, port)
        
        with self.lock:
            if peer_id in self.connected_sockets:
                logger.warning(f"Peer {peer_id} already connected. Closing new connection.")
                sock.close()
                return
            
            self.connected_sockets[peer_id] = sock
            self.connection_states[peer_id] = 'connecting'
            self.peers.add(peer_address)
            
        # Start the message handling loop for this peer
        threading.Thread(
            target=self.node._handle_peer_connection,
            args=(sock, peer_id),
            daemon=True
        ).start()
        
    def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a peer."""
        with self.lock:
            if peer_id in self.connected_sockets:
                sock = self.connected_sockets.pop(peer_id)
                self.connection_states.pop(peer_id, None)
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass
                logger.info(f"Disconnected from peer {peer_id[:8]}...")

    def broadcast_to_peers(self, message: dict[str, Any], exclude_peer: Optional[str] = None) -> None:
        """Broadcast a message to all connected peers."""
        with self.lock:
            peers_to_broadcast = list(self.connected_sockets.items())
            
        for peer_id, sock in peers_to_broadcast:
            if peer_id != exclude_peer:
                try:
                    send_message(sock, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to peer {peer_id}: {e}")
                    self.disconnect_peer(peer_id)
    
    def save_peers(self) -> None:
        """Save the list of known peers to a file."""
        with self.lock:
            try:
                with open(PEERS_FILE, "w") as f:
                    json.dump(list(self.peers), f)
                logger.info("Saved known peers to file.")
            except IOError as e:
                logger.error(f"Error saving peers to file: {e}")

    def load_peers(self) -> set[str]:
        """Load the list of known peers from a file."""
        try:
            with open(PEERS_FILE, "r") as f:
                peers_list = json.load(f)
                return set(peers_list)
        except (IOError, json.JSONDecodeError):
            logger.info("Peers file not found or invalid, starting with an empty peer list.")
            return set()

    def ping_peers(self) -> None:
        """Periodically send PING messages to connected peers."""
        while self.node.running:
            with self.lock:
                peers_to_ping = list(self.connected_sockets.items())
            
            for peer_id, sock in peers_to_ping:
                try:
                    with self.node.blockchain.lock:
                        latest_block = self.node.blockchain.get_latest_block()
                        chain_height = len(self.node.blockchain.chain)
                        latest_hash = latest_block.current_hash if latest_block else "0"
                        
                    message = {
                        "type": "PING",
                        "payload": {
                            "chain_height": chain_height,
                            "latest_hash": latest_hash
                        }
                    }
                    send_message(sock, message)
                    logger.debug(f"Sent PING to {peer_id[:8]}...")
                except Exception as e:
                    logger.error(f"Error pinging peer {peer_id[:8]}: {e}")
                    self.disconnect_peer(peer_id)
            time.sleep(PING_INTERVAL)
            
    def retry_connections(self) -> None:
        """Periodically try to reconnect to peers that we failed to connect to."""
        while self.node.running:
            with self.lock:
                peers_to_retry = [
                    peer for peer, count in self.connection_retries.items() 
                    if count < MAX_RETRIES
                ]
            for peer_address in peers_to_retry:
                host, port_str = peer_address.split(':')
                logger.info(f"Retrying connection to {peer_address}...")
                self.connect_to_peer(host, int(port_str))
                
            time.sleep(RETRY_DELAY)

    def close_all_connections(self) -> None:
        """Close all active P2P connections."""
        with self.lock:
            peers_to_disconnect = list(self.connected_sockets.keys())
        for peer_id in peers_to_disconnect:
            self.disconnect_peer(peer_id)
        logger.info("All peer connections have been closed.")
        
    def _initiate_sync_if_needed(self, sock: socket.socket, peer_id: str, peer_height: int) -> None:
        """Initiate the sync process with a peer if needed."""
        with self.lock:
            if self.sync_in_progress:
                logger.info("Sync already in progress, not initiating another one.")
                return

            self.sync_in_progress = True
            logger.info(f"Starting sync with peer {peer_id[:8]}. Setting sync_in_progress to True.")

        try:
            our_height = len(self.node.blockchain.chain)
            logger.info(f"Requesting blocks from peer {peer_id[:8]} starting from height {our_height}.")
            
            request = {"type": "GET_BLOCKS", "payload": {"start": our_height}}
            send_message(sock, request)
        except Exception as e:
            logger.error(f"Error initiating sync with {peer_id[:8]}: {e}")
            with self.lock:
                self.sync_in_progress = False

    def sync_complete(self) -> None:
        """Marks the sync process as complete."""
        with self.lock:
            if self.sync_in_progress:
                logger.info("Sync process complete. Setting sync_in_progress to False.")
                self.sync_in_progress = False
            else:
                logger.warning("sync_complete called but no sync was in progress.")

    def update_connection_state(self, peer_id: str, state: str) -> None:
        """Update the connection state of a peer."""
        with self.lock:
            self.connection_states[peer_id] = state

    def release_mining_lock(self):
        """Releases the network-wide mining lock."""
        with self.network_mining_lock:
            if self.mining_lock_timer:
                self.mining_lock_timer.cancel()
                self.mining_lock_timer = None
            
            if self.network_mining_in_progress:
                self.network_mining_in_progress = False
                self.mining_lock_peer_id = None
                logger.info("Mining lock has been released.")

    def acquire_mining_lock_from_peer(self, peer_id: str):
        """Handles a MINING_START message from a peer to lock the network."""
        with self.network_mining_lock:
            if self.network_mining_in_progress and self.mining_lock_peer_id != peer_id:
                logger.warning(f"Peer {peer_id[:8]} tried to acquire lock while held by another peer. Ignoring.")
                return

            self.network_mining_in_progress = True
            self.mining_lock_peer_id = peer_id
            
            if self.mining_lock_timer:
                self.mining_lock_timer.cancel()
            
            self.mining_lock_timer = threading.Timer(MINING_LOCK_TIMEOUT, self.release_mining_lock)
            self.mining_lock_timer.start()
            logger.info(f"Mining lock acquired by peer {peer_id[:8]} with a {MINING_LOCK_TIMEOUT}s timeout.")
    
    def handle_mining_finish(self, peer_id: str):
        """Handles a MINING_FINISH message from a peer to release the lock."""
        with self.network_mining_lock:
            # Only the peer that currently holds the lock can release it.
            if self.network_mining_in_progress and self.mining_lock_peer_id == peer_id:
                logger.info(f"Received MINING_FINISH from lock holder {peer_id[:8]}. Releasing lock.")
                self.release_mining_lock()
            elif self.mining_lock_peer_id != peer_id:
                logger.warning(f"Received MINING_FINISH from non-lock-holding peer {peer_id[:8]}. Ignoring.")