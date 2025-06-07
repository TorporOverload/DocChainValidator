"""Connection management for the P2P network."""
import socket
import threading
import json
import os
import time
from .config import (
    logger, PEERS_FILE, SOCKET_TIMEOUT,
    PING_INTERVAL, RETRY_INTERVAL
)
from .protocol import send_message, receive_message

class ConnectionManager:
    """Manages peer connections and their states."""

    def __init__(self, node):
        self.node = node
        self.peers_lock = threading.Lock()
        self.sockets_lock = threading.RLock()
        self.retries_lock = threading.Lock()
        self.connection_lock = threading.Lock()
        self.peers = {}
        self.connected_sockets = {}
        self.connection_retries = {}
        self.connection_states = {}
        self.max_retries = 3
        self.load_peers()

    def load_peers(self):
        """Load known peers from file"""
        try:
            if os.path.exists(PEERS_FILE):
                with open(PEERS_FILE, 'r') as file:
                    peers_data = json.load(file)
                    for peer_id, addr in peers_data.items():
                        host, port = addr.split(":")
                        self.peers[peer_id] = (host, int(port))
                logger.info(f"Loaded {len(self.peers)} known peers")
        except Exception as e:
            logger.error(f"Error loading peers: {e}")

    def save_peers(self):
        """Save known peers to file"""
        try:
            peers_data = {
                peer_id: f"{host}:{port}"
                for peer_id, (host, port) in self.peers.items()
            }
            with open(PEERS_FILE, 'w') as f:
                json.dump(peers_data, f, indent=4)
            logger.info(f"Saved {len(self.peers)} peers")
        except Exception as e:
            logger.error(f"Error saving peers: {e}")

    def _initiate_sync_if_needed(self, sock: socket.socket, peer_id: str, peer_chain_height: int) -> None:
        """Compares local chain height with a peer's and sends a GET_BLOCKS request if behind."""
        with self.node.blockchain.lock:
            our_height: int = len(self.node.blockchain.chain)
        
        logger.info(
            f"Checking if sync is needed for peer {peer_id[:8]}... "
            f"[Our Height: {our_height}, Peer Height: {peer_chain_height}]"
        )
        
        if peer_chain_height > our_height:
            logger.info(f"Our chain is shorter. Requesting blocks from peer {peer_id[:8]} starting at block {our_height}.")
            request = {
                "type": "GET_BLOCKS",
                "payload": {"start": our_height}
            }
            send_message(sock, request)

    def update_connection_state(self, peer_id: str, state: str) -> None:
        """Update the connection state of a peer and log the change."""
        with self.connection_lock:
            self.connection_states[peer_id] = state
            logger.debug(f"Peer {peer_id[:8]} state changed to {state}")

    def connect_to_peer(self, host: str, port: int) -> bool:
        """Connect to a new peer node."""
        logger.info(f"Attempting to connect to peer at {host}:{port}")
        if host == self.node.host and port == self.node.port:
            return False

        peer_id: str = self.node.hash_peer_id(host, port)
        if peer_id in self.connected_sockets:
            return True

        sock: socket.socket = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((host, port))
            
            with self.node.blockchain.lock:
                our_height: int = len(self.node.blockchain.chain)
                latest_hash: str = self.node.blockchain.get_latest_block().current_hash

            hello_msg: dict = {
                "type": "HELLO",
                "payload": {
                    "peer_id": self.node.peer_id,
                    "protocol_version": self.node.protocol_version,
                    "chain_height": our_height,
                    "latest_hash": latest_hash
                }
            }
            send_message(sock, hello_msg)
            
            response: dict = receive_message(sock)
            if response.get("type") != "WELCOME":
                raise Exception(f"Expected 'WELCOME' message, got {response.get('type')}")

            with self.peers_lock:
                self.peers[peer_id] = (host, port)
            with self.sockets_lock:
                self.connected_sockets[peer_id] = sock
            
            logger.info(f"Successfully connected to peer {peer_id[:8]} at {host}:{port}")

            threading.Thread(
                target=self.node._handle_peer_connection,
                args=(sock, peer_id),
                daemon=True
            ).start()

            peer_chain_height: int = response.get("payload", {}).get("chain_height", 0)
            self._initiate_sync_if_needed(sock, peer_id, peer_chain_height)
            
            return True
        except Exception as e:
            logger.error(f"Failed to establish connection to {host}:{port}: {e}")
            if sock:
                sock.close()
            return False

    def handle_new_connection(self, sock: socket.socket, addr: tuple[str, int]) -> None:
        """Handle a new incoming peer connection."""
        logger.info(f"Handling new connection from {addr}")
        peer_id: str = None
        try:
            message: dict = receive_message(sock)
            if message.get("type") != "HELLO":
                raise Exception("Expected HELLO message")

            payload: dict = message.get("payload", {})
            peer_id = payload.get("peer_id")
            peer_chain_height: int = payload.get("chain_height", 0)

            if not peer_id:
                raise Exception("Peer ID missing from HELLO message")

            with self.node.blockchain.lock:
                our_height: int = len(self.node.blockchain.chain)
                latest_hash: str = self.node.blockchain.get_latest_block().current_hash

            welcome_msg: dict = {
                "type": "WELCOME", "payload": {
                    "peer_id": self.node.peer_id,
                    "chain_height": our_height,
                    "latest_hash": latest_hash
                }
            }
            send_message(sock, welcome_msg)

            with self.peers_lock:
                self.peers[peer_id] = addr
            with self.sockets_lock:
                self.connected_sockets[peer_id] = sock

            logger.info(f"New peer connected: {peer_id[:8]}")
            self.save_peers()

            threading.Thread(
                target=self.node._handle_peer_connection,
                args=(sock, peer_id),
                daemon=True
            ).start()
            
            self._initiate_sync_if_needed(sock, peer_id, peer_chain_height)

        except Exception as e:
            logger.error(f"Error handling new connection from {addr}: {e}")
            if peer_id:
                self.disconnect_peer(peer_id)
            elif sock:
                sock.close()

    def disconnect_peer(self, peer_id: str) -> None:
        """Safely disconnect and clean up a peer connection."""
        with self.sockets_lock:
            sock: socket.socket = self.connected_sockets.pop(peer_id, None)
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    sock.close()
        with self.connection_lock:
            self.connection_states.pop(peer_id, None)

    def close_all_connections(self) -> None:
        """Close all peer connections."""
        with self.sockets_lock:
            for peer_id in list(self.connected_sockets.keys()):
                self.disconnect_peer(peer_id)

    def broadcast_to_peers(self, message: dict, exclude_peer: str = None) -> None:
        """Broadcast a message to all connected peers except the excluded one."""
        disconnected: list[str] = []
        with self.sockets_lock:
            for peer_id, sock in self.connected_sockets.items():
                if peer_id != exclude_peer:
                    try:
                        send_message(sock, message)
                    except Exception:
                        disconnected.append(peer_id)
        for peer_id in disconnected:
            self.disconnect_peer(peer_id)

    def ping_peers(self) -> None:
        """Send periodic PING messages to peers."""
        while self.node.running:
            time.sleep(PING_INTERVAL)
            with self.node.blockchain.lock:
                our_height: int = len(self.node.blockchain.chain)
                latest_hash: str = self.node.blockchain.get_latest_block().current_hash
            ping_msg: dict = {"type": "PING", "payload": {"chain_height": our_height, "latest_hash": latest_hash}}
            self.broadcast_to_peers(ping_msg)

    def retry_connections(self) -> None:
        """Periodically retry failed connections."""
        while self.node.running:
            time.sleep(RETRY_INTERVAL)
            with self.retries_lock:
                retry_peers: list[str] = list(self.connection_retries.keys())
            for peer_id in retry_peers:
                with self.retries_lock:
                    retries: int = self.connection_retries.get(peer_id, 0)
                if retries >= self.max_retries:
                    logger.warning(f"Max retries reached for peer {peer_id[:8]}. Giving up.")
                    with self.retries_lock:
                        self.connection_retries.pop(peer_id, None)
                    continue
                with self.peers_lock:
                    peer_info: tuple[str, int] = self.peers.get(peer_id)
                if not peer_info:
                    logger.warning(f"No address info for peer {peer_id[:8]}. Skipping retry.")
                    with self.retries_lock:
                        self.connection_retries.pop(peer_id, None)
                    continue
                host, port = peer_info
                logger.info(f"Retrying connection to peer {peer_id[:8]} at {host}:{port} (attempt {retries+1})")
                success: bool = self.connect_to_peer(host, port)
                if success:
                    logger.info(f"Successfully reconnected to peer {peer_id[:8]} at {host}:{port}")
                    with self.retries_lock:
                        self.connection_retries.pop(peer_id, None)
                else:
                    with self.retries_lock:
                        self.connection_retries[peer_id] = retries + 1