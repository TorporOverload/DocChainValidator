import hashlib # For SHA-256
import time
import json


class Block:
    def __init__(self, index, previous_hash, timestamp, data, signature, nonce=0):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.version = 1 # Version of the block
        self.data = data # The data stored in the block (e.g., page content, page number)
        self.signature = signature # Signature of the 'data'
        self.nonce = nonce # The nonce found by Proof of Work

        # The block's hash is calculated after all attributes, including the correct nonce, are set.
        # It will be set explicitly after PoW.
        self.current_hash = None # Initialize and set after PoW

    def calculate_hash(self):
        """Calculates the hash of the block's content."""
        block_content = (str(self.index) +
                         str(self.previous_hash) +
                         str(self.timestamp) +
                         str(self.version) +
                         json.dumps(self.data, sort_keys=True, separators=(',', ':')) +
                         str(self.signature) +
                         str(self.nonce))
        return hashlib.sha256(block_content.encode('utf-8')).hexdigest()


    def __str__(self):
        data_str = json.dumps(self.data, indent=4)  
        return (f"Block {self.index}:\n"
                f"  Version: {self.version}\n"
                f"  Timestamp: {self.timestamp}\n"
                f"  Previous Hash: {self.previous_hash}\n"
                f"  Data: {data_str}\n"
                f"  Signature: {self.signature}\n"
                f"  Nonce: {self.nonce}\n"
                f"  Current Hash: {self.current_hash}\n")


class Blockchain:
    def __init__(self, difficulty=3): # Difficulty: number of leading binary zeros
        self.chain = []
        self.difficulty = difficulty
        self._create_genesis_block()
        print("Blockchain Initialized.")

    def _create_genesis_block(self):
        """Creates the first block in the blockchain (Genesis Block)."""
        genesis_timestamp = int(time.time())
        genesis_data = "Genesis Block"
        genesis_signature = "N/A"
        
        # Create a temporary genesis block to find its nonce and hash
        temp_genesis_block = Block(
            index=0,
            previous_hash="0", 
            timestamp=genesis_timestamp,
            data=genesis_data,
            signature=genesis_signature,
            nonce=0
        )

        # Perform Proof of Work for the genesis block
        mined_nonce = self._proof_of_work(temp_genesis_block)
        temp_genesis_block.nonce = mined_nonce
        temp_genesis_block.current_hash = temp_genesis_block.calculate_hash() 

        self.chain.append(temp_genesis_block)
        print("Genesis Block Created:")
        print(temp_genesis_block)

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

        # Perform Proof of Work for the new block
        mined_nonce = self._proof_of_work(new_block)
        new_block.nonce = mined_nonce
        new_block.current_hash = new_block.calculate_hash() # Calculate final hash with correct nonce

        # Basic validation before adding
        if self._is_new_block_valid(new_block, latest_block):
            self.chain.append(new_block)
            print(f"Block #{new_block.index} added to the blockchain.")
            print(new_block)
            return new_block
        else:
            print(f"Error: New block #{new_block.index} is invalid. Not added.")
            return None

    def _proof_of_work(self, block_to_mine):
        """
        Simple Proof of Work Algorithm:
        - Find a number 'nonce' such that the hash of the (block's content + nonce)
          has a certain number of leading zeros in its binary representation.
        - Modifies the block_to_mine's nonce attribute during the process.
        """
        print(f"Mining block {block_to_mine.index} with data: '{block_to_mine.data}'...")
        nonce_to_try = 0
        while True:
            block_to_mine.nonce = nonce_to_try # Set the nonce to try
            calculated_hash = block_to_mine.calculate_hash()
            
            # Convert hex hash to binary string, ensuring it's padded to 256 bits
            binary_hash = bin(int(calculated_hash, 16))[2:].zfill(256)

            if binary_hash.startswith('0' * self.difficulty):
                print(f"Block {block_to_mine.index} Mined! Nonce: {nonce_to_try}, Hash: {calculated_hash}")
                return nonce_to_try # Return the successful nonce
            nonce_to_try += 1

    def _is_new_block_valid(self, new_block, previous_block):
        """Validates a new block before adding it to the chain."""
        if new_block.index != previous_block.index + 1:
            print(f"Validation Error: Invalid index. Expected {previous_block.index + 1}, got {new_block.index}")
            return False
        if new_block.previous_hash != previous_block.current_hash:
            print("Validation Error: Previous hash mismatch.")
            return False
        
        # Check if the block's hash is correct based on its content (including the PoW nonce)
        if new_block.current_hash != new_block.calculate_hash():
            print("Validation Error: Block's current_hash is incorrect.")
            return False

        # Check if the PoW was actually met for the block's hash
        binary_hash = bin(int(new_block.current_hash, 16))[2:].zfill(256)
        if not binary_hash.startswith('0' * self.difficulty):
            print("Validation Error: Proof of Work not met for the block's hash.")
            return False
            
        curret_time = int(time.time())
        if new_block.timestamp > curret_time:
            print("Validation Error: Block timestamp is in the future.")
            return False
        
        if new_block.timestamp < previous_block.timestamp:
            print("Validation Error: Block timestamp is not greater than the previous block's timestamp.")
            return False
        
        return True

    def is_chain_valid(self):
        """Validates the integrity of the entire blockchain."""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # Check if current block's hash is correctly calculated
            if current_block.current_hash != current_block.calculate_hash():
                print(f"Chain Error: Block {current_block.index} hash is tampered.")
                return False
            
            # Check if current block points to the correct previous block's hash
            if current_block.previous_hash != previous_block.current_hash:
                print(f"Chain Error: Block {current_block.index} previous_hash mismatch.")
                return False

            # Check if the PoW was met for each block's hash
            binary_hash = bin(int(current_block.current_hash, 16))[2:].zfill(256)
            if not binary_hash.startswith('0' * self.difficulty):
                print(f"Chain Error: Proof of Work not met for Block {current_block.index}.")
                return False
        
        # Also check the genesis block's own integrity (PoW)
        if self.chain:
            genesis_block = self.chain[0]
            if genesis_block.current_hash != genesis_block.calculate_hash():
                 print(f"Chain Error: Genesis Block {genesis_block.index} hash is tampered.")
                 return False
            binary_genesis_hash = bin(int(genesis_block.current_hash, 16))[2:].zfill(256)
            if not binary_genesis_hash.startswith('0' * self.difficulty):
                print(f"Chain Error: Proof of Work not met for Genesis Block {genesis_block.index}.")
                return False


        print("Blockchain is valid.")
        return True
