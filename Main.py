import os
import signal
from time import sleep
from datetime import datetime
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from blockchain import Blockchain
from network.node import BlockchainNode
from pdfreader import parse_pdf_to_pages_text, get_pdf_title
from signature import (
    generate_dp_page_signature,
    get_keypair_by_username,
    sign_data,
    verify_signature,
    generate_key_pair
)
from text_matcher import find_text_matches
from mining_worker import BlockMiningWorker # Import from the new file

from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)
logger.info("Application starting...")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class DocValidatorApp:
    """
    Encapsulates the MNU Digital Document Blockchain System application.
    """
    DIFFICULTY = 3
    DEFAULT_PORT = 5000

    def __init__(self):
        self._clear_terminal()
        logger.info("Loading blockchain and initializing components...")
        self.blockchain = Blockchain(self.DIFFICULTY)
        self.mining_worker = BlockMiningWorker(self.blockchain)
        self.network_node = None
        self._initialize_network_node()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        logger.info("DocValidatorApp initialized.")

    def _initialize_network_node(self):
        """Initializes and starts the network node."""
        try:
            self.network_node = BlockchainNode("localhost", self.DEFAULT_PORT, self.blockchain)
            self.network_node.start()
            logger.info(f"Network node started on port {self.DEFAULT_PORT}")
            print(f"Network running stat: {self.network_node.running}")
            print(f"Network node started on port {self.DEFAULT_PORT}")
        except Exception as e:
            logger.warning(f"Could not start network node: {e}")
            print(f"{Colors.YELLOW}Warning: Could not start network node: {e}{Colors.RESET}")
            print("Running in standalone mode. Network features will be unavailable.")

    def _clear_terminal(self):
        """Clears the terminal screen without triggering signal handlers."""
        if os.name == 'nt':  # For Windows
            os.system('cls')
        else:  # For Unix systems
            print('\033[H\033[J')
            
    def _signal_handler(self, signum, frame):
        """Handles interrupt signals (e.g., Ctrl+C) gracefully."""
        if signum == signal.SIGINT:  # Only handle Ctrl+C, not other signals
            logger.info("Interrupt signal received. Shutting down application.")
            print("\n\nInterrupt signal received.")
            self._shutdown()
            exit(0)

    def _shutdown(self):
        logger.info("Shutting down application. Saving blockchain and stopping network node if running.")
        print("Saving blockchain...")
        self.blockchain.save_chain()
        print("Blockchain saved.")
        if self.network_node and hasattr(self.network_node, 'stop'):
            print("Stopping network node...")
            self.network_node.stop()
            logger.info("Network node stopped.")
            print("Network node stopped.")
        print("Exiting the system...")
        sleep(1)

    def _sign_document(self):
        self._clear_terminal()
        logger.info("User started document signing process.")
        print("Sign a New Document")
        print("---------------------")
        while True:
            file_path = input("Enter the path to the PDF document: ")
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                print(f"{Colors.RED}File not found. Please check the path and try again.{Colors.RESET}")
                continue
            if not file_path.lower().endswith('.pdf'):
                logger.warning(f"File is not a PDF: {file_path}")
                print(f"{Colors.RED}The file is not a PDF. Please provide a valid PDF document.{Colors.RESET}")
                continue
            break
        
        pages = parse_pdf_to_pages_text(file_path)
        title = get_pdf_title(file_path, self.blockchain.doc_index)
        if title is None:
            logger.error(f"Failed to extract a valid title from PDF: {file_path}")
            print(f"{Colors.RED}Failed to extract a valid title from the PDF. Please check the file and try again.{Colors.RESET}")
            input("\nPress Enter to continue...")
            return
        logger.info(f"Signing document with title: {title}")
        print(f"Title of the Document: {title}")
        
        attempts = 0
        username = input("Enter username to load keys: ")
        private_key, public_key_obj = get_keypair_by_username(username) #
        while (private_key is None or public_key_obj is None) and attempts < 3:
            attempts += 1
            print(f"{Colors.YELLOW}Keys not found for '{username}'. Attempt {attempts}/3.{Colors.RESET}")
            if attempts < 3:
                 username = input("Enter a valid username to load keys: ")
                 private_key, public_key_obj = get_keypair_by_username(username) #
            else:
                print(f"{Colors.RED}Failed to load keys after 3 attempts. Please create a key pair or check the username.{Colors.RESET}")
                input("\nPress Enter to continue...")
                return

        if private_key is None or public_key_obj is None:
            print(f"{Colors.RED}Failed to load keys.{Colors.RESET}")
            input("\nPress Enter to continue...")
            return

        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        print("\nQueuing blocks for mining...")
        for i, page_content in enumerate(pages):
            data = {
                'title': title,
                'page': i, 
                'content': page_content,
                'public_key': public_key_pem
            }
            page_signature_dp = generate_dp_page_signature(page_content, title, i + 1) #
            signature = sign_data(page_signature_dp, private_key) #
            self.mining_worker.add_block_task(data=data, signature=signature)
        
        logger.info(f"Queued {len(pages)} pages for mining for document '{title}'")
        print(f"\n{Colors.GREEN}All {len(pages)} pages have been queued for mining.{Colors.RESET}")
        print("The mining process will continue in the background.")
        print("You can monitor the status on the main menu.")
        input("\nPress Enter to return to the main menu...")

    def _verify_document(self):
        self._clear_terminal()
        logger.info("User started document verification process.")
        print("Verify a Document")
        print("-------------------")
        while True:
            file_path = input("Enter the path to the PDF document: ")
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                print(f"{Colors.RED}File not found. Please check the path and try again.{Colors.RESET}")
                continue
            if not file_path.lower().endswith('.pdf'):
                logger.warning(f"File is not a PDF: {file_path}")
                print(f"{Colors.RED}The file is not a PDF. Please provide a valid PDF document.{Colors.RESET}")
                continue
            break
        
        pages = parse_pdf_to_pages_text(file_path)
        title = get_pdf_title(file_path, self.blockchain.doc_index, validation=True)
        logger.info(f"Verifying document with title: {title}")
        print(f"Title of the Document: {title}")
        
        doc_blocks = []
        tampered_pages = {}
        title_blocks = self.blockchain.get_blocks_by_title(title) #
        if title_blocks:
            print("Found blocks for document title, checking for tampering...")
            doc_blocks, tampered_pages = self._check_for_pages_by_content(pages, title_blocks)
        else:
            print(f"\n{Colors.YELLOW}No blocks found for document title: {title}{Colors.RESET}")
            print("\nWould you like to search for similar content across the entire blockchain?")
            print("This process may take longer as it needs to compare with all blocks.")
            choice = input("Enter 'y' to continue with content search, or any other key to cancel: ")
            
            if choice.lower() == 'y':
                print("\nSearching by content across the entire blockchain. Please wait...")
                doc_blocks, tampered_pages = self._check_for_pages_by_content(pages, self.blockchain.chain)
            else:
                print(f"\n{Colors.RED}✗ VERIFICATION FAILED - Document not found in blockchain.{Colors.RESET}")
                input("\nPress Enter to continue...")
                return
            
        if not doc_blocks and not tampered_pages:
            print(f"\n{Colors.RED}✗ VERIFICATION FAILED - No matching or similar content found in the blockchain.{Colors.RESET}")
            print("This document appears to be completely different from any registered document.")
            input("\nPress Enter to continue...")
            return

        print("\nVerifying blocks...")
        verified_pages_indices = set()
        
        for i, page_content in enumerate(pages):
            print(f"\nVerifying Page {i+1}...")
            page_verified_this_iteration = False
            
            for block in doc_blocks:
                if block.data.get('page') == i and block.data.get('content','').strip() == page_content.strip():
                    page_signature_dp = generate_dp_page_signature( #
                        block.data['content'],
                        block.data['title'],
                        block.data['page'] + 1 
                    )
                    public_key = serialization.load_pem_public_key(
                        block.data['public_key'].encode('utf-8'),
                        backend=default_backend()
                    )
                    if verify_signature(page_signature_dp, block.signature, public_key): #
                        print(f"{Colors.GREEN}✓ Page {i+1} verified successfully.{Colors.RESET}")
                        print(f"  Block #{block.index}, Timestamp: {datetime.fromtimestamp(block.timestamp)}")
                        verified_pages_indices.add(i)
                        page_verified_this_iteration = True
                    else:
                        print(f"{Colors.RED}✗ Page {i+1} VERIFICATION FAILED - Signature invalid for exact content match.{Colors.RESET}")
                        tampered_pages[i] = {
                            'original': block.data['content'], 'modified': page_content, 'block': block,
                            'similarity': 100.0, 'matches': []
                        }
                    break 
            
            if page_verified_this_iteration:
                continue

            if i in tampered_pages:
                info = tampered_pages[i]
                print(f"{Colors.RED}✗ Page {i+1} VERIFICATION FAILED - Content has been modified.{Colors.RESET}")
                print(f"  {Colors.YELLOW}Found similar content in Block #{info['block'].index} with {info['similarity']:.1f}% similarity.{Colors.RESET}")
            elif not any(b.data.get('page') == i for b in doc_blocks):
                 print(f"{Colors.RED}✗ Page {i+1} VERIFICATION FAILED - No matching block found in the blockchain.{Colors.RESET}")


        print("\n--- Verification Summary ---")
        print(f"Total Pages in Document: {len(pages)}")
        print(f"{Colors.GREEN}Verified Pages: {len(verified_pages_indices)}{Colors.RESET}")
        unverified_count = len(pages) - len(verified_pages_indices)
        print(f"{Colors.RED}Unverified/Tampered Pages: {unverified_count}{Colors.RESET}")
        
        if unverified_count == 0:
            print(f"\n{Colors.GREEN}✓ DOCUMENT IS VALID - All pages verified successfully.{Colors.RESET}")
        else:
            print(f"\n{Colors.RED}✗ DOCUMENT IS INVALID - Some pages failed verification or were tampered with.{Colors.RESET}")
            
        print(f"\nVerification completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        input("\nPress Enter to continue...")

    def _check_for_pages_by_content(self, pages, blocks_to_check):
        logger.info(f"Checking for pages by content. Pages: {len(pages)}, Blocks to check: {len(blocks_to_check)}")

        matching_blocks_for_doc = [] 
        tampered_info = {} 
        available_blocks = list(blocks_to_check)

        for page_idx, page_content_current_doc in enumerate(pages):
            found_exact_match_for_page = False
            best_similarity_for_page = -1.0
            candidate_tampered_block = None
            
            # Prioritize exact match for the current page index
            for block_idx, block in enumerate(available_blocks):
                if 'content' not in block.data or block.data.get('page') != page_idx:
                    continue

                block_content_stored = block.data['content'].strip()
                page_content_current_doc_stripped = page_content_current_doc.strip()
                
                match_type, similarity, _ = find_text_matches(block_content_stored, page_content_current_doc_stripped) #
                
                if match_type == 'exact':
                    matching_blocks_for_doc.append(block)
                    found_exact_match_for_page = True
                    print(f"Found exact match for page {page_idx + 1} (Block #{block.index})")
                    break 
            
            if found_exact_match_for_page:
                continue 

            # If no exact match for this page_idx, look for modified content from any remaining block
            for block in available_blocks: # Check all blocks again if not found for specific page_idx
                if 'content' not in block.data: # or block in matching_blocks_for_doc: # Already used as exact
                    continue

                block_content_stored = block.data['content'].strip()
                page_content_current_doc_stripped = page_content_current_doc.strip()
                match_type, similarity, matches = find_text_matches(block_content_stored, page_content_current_doc_stripped) #

                if similarity > best_similarity_for_page and similarity >= 30: 
                    best_similarity_for_page = similarity
                    candidate_tampered_block = block
                    candidate_matches_info = matches # Store matches for potential display
            
            if candidate_tampered_block:
                 # Check if this block was already assigned as an exact match to another page
                 is_candidate_block_used_exact = any(b.index == candidate_tampered_block.index for b in matching_blocks_for_doc)

                 if not is_candidate_block_used_exact:
                    tampered_info[page_idx] = {
                        'original': candidate_tampered_block.data['content'],
                        'modified': page_content_current_doc,
                        'block': candidate_tampered_block,
                        'similarity': best_similarity_for_page,
                        'matches': candidate_matches_info
                    }
                    print(f"{Colors.YELLOW}⚠ Page {page_idx + 1} appears to be modified. Best match with Block #{candidate_tampered_block.index} ({best_similarity_for_page:.1f}% similar).{Colors.RESET}")
        
        return matching_blocks_for_doc, tampered_info


    def _create_new_key_pair(self):
        self._clear_terminal()
        logger.info("User started key pair creation process.")
        print("Create New Key Pair")
        print("-------------------")
        try:
            generate_key_pair()
            logger.info("Key pair generation completed.")
            print(f"\n{Colors.GREEN}Key pair generation successful.{Colors.RESET}")
            
            # Ask user if they want to sign a document now
            choice = input("Would you like to sign a document with this new key? (y/n): ").lower()
            if choice == 'y':
                self._sign_document()

        except Exception as e:
            logger.error(f"Error during key pair generation: {e}")
            print(f"{Colors.RED}An error occurred during key pair generation: {e}{Colors.RESET}")
        
        input("\nPress Enter to return to the main menu...")


    def _show_network_status(self):
        self._clear_terminal()
        logger.info("User requested network status.")
        print("Network Status")
        print("--------------")
        if not self.network_node or not hasattr(self.network_node, 'get_network_stats') or not self.network_node.running:
            logger.warning("Network node is not running or not fully initialized.")
            print(f"{Colors.YELLOW}Network node is not running or not fully initialized (standalone mode).{Colors.RESET}")
        else:
            try:
                stats = self.network_node.get_network_stats()
                logger.info(f"Network status: {stats}")
                print(f"Node ID: {self.network_node.peer_id[:12]}...")
                print(f"Listening on: {self.network_node.host}:{self.network_node.port}")
                print(f"Connected Peers: {stats.get('peer_count', 'N/A')}")
                print(f"Local Chain Height: {stats.get('chain_height', 'N/A')}")
                print(f"Latest Block Hash: {stats.get('latest_block_hash', 'N/A')[:12]}...")
                if stats.get('pending_retries', 0) > 0:
                    print(f"{Colors.YELLOW}Pending reconnection attempts: {stats['pending_retries']}{Colors.RESET}")
            except Exception as e:
                logger.error(f"Error getting network status: {e}")
                print(f"{Colors.RED}Error getting network status: {e}{Colors.RESET}")
        input("\nPress Enter to continue...")

    def _connect_to_peer(self):
        self._clear_terminal()
        logger.info("User started peer connection process.")
        print("Connect to Peer")
        print("---------------")
        if self.network_node is None or not hasattr(self.network_node, 'running') or not self.network_node.running:
            logger.warning("Network node is not running or not fully initialized.")
            print(f"{Colors.YELLOW}Network node is not running or not fully initialized (standalone mode).{Colors.RESET}")
            input("\nPress Enter to continue...")
            return
        try:
            host = input("Enter peer host (default: localhost): ").strip() or "localhost"
            port_str = input(f"Enter peer port (e.g., {self.DEFAULT_PORT}): ").strip()
            if not port_str:
                logger.warning("Peer connection attempt with empty port.")
                print(f"{Colors.RED}Port number cannot be empty.{Colors.RESET}")
                input("\nPress Enter to continue..."); return
            try:
                port = int(port_str)
                if not (0 < port < 65536):
                    raise ValueError("Port number out of range.")
            except ValueError as ve:
                logger.warning(f"Invalid port number: {ve}")
                print(f"{Colors.RED}Invalid port number: {ve}{Colors.RESET}")
                input("\nPress Enter to continue..."); return
            logger.info(f"Attempting to connect to peer {host}:{port}")
            print(f"\nAttempting to connect to {host}:{port}...")
            self.network_node.connect_to_peer(host, port)
            print("Connection request sent. Check node logs for status.")
        except Exception as e:
            logger.error(f"Error initiating connection to peer: {e}")
            print(f"{Colors.RED}Error initiating connection to peer: {e}{Colors.RESET}")
        input("\nPress Enter to continue...")

    def run(self):
        """Main application loop."""
        menu_actions = {
            '1': self._sign_document,
            '2': self._verify_document,
            '3': self._create_new_key_pair,
            '4': self._show_network_status,
            '5': self._connect_to_peer,
        }

        while True:
            self._clear_terminal()
            # Check mining status
            mining_status_indicator = ""
            if self.mining_worker and self.mining_worker.working:
                mining_status_indicator = f" {Colors.YELLOW}(Mining in progress...){Colors.RESET}"
            
            print(f"\n{Colors.BLUE}MNU Digital Document Blockchain System{Colors.RESET}{mining_status_indicator}")
            print("---------------------------------------")
            print("1. Sign a new document")
            print("2. Verify a document")
            print("3. Create new key pair")
            print("4. Network Status")
            print("5. Connect to peer")
            print("6. Exit")
            print("---------------------------------------")
            choice = input("Enter your choice: ")

            if choice in menu_actions:
                logger.info(f"User selected menu option: {choice}")
                action = menu_actions[choice]
                action()
            elif choice == '6':
                logger.info("User selected exit. Shutting down application.")
                self._shutdown()
                break
            else:
                logger.warning(f"Invalid menu choice: {choice}")
                print(f"{Colors.RED}Invalid choice. Please try again.{Colors.RESET}")
                sleep(1)

if __name__ == "__main__":
    app = None
    try:
        app = DocValidatorApp()
        app.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected during app initialization or run.")
        if app:
            app._shutdown()
        else:
            print("Application not fully initialized. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred in the application: {e}")
        import traceback
        traceback.print_exc() 
        if app and hasattr(app, 'blockchain') and app.blockchain:
            print("Attempting to save blockchain before critical exit...")
            app.blockchain.save_chain() #
            print("Blockchain saved.")
        else:
            print("Could not save blockchain, app or blockchain not available.")
        print("Exiting due to critical error.")