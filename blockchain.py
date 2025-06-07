import hashlib # For SHA-256
import time
import json
import os
import logging
import threading
from typing import Any, Dict, List, Optional, Union
from signature import verify_signature, generate_dp_page_signature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

BLOCKCHAIN_FILE = os.path.join("data", "blockchain", "chain.json")

class Block:
    def __init__(self, index: int, previous_hash: str, timestamp: int, data: Union[Dict[str, Any], str], signature: str, nonce: int = 0) -> None:
        self.index: int = index
        self.previous_hash: str = previous_hash
        self.timestamp: int = timestamp
        self.version: int = 1 # Version of the block
        self.data: Union[Dict[str, Any], str] = data # The data stored in the block (e.g., page content, page number)
        self.signature: str = signature # Signature of the 'data'
        self.nonce: int = nonce # The nonce found by Proof of Work
        self.current_hash: Optional[str] = None # Initialize and set after PoW

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

class Blockchain:
    def __init__(self, difficulty: int = 3, blockchain_dir: str = BLOCKCHAIN_FILE) -> None:
        self.chain = []
        self.difficulty_string = '0' * difficulty
        self.blockchain_dir = blockchain_dir
        self.doc_index = {}  # Document index to store blocks by title
        self.logger = logging.getLogger("blockchain")
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Create blockchain directory if it doesn't exist
        os.makedirs(os.path.dirname(self.blockchain_dir), exist_ok=True)
        
        # Try to load existing chain, create genesis block if none exists
        if not self.load_chain():
            self.logger.info("No existing blockchain found. Creating new blockchain...")
            self._create_genesis_block()

    def save_chain(self) -> None:
        """Save the blockchain to a JSON file"""
        with self.lock:
            chain_data = [block.to_dict() for block in self.chain]
            try:
                with open(self.blockchain_dir, 'w') as f:
                    json.dump(chain_data, f, indent=4)
                self.logger.info("Blockchain saved successfully to %s", self.blockchain_dir)
            except Exception as e:
                self.logger.error("Failed to save blockchain: %s", str(e))

    def load_chain(self) -> bool:
        """Load the blockchain from the JSON file"""
        try:
            if not os.path.exists(self.blockchain_dir):
                self.logger.info("No blockchain file exists at %s", self.blockchain_dir)
                return False
            
            with self.lock:    
                with open(self.blockchain_dir, 'r') as f:
                    chain_data = json.load(f)
                    
                self.chain = [Block.from_dict(block_dict) for block_dict in chain_data]
                self.logger.info("Blockchain loaded successfully: %d blocks", len(self.chain))
                self.logger.info("Existing blockchain loaded. Validating...")
                self.validate_and_repair_chain()  # Validate and repair chain if needed
                print("Building document index...please wait.")
                self.logger.debug("Building document index...")
                # build index after the validation
                for block in self.chain:
                    if isinstance(block.data, dict) and 'title' in block.data:
                        self.add_block_to_index(block)
                return True
        except Exception as e:
            self.logger.error("Failed to load blockchain: %s", str(e))
            return False

    def validate_and_repair_chain(self) -> None:
        """Validate the loaded chain and remove tampered blocks"""
        if not self.chain:
            self.logger.info("Empty chain loaded. Creating new genesis block...")
            self._create_genesis_block()
            return

        valid_chain = [self.chain[0]]  # Start with genesis block
        total_blocks = len(self.chain)
        
        # Validate genesis block
        if not self._is_genesis_block_valid(self.chain[0]):
            self.logger.warning("Genesis block tampered. Creating new blockchain...")
            self.chain = []
            self._create_genesis_block()
            return
        print("\nValidating blockchain...")
        self.logger.info("Validating blockchain...")
        # Validate rest of the chain
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = valid_chain[-1]
            
            # Print progress
            if i % 50 == 0 or i == len(self.chain) - 1:
                print(f"Progress: {i}/{total_blocks} blocks ({(i/total_blocks*100):.1f}%)", end='\r')
            
            if self.is_new_block_valid(current_block, previous_block):
                valid_chain.append(current_block)
            else:
                self.logger.warning(f"Chain tampered at block {i}. Discarding this and all subsequent blocks.")
                break

        if len(valid_chain) < len(self.chain):
            self.logger.info(f"Removed {len(self.chain) - len(valid_chain)} invalid blocks")
            print(f"\nRemoved {len(self.chain) - len(valid_chain)} invalid blocks")
            self.chain = valid_chain
            self.save_chain()  # Save the repaired chain
        print("\nBlockchain validation complete.")
        self.logger.info("Blockchain validation complete.")

    def _is_genesis_block_valid(self, block: Block) -> bool:
        """Special validation for genesis block"""
        if block.index != 0:
            return False
        if block.previous_hash != "0":
            return False
        if block.current_hash != block.calculate_hash():
            return False
        if not block.current_hash.startswith(self.difficulty_string):
            return False
        return True

    def _create_genesis_block(self) -> None:
        """Creates the first block in the blockchain (Genesis Block)."""
        genesis_timestamp = int(time.time())
        genesis_data = {"message": "Genesis Block"} 
        genesis_signature = "N/A_GENESIS_SIGNATURE"
        
        temp_genesis_block = Block(
            index=0,
            previous_hash="0", 
            timestamp=genesis_timestamp,
            data=genesis_data,
            signature=genesis_signature,
            nonce=0
        )

        mined_nonce = self._proof_of_work(temp_genesis_block)
        temp_genesis_block.nonce = mined_nonce
        temp_genesis_block.current_hash = temp_genesis_block.calculate_hash() 

        self.chain.append(temp_genesis_block)
        self.logger.info("Genesis Block Created:")
        self.logger.info(temp_genesis_block)
        
    def add_block_to_index(self, block: Block) -> None:
        """Adds a block to the document index."""
        if not isinstance(block, Block):
            self.logger.error("Invalid block type while adding to index")
            return
        if not block.data or 'title' not in block.data:
            self.logger.error("Block data is missing or does not contain a title")
            return
        
        title = block.data['title']
        with self.lock:
            if title not in self.doc_index:
                self.doc_index[title] = []
            self.doc_index[title].append(block)
            self.doc_index[title].sort(key=lambda b: b.index)
        self.logger.debug("Block %d added to index for document '%s'", block.index, title)

    def get_blocks_by_title(self, title: str) -> List[Block]:
        """Returns all blocks associated with a given document title."""
        with self.lock:
            if title not in self.doc_index:
                self.logger.info(f"No blocks found for document '{title}'.")
                return []
            return self.doc_index[title]

    def get_latest_block(self) -> Optional[Block]:
        """Returns the last block in the chain."""
        with self.lock:
            if not self.chain:
                return None
            return self.chain[-1]

    def add_block(self, data: Dict[str, Any], signature: str) -> Optional[Block]:
        """Creates a new block, performs PoW, and adds it to the chain."""
        with self.lock:
            latest_block = self.get_latest_block()
            if not latest_block:
                self.logger.error("Genesis block not found. Cannot add new block.")
                return None
            if not isinstance(data, dict):
                self.logger.error("Data must be a dictionary.")
                return None

            new_index = latest_block.index + 1
            new_timestamp = int(time.time())
            previous_hash = latest_block.current_hash

            new_block = Block(
                index=new_index,
                previous_hash=previous_hash,
                timestamp=new_timestamp,
                data=data,
                signature=signature,
                nonce=0
            )

            mined_nonce = self._proof_of_work(new_block)
            new_block.nonce = mined_nonce
            new_block.current_hash = new_block.calculate_hash()

            if self.is_new_block_valid(new_block, latest_block):
                self.chain.append(new_block)
                self.add_block_to_index(new_block)
                self.logger.info(f"Block #{new_block.index} added to the blockchain.")
                return new_block
            else:
                self.logger.error(f"New block #{new_block.index} was invalid. Not added.")
                return None

    def _proof_of_work(self, block_to_mine: Block) -> int:
        """
        Simple Proof of Work Algorithm:
        - Find a 'nonce' such that the hex hash of (block's content + nonce)
          has a certain number of leading zeros.
        """
        
        data_preview = json.dumps(block_to_mine.data, sort_keys=True, separators=(',', ':'))
        if len(data_preview) > 50:
            data_preview = data_preview[:47] + "..."
            
        self.logger.info("Mining block %d with data: '%s'", block_to_mine.index, data_preview)
        
        nonce_to_try = 0
        while True:
            block_to_mine.nonce = nonce_to_try
            calculated_hash = block_to_mine.calculate_hash()

            if calculated_hash.startswith(self.difficulty_string):
                self.logger.info("Block %d Mined! Nonce: %d, Hash: %s", 
                               block_to_mine.index, nonce_to_try, calculated_hash)
                return nonce_to_try
            nonce_to_try += 1
            if nonce_to_try % 100000 == 0:  # Log progress periodically
                self.logger.debug("Mining progress - Tried %d nonces for block %d", 
                                nonce_to_try, block_to_mine.index)

    def is_new_block_valid(self, new_block: Block, previous_block: Block) -> bool:
        """Validates a new block before adding it to the chain."""
        if new_block.index != previous_block.index + 1:
            self.logger.error("Block %d validation failed: Invalid index. Expected %d", 
                            new_block.index, previous_block.index + 1)
            return False
            
        if new_block.previous_hash != previous_block.current_hash:
            self.logger.error("Block %d validation failed: Previous hash mismatch", new_block.index)
            return False
            
        if new_block.current_hash != new_block.calculate_hash():
            self.logger.error("Block %d validation failed: Current hash is incorrect", new_block.index)
            return False

        if not new_block.current_hash.startswith(self.difficulty_string):
            self.logger.error("Block %d validation failed: Proof of Work not met. Expected prefix '%s'", 
                            new_block.index, self.difficulty_string)
            return False
            
        current_time_check = int(time.time())
        if new_block.timestamp > current_time_check + 60:
            self.logger.error("Block %d validation failed: Timestamp %d is too far in future (current: %d)", 
                            new_block.index, new_block.timestamp, current_time_check)
            return False
        
        if new_block.timestamp < previous_block.timestamp:
            self.logger.error("Block %d validation failed: Timestamp %d is before previous block (%d)", 
                            new_block.index, new_block.timestamp, previous_block.timestamp)
            return False

        pem_public_key_str = new_block.data.get('public_key')
        if not pem_public_key_str:
            self.logger.error("Block %d validation failed: No public key in block data", new_block.index)
            return False

        try:
            public_key = serialization.load_pem_public_key(
                pem_public_key_str.encode('utf-8'),
                backend=default_backend()
            )
            
            dp_signature = generate_dp_page_signature(
                new_block.data['content'],
                new_block.data['title'],
                new_block.data['page'] + 1
            )
            
            if not verify_signature(dp_signature, new_block.signature, public_key):
                self.logger.error("Block %d validation failed: Signature verification failed", new_block.index)
                return False
                
            self.logger.debug("Block %d passed all validation checks", new_block.index)
            return True
            
        except Exception as e:
            self.logger.error("Block %d validation failed with exception: %s", new_block.index, str(e))
            return False

    def is_chain_valid(self) -> bool:
        """Validates the integrity of the entire blockchain."""
        with self.lock:
            if not self.chain:
                self.logger.info("Chain is empty.")
                return True 

            # Check genesis block first
            genesis_block = self.chain[0]
            if genesis_block.index != 0:
                self.logger.error("Chain Error: Genesis Block index is not 0.")
                return False
            if genesis_block.current_hash != genesis_block.calculate_hash(): # Recalculate to check for tampering
                self.logger.error("Chain Error: Genesis Block {genesis_block.index} hash is tampered.")
                return False
            if not genesis_block.current_hash.startswith(self.difficulty_string): # Check PoW
                self.logger.error("Chain Error: Proof of Work not met for Genesis Block {genesis_block.index}. Expected prefix '{self.difficulty_string}'.")
                return False

            # Check rest of the chain
            for i in range(1, len(self.chain)):
                current_block = self.chain[i]
                previous_block = self.chain[i-1]
                
                if not self.is_new_block_valid(current_block, previous_block):
                     self.logger.error("Chain Error: Validation failed for Block {current_block.index} when checking against Block {previous_block.index}.")
                     return False
        
        self.logger.info("Blockchain is valid.")
        return True
    
    def get_blocks(self, start_index: int, end_index: Optional[int] = None) -> List[Block]:
        """Get a range of blocks from the chain.
        
        Args:
            start_index: Starting index (inclusive)
            end_index: Ending index (exclusive), if None returns all blocks from start
            
        Returns:
            List of blocks from start_index to end_index
        """
        with self.lock:
            if start_index < 0 or start_index >= len(self.chain):
                return []
                
            if end_index is None:
                end_index = len(self.chain)
            else:
                end_index = min(end_index, len(self.chain))
                
            return self.chain[start_index:end_index]

    def rewind_to_index(self, index: int) -> bool:
        """Rewinds the blockchain to the given index, removing all subsequent blocks."""
        with self.lock:
            if index < 0 or index >= len(self.chain):
                self.logger.error(f"Cannot rewind to invalid index {index}")
                return False

            self.logger.warning(f"Rewinding blockchain from head {len(self.chain) - 1} back to index {index}")
            
            self.chain = self.chain[:index + 1]

            # Rebuild the document index
            self.doc_index.clear()
            for block in self.chain:
                if isinstance(block.data, dict) and 'title' in block.data:
                    self.add_block_to_index(block)

            self.save_chain()  # Save the updated chain to file
            self.logger.info(f"Rewind complete. Chain height is now {len(self.chain)}")
            return True