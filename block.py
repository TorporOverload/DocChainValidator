"""Block class for the blockchain."""
import hashlib
import json
from typing import Dict, Any, Union

class Block:
    def __init__(self, index: int, previous_hash: str, timestamp: int, data: Union[Dict[str, Any], str], signature: str, nonce: int = 0) -> None:
        self.index: int = index
        self.previous_hash: str = previous_hash
        self.timestamp: int = timestamp
        self.version: int = 1  # Version of the block
        self.data: Union[Dict[str, Any], str] = data  # The data stored in the block (e.g., page content, page number)
        self.signature: str = signature  # Signature of the 'data'
        self.nonce: int = nonce  # The nonce found by Proof of Work
        self.current_hash: str = None  # Initialize and set after PoW

    def calculate_hash(self) -> str:
        """Calculates the hash of the block's content."""
        # Ensure data (if a dict) is serialized consistently
        if isinstance(self.data, dict):
            data_str = json.dumps(self.data, sort_keys=True, separators=(',', ':'))
        else:
            data_str = str(self.data)

        block_content = (str(self.index) +
                        str(self.previous_hash) +
                        str(self.timestamp) +
                        str(self.version) +
                        data_str +
                        str(self.signature) +
                        str(self.nonce))
        
        first_hash = hashlib.sha256(block_content.encode('utf-8')).digest()
        double_hash = hashlib.sha256(first_hash).hexdigest()
        return double_hash

    def __str__(self) -> str:
        """String representation of the block."""
        if isinstance(self.data, dict):
            data_str = json.dumps(self.data, indent=4, sort_keys=True)
        else:
            data_str = str(self.data)
            
        return (f"Block {self.index}:\n"
                f"  Version: {self.version}\n"
                f"  Timestamp: {self.timestamp}\n"
                f"  Previous Hash: {self.previous_hash}\n"
                f"  Data: {data_str}\n"
                f"  Signature: {self.signature}\n"
                f"  Nonce: {self.nonce}\n"
                f"  Current Hash: {self.current_hash}\n")

    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary for JSON serialization"""
        return {
            'index': self.index,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'version': self.version,
            'data': self.data,
            'signature': self.signature,
            'nonce': self.nonce,
            'current_hash': self.current_hash
        }
    
    @classmethod
    def from_dict(cls, block_dict: Dict[str, Any]) -> 'Block':
        """Create a Block instance from a dictionary"""
        block = cls(
            index=block_dict['index'],
            previous_hash=block_dict['previous_hash'],
            timestamp=block_dict['timestamp'],
            data=block_dict['data'],
            signature=block_dict['signature'],
            nonce=block_dict['nonce']
        )
        block.version = block_dict['version']
        block.current_hash = block_dict['current_hash']
        return block
