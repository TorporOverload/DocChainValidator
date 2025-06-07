"""Message handling and protocol implementation."""
import json
import socket
from typing import Any
from .config import logger, MAGIC_NUMBER, MAGIC_NUMBER_LEN, LENGTH_PREFIX_LEN, MAX_ALLOWED_PAYLOAD_SIZE

def send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    """Send a message using a magic number and fixed binary length prefix.
    
    Args:   sock: The socket to send the message through
            message: The message to send, can be a Block or dict
    
    Raises IOError if the socket is closed or not connected.
    """
    if not sock or sock._closed:
        logger.error("Socket is closed or not connected, cannot send message")
        raise IOError("Socket is closed or not connected")
        
    try:
        json_payload_bytes = json.dumps(message).encode('utf-8')
        payload_length = len(json_payload_bytes)

        length_prefix_bytes = payload_length.to_bytes(LENGTH_PREFIX_LEN, 'big')

        # Send: MAGIC_NUMBER + LENGTH_PREFIX + JSON_PAYLOAD
        sock.sendall(MAGIC_NUMBER + length_prefix_bytes + json_payload_bytes)
        
        logger.debug(f"Sent message type {message.get('type', 'unknown')} with payload length {payload_length}")

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise IOError(f"Error sending message: {str(e)}")

def read_exact_bytes(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Function read exactly num_bytes from a socket.
    Raises ConnectionError if the connection is broken or not enough bytes are received.

    Args:   sock: The socket to read from
            num_bytes: The exact number of bytes to read
    """
    data = b""
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))

        if not chunk:
            # Socket closed before all bytes were received
            raise ConnectionError(
                f"Connection closed by peer. Expected {num_bytes} bytes, "
                f"received {len(data)} before close."
            )
        data += chunk
    return data

def receive_message(sock: socket.socket) -> dict[str, Any]:
    """Receive one complete message (Magic + Length Prefix + JSON Payload) from a peer.
    
    Args: sock: The socket to read from
    
    Returns the parsed message dictionary.
    Raises ConnectionError or ValueError for serious issues.
    """
    try:
        received_magic_number = read_exact_bytes(sock, MAGIC_NUMBER_LEN)
        if received_magic_number != MAGIC_NUMBER:
            logger.error(
                f"Invalid magic number received. Expected {MAGIC_NUMBER!r}, "
                f"got {received_magic_number!r}."
            )
            raise ValueError("Invalid magic number received.")

        length_prefix_bytes = read_exact_bytes(sock, LENGTH_PREFIX_LEN)
        payload_length = int.from_bytes(length_prefix_bytes, 'big')

        if not (0 <= payload_length <= MAX_ALLOWED_PAYLOAD_SIZE):
            logger.error(
                f"Invalid payload length received: {payload_length}. Max allowed: {MAX_ALLOWED_PAYLOAD_SIZE}."
            )
            raise ValueError(f"Invalid payload length: {payload_length}")

        json_payload_bytes = b"" 
        if payload_length > 0:
            json_payload_bytes = read_exact_bytes(sock, payload_length)
        
        if not json_payload_bytes and payload_length == 0:
            logger.error("Received empty payload with zero length.")
        elif not json_payload_bytes and payload_length > 0:
            logger.error(f"Expected payload of size {payload_length} but got empty bytes.")
            raise ValueError("Empty payload received when non-empty was expected.")
        else:
            message_str = json_payload_bytes.decode('utf-8')
            message_dict = json.loads(message_str)
        
        logger.debug(f"Received message type {message_dict.get('type', 'unknown_type')} with payload length {payload_length}")
        return message_dict

    except ConnectionError:
        raise
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Error processing received message segment: {e}")
        raise ValueError(f"Malformed message received: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in receive_message: {e}")
        raise
