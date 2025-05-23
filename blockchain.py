import hashlib # For SHA-256
import time
import json
import os
from signature import verify_signature, generate_dp_page_signature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

BLOCKCHAIN_FILE = os.path.join("data", "blockchain", "chain.json")

class Block:
    def __init__(self, index, previous_hash, timestamp, data, signature, nonce=0):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.version = 1 # Version of the block
        self.data = data # The data stored in the block (e.g., page content, page number)
        self.signature = signature # Signature of the 'data'
        self.nonce = nonce # The nonce found by Proof of Work
        self.current_hash = None # Initialize and set after PoW

    def calculate_hash(self):
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


    def __str__(self):
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

    def to_dict(self):
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
    def from_dict(cls, block_dict):
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
    def __init__(self, difficulty=3):
        self.chain = []
        self.difficulty_string = '0' * difficulty
        self.doc_index = {}  # Document index to store blocks by title
        # Create blockchain directory if it doesn't exist
        os.makedirs(os.path.dirname(BLOCKCHAIN_FILE), exist_ok=True)
        
        # Try to load existing chain, create genesis block if none exists
        if not self.load_chain():
            print("No existing blockchain found. Creating new blockchain...")
            self._create_genesis_block()
        else:
            print("Existing blockchain loaded. Validating...")
            self._validate_and_repair_chain()

    def save_chain(self):
        """Save the blockchain to a JSON file"""
        chain_data = [block.to_dict() for block in self.chain]
        try:
            with open(BLOCKCHAIN_FILE, 'w') as f:
                json.dump(chain_data, f, indent=4)
            print("Blockchain saved successfully")
        except Exception as e:
            print(f"Error saving blockchain: {e}")

    def load_chain(self):
        """Load the blockchain from the JSON file"""
        try:
            if not os.path.exists(BLOCKCHAIN_FILE):
                return False
                
            with open(BLOCKCHAIN_FILE, 'r') as f:
                chain_data = json.load(f)
                
            self.chain = [Block.from_dict(block_dict) for block_dict in chain_data]
            return True
        except Exception as e:
            print(f"Error loading blockchain: {e}")
            return False

    def _validate_and_repair_chain(self):
        """Validate the loaded chain and remove tampered blocks"""
        if not self.chain:
            print("Empty chain loaded. Creating new genesis block...")
            self._create_genesis_block()
            return

        valid_chain = [self.chain[0]]  # Start with genesis block
        
        # Validate genesis block
        if not self._is_genesis_block_valid(self.chain[0]):
            print("Genesis block tampered. Creating new blockchain...")
            self.chain = []
            self._create_genesis_block()
            return

        # Validate rest of the chain
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = valid_chain[-1]
            
            if self._is_new_block_valid(current_block, previous_block):
                valid_chain.append(current_block)
            else:
                print(f"Chain tampered at block {i}. Discarding this and all subsequent blocks.")
                break

        if len(valid_chain) < len(self.chain):
            print(f"Removed {len(self.chain) - len(valid_chain)} invalid blocks")
            self.chain = valid_chain
            self.save_chain()  # Save the repaired chain

    def _is_genesis_block_valid(self, block):
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

    def _create_genesis_block(self):
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
        print("Genesis Block Created:")
        print(temp_genesis_block)
        
    def add_block_to_index(self, block):
        """Adds a block to the document index."""
        if not isinstance(block, Block):
            print("Error: Invalid block type.")
            return None
        if not block.data or 'title' not in block.data:
            print("Error: Block data is missing or does not contain a title.")
            return None
        
        title = block.data['title']
        if title not in self.doc_index:
            self.doc_index[title] = []
        self.doc_index[title].append(block)
        self.doc_index[title].sort(key=lambda b: b.index)  # Sort blocks by index for each title
        print(f"Block {block.index} added to index for document '{title}'.")
        
    def get_blocks_by_title(self, title):
        """Returns all blocks associated with a given document title."""
        if title not in self.doc_index:
            print(f"No blocks found for document '{title}'.")
            return []
        return self.doc_index[title]

    def get_latest_block(self):
        """Returns the last block in the chain."""
        if not self.chain:
            return None
        return self.chain[-1]

    def add_block(self, data, signature):
        """Creates a new block, performs PoW, and adds it to the chain."""
        latest_block = self.get_latest_block()
        if not latest_block:
            print("Error: Genesis block not found. Cannot add new block.")
            return None
        if not isinstance(data, dict):
            print("Error: Data must be a dictionary.")
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

        if self._is_new_block_valid(new_block, latest_block):
            self.chain.append(new_block)
            print(f"Block #{new_block.index} added to the blockchain.")
            self.add_block_to_index(new_block)
            # print(new_block)
            return new_block
        else:
            print(f"Error: New block #{new_block.index} was invalid. Not added.")
            return None

    def _proof_of_work(self, block_to_mine):
        """
        Simple Proof of Work Algorithm:
        - Find a 'nonce' such that the hex hash of (block's content + nonce)
          has a certain number of leading zeros.
        """
        
        data_preview =  json.dumps(block_to_mine.data, sort_keys=True, separators=(',', ':'))
        if len(data_preview) > 50:
            data_preview = data_preview[:47] + "..."
        print(f"Mining block {block_to_mine.index} with data: '{data_preview}'...")
        
        nonce_to_try = 0
        while True:
            block_to_mine.nonce = nonce_to_try
            calculated_hash = block_to_mine.calculate_hash()

            if calculated_hash.startswith(self.difficulty_string):
                print(f"Block {block_to_mine.index} Mined! Nonce: {nonce_to_try}, Hash: {calculated_hash}")
                return nonce_to_try
            nonce_to_try += 1

    def _is_new_block_valid(self, new_block, previous_block):
        """Validates a new block before adding it to the chain."""
        if new_block.index != previous_block.index + 1:
            print(f"Validation Error (Block {new_block.index}): Invalid index. Expected {previous_block.index + 1}, got {new_block.index}")
            return False
        if new_block.previous_hash != previous_block.current_hash:
            print(f"Validation Error (Block {new_block.index}): Previous hash mismatch.")
            return False
        
        if new_block.current_hash != new_block.calculate_hash():
            print(f"Validation Error (Block {new_block.index}): Block's current_hash is incorrect (tampered or PoW error).")
            return False

        # Check if the PoW was actually met for the block's HEX hash
        if not new_block.current_hash.startswith(self.difficulty_string):
            print(f"Validation Error (Block {new_block.index}): Proof of Work not met for the block's hash. Expected prefix '{self.difficulty_string}'.")
            return False
            
        current_time_check = int(time.time())
        if new_block.timestamp > current_time_check + 60: # in case of client clock innacuracy
            print(f"Validation Error (Block {new_block.index}): Block timestamp {new_block.timestamp} is too far in the future compared to current time {current_time_check}.")
            return False
        
        if new_block.timestamp < previous_block.timestamp:
            print(f"Validation Error (Block {new_block.index}): Block timestamp {new_block.timestamp} is less than the previous block's timestamp {previous_block.timestamp}.")
            return False
        
        pem_public_key_str = new_block.data.get('public_key')
        
        if not pem_public_key_str:
            print(f"Validation Error (Block {new_block.index}): No public key found in block data.")
            return False
        
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
            print(f"Validation Error (Block {new_block.index}): Signature verification failed.")
            return False
        
        return True

    def is_chain_valid(self):
        """Validates the integrity of the entire blockchain."""
        if not self.chain:
            print("Chain is empty.")
            return True 

        # Check genesis block first
        genesis_block = self.chain[0]
        if genesis_block.index != 0:
            print(f"Chain Error: Genesis Block index is not 0.")
            return False
        if genesis_block.current_hash != genesis_block.calculate_hash(): # Recalculate to check for tampering
            print(f"Chain Error: Genesis Block {genesis_block.index} hash is tampered.")
            return False
        if not genesis_block.current_hash.startswith(self.difficulty_string): # Check PoW
            print(f"Chain Error: Proof of Work not met for Genesis Block {genesis_block.index}. Expected prefix '{self.difficulty_string}'.")
            return False

        # Check rest of the chain
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            if not self._is_new_block_valid(current_block, previous_block):
                 print(f"Chain Error: Validation failed for Block {current_block.index} when checking against Block {previous_block.index}.")
                 return False
        
        print("Blockchain is valid.")
        return True
