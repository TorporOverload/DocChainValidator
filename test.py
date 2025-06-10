import unittest
import os
import time
import shutil
from unittest.mock import MagicMock, patch
from block import Block
from blockchain import Blockchain
from signature import sign_data, verify_signature, generate_dp_page_signature
from text_matcher import find_text_matches
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# --- Test Cases ---

class TestBlock(unittest.TestCase):
    """Tests for the Block class."""

    def test_block_creation_and_hash(self):
        """Test if a block is created correctly and its hash is consistent."""
        block = Block(
            index=1,
            previous_hash="0",
            timestamp=int(time.time()),
            data={'message': 'test block'},
            signature='test_signature'
        )
        initial_hash = block.calculate_hash()
        self.assertIsNotNone(initial_hash)
        # The hash should be the same if calculated again with the same data
        self.assertEqual(initial_hash, block.calculate_hash())

    def test_block_serialization(self):
        """Test the to_dict and from_dict methods."""
        block = Block(
            index=2,
            previous_hash="abc",
            timestamp=int(time.time()),
            data={'sender': 'A', 'receiver': 'B', 'amount': 50},
            signature='test_signature_2'
        )
        block.current_hash = block.calculate_hash()
        block_dict = block.to_dict()

        self.assertIsInstance(block_dict, dict)
        recreated_block = Block.from_dict(block_dict)

        self.assertEqual(block.index, recreated_block.index)
        self.assertEqual(block.previous_hash, recreated_block.previous_hash)
        self.assertEqual(block.current_hash, recreated_block.current_hash)
        self.assertEqual(block.data, recreated_block.data)


class TestBlockchain(unittest.TestCase):
    """Tests for the Blockchain class."""

    def setUp(self):
        """Set up a clean blockchain for each test."""
        # Create a temporary directory for test blockchain files
        self.test_dir = "temp_test_data"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(os.path.join(self.test_dir, "blockchain"))
        
        test_blockchain_file = os.path.join(self.test_dir, "blockchain", "chain.json")
        self.blockchain = Blockchain(difficulty=1, blockchain_dir=test_blockchain_file)

        # Mock the node to prevent actual broadcasting
        self.blockchain.node = MagicMock()

    def tearDown(self):
        """Clean up the test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_genesis_block_creation(self):
        """Test if the genesis block is created correctly."""
        self.assertEqual(len(self.blockchain.chain), 1)
        genesis_block = self.blockchain.get_latest_block()
        self.assertEqual(genesis_block.index, 0)
        self.assertEqual(genesis_block.previous_hash, "0")

    @patch('threading.Event')
    def test_add_block_and_validation(self, mock_event):
        """Test adding a new block and validating the chain."""
        mock_event.return_value.is_set.return_value = False # Ensure stop_event is not set
        
        # We need a valid signature to pass block validation
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        page_content = "This is a test page."
        doc_title = "TestDoc"
        page_num = 1
        
        data = {
            'title': doc_title, 'page': page_num - 1, 'content': page_content, 'public_key': public_key_pem
        }
        
        dp_hash = generate_dp_page_signature(page_content, doc_title, page_num)
        signature = sign_data(dp_hash, private_key)

        # Add the block
        added_block = self.blockchain.add_block(data, signature, mock_event())
        
        self.assertIsNotNone(added_block)
        self.assertEqual(len(self.blockchain.chain), 2)
        self.assertEqual(self.blockchain.get_latest_block().index, 1)
        self.assertTrue(self.blockchain.is_chain_valid())

    def test_tampered_chain_detection(self):
        """Test if tampering with a block invalidates the chain."""
        # Add a valid block first
        self.test_add_block_and_validation()

        # Tamper with the genesis block's data
        self.blockchain.chain[0].data = {"message": "Tampered Genesis Block"}
        
        # The chain should now be invalid because the hash of the genesis block will not match
        # the previous_hash of the next block.
        self.blockchain.validate_and_repair_chain()
        self.assertEqual(len(self.blockchain.chain), 1)
        self.assertTrue(self.blockchain._is_genesis_block_valid(self.blockchain.chain[0]))


class TestSignatures(unittest.TestCase):
    """Tests for the signature generation and verification logic."""

    def setUp(self):
        """Generate a temporary key pair for testing."""
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        self.test_data = "This is the data to be signed for the test."
        self.doc_title = "SignatureTest"
        self.page_num = 1

    def test_dp_signature_generation(self):
        """Test if the DP signature is deterministic."""
        sig1 = generate_dp_page_signature(self.test_data, self.doc_title, self.page_num)
        sig2 = generate_dp_page_signature(self.test_data, self.doc_title, self.page_num)
        self.assertEqual(sig1, sig2)
        
        self.modified_data = "This is the data to be signed for the test"
        # A small change should result in a different signature
        sig3 = generate_dp_page_signature(self.modified_data, self.doc_title, self.page_num)
        self.assertNotEqual(sig1, sig3)

    def test_sign_and_verify_success(self):
        """Test successful signing and verification."""
        dp_hash = generate_dp_page_signature(self.test_data, self.doc_title, self.page_num)
        signature = sign_data(dp_hash, self.private_key)
        self.assertTrue(verify_signature(dp_hash, signature, self.public_key))

    def test_verify_failure_wrong_data(self):
        """Test that verification fails with tampered data."""
        dp_hash = generate_dp_page_signature(self.test_data, self.doc_title, self.page_num)
        signature = sign_data(dp_hash, self.private_key)
        
        wrong_dp_hash = generate_dp_page_signature("This is the wrong data.", self.doc_title, self.page_num)
        self.assertFalse(verify_signature(wrong_dp_hash, signature, self.public_key))


class TestTextMatcher(unittest.TestCase):
    """Tests for the text matching and similarity logic."""

    def test_find_text_matches_exact(self):
        """Test an exact match."""
        original = "The quick brown fox jumps over the lazy dog."
        modified = "The quick brown fox jumps over the lazy dog."
        match_type, similarity, _ = find_text_matches(original, modified)
        self.assertEqual(match_type, 'exact')
        self.assertGreaterEqual(similarity, 99.0)

    def test_find_text_matches_modified(self):
        """Test a modified match with high similarity."""
        original = "The quick brown fox jumps over the lazy dog."
        modified = "The quick brown fox jumps over the very lazy dog."
        match_type, _, _ = find_text_matches(original, modified)
        self.assertEqual(match_type, 'modified')

    def test_find_text_matches_similar(self):
        """Test a similar match with some commonality."""
        original = "The quick brown fox is a fast animal."
        modified = "A slow brown fox is not a quick creature."
        match_type, _, _ = find_text_matches(original, modified)
        self.assertEqual(match_type, 'similar')

    def test_find_text_matches_different(self):
        """Test two completely different texts."""
        original = "The quick brown fox jumps over the lazy dog."
        modified = "Hello world, this is a test sentence."
        match_type, similarity, _ = find_text_matches(original, modified)
        self.assertEqual(match_type, 'different')
        self.assertLess(similarity, 40.0)

# --- Test Runner ---
if __name__ == '__main__':
    unittest.main(verbosity=3)