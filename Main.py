from time import sleep
from blockchain import Blockchain
from pdfreader import parse_pdf_to_pages_text, get_pdf_title
from signature import generate_dp_page_signature, get_keypair_by_username, sign_data, verify_signature, generate_key_pair
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from text_matcher import find_text_matches, show_diff
import os
from datetime import datetime
import signal


DIFFICULTY = 3  # Default difficulty for mining blocks

blockchain = Blockchain(DIFFICULTY)
        
def main_menu():
    clear_terminal()
    print("Loading blockchain...")
    global blockchain
    blockchain = Blockchain(DIFFICULTY)
    
    while 1:
        print("\nMNU Digital Document Blockchain System")
        print("---------------------------------------")
        print("1. Sign a new document")
        print("2. Verify a document")
        print("3. Create new key pair")
        print("4. Exit")
        choice = input("Enter your choice: ")
        if choice == '1':
            sign_document()
        elif choice == '2':
            verify_document()
        elif choice == '3':
            generate_key_pair()
        elif choice == '4':
            print("Saving blockchain...")
            blockchain.save_chain()
            print("Exiting the system..")
            sleep(1)
            break
        else:
            print("Invalid choice. Please try again.")
         
      
def sign_document():
    global blockchain
    clear_terminal()
    print("Sign a New Document")
    print("---------------------")
    while True:
        file_path = input("Enter the path to the PDF document: ")
        if not os.path.exists(file_path):
            print("File not found. Please check the path and try again.")
            continue
        if not file_path.lower().endswith('.pdf'):
            print("The file is not a PDF. Please provide a valid PDF document.")
            continue
        else:
            break
            
    # Extract text from the PDF
    pages = parse_pdf_to_pages_text(file_path)
    title = get_pdf_title(file_path, blockchain.doc_index)
    if title is None:
        print("Failed to extract a valid title from the PDF. Please check the file and try again.")
        return
    print(f"Title of the Document: {title}")
    
    attempts = 0
    username = input("Enter username to load keys: ")
    private_key, public_key = get_keypair_by_username(username)
    while (private_key is None or public_key is None) and attempts < 3:
        if attempts > 0:
            username = input("Enter a valid username to load keys: ")
        private_key, public_key = get_keypair_by_username(username)
        attempts += 1
    if private_key is None or public_key is None:
        print("Failed to load keys after 3 attempts.")
        return

    public_key = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo).decode('utf-8')
    
    print("\nAdding new blocks...")
    for i, page in enumerate(pages):
        print(f"Adding block for Page {i+1}...")
        data = {
            'title' : title,
            'page': i,
            'content' : page,
            'public_key' : public_key
        }
        page_signature_dp = generate_dp_page_signature(page, title, i+1)
        signature = sign_data(page_signature_dp, private_key)
        blockchain.add_block(data=data, signature=signature)
        print(f"Block {i+1} added with signature: {signature}")
            
    print("\nCurrent Blockchain length:", len(blockchain.chain))
    
def verify_document():
    global blockchain
    clear_terminal()
    print("Verify a Document")
    print("-------------------")
    while True:
        file_path = input("Enter the path to the PDF document: ")
        if not os.path.exists(file_path):
            print("File not found. Please check the path and try again.")
            continue
        if not file_path.lower().endswith('.pdf'):
            print("The file is not a PDF. Please provide a valid PDF document.")
            continue
        else:
            break
            
    # Extract text from the PDF
    pages = parse_pdf_to_pages_text(file_path)
    title = get_pdf_title(file_path, blockchain.doc_index)
    print(f"Title of the Document: {title}")
    
    # Initialize containers
    doc_blocks = []
    tampered_pages = {}  # Dictionary to store pages with modifications    
    title_blocks = blockchain.get_blocks_by_title(title) # First try to find blocks by title
    if title_blocks:
        print("Found blocks for document title, checking for tampering...")
        doc_blocks, tampered_pages = check_for_pages_by_content(pages, title_blocks)
    else:
        print("No blocks found for this document name in the blockchain. Searching by content...")
        # Search through all blocks in the blockchain
        doc_blocks, tampered_pages = check_for_pages_by_content(pages, blockchain.chain)
        
    if not doc_blocks and not tampered_pages:
        print("No matching blocks found in the blockchain.")
        return

    print("\nVerifying blocks...")
    verified_pages = set()
    
    # Verify each page from the document
    for i, page in enumerate(pages):
        print(f"\nVerifying Page {i+1}...")
        page_verified = False
        found_similar = False
        
        # Try to find and verify matching block
        for block in doc_blocks:
            # Only verify if content matches exactly
            if block.data['content'].strip() == page.strip():
                # Reconstruct the signature for verification
                page_signature_dp = generate_dp_page_signature(
                    block.data['content'],
                    block.data['title'],
                    block.data['page']+1
                )
                
                # Load the public key from the block
                public_key = serialization.load_pem_public_key(
                    block.data['public_key'].encode('utf-8'),
                    backend=default_backend()
                )
                
                # Verify the signature
                if verify_signature(page_signature_dp, block.signature, public_key):
                    print(f"✓ Page {i+1} verified successfully")
                    print(f"  Block #{block.index}")
                    print(f"  Timestamp: {block.timestamp}")
                    verified_pages.add(i)
                    page_verified = True
                    found_similar = True
                    break
                else:
                    print(f"✗ Page {i+1} verification failed - Signature invalid")
                    tampered_pages[i] = {
                        'original': block.data['content'],
                        'modified': page,
                        'block': block,
                        'similarity': 100.0,  # Content matches but signature doesn't
                        'matches': []
                    }
                    found_similar = True
                    break
        
        # If not verified, search for similar content
        if not found_similar:
            best_block = None
            best_similarity = 0.0
            best_matches = []
            
            # Search through available blocks
            search_blocks = title_blocks if title_blocks else blockchain.chain
            for block in search_blocks:
                if 'content' not in block.data:
                    continue
                    
                block_content = block.data['content'].strip()
                page_content = page.strip()
                match_type, similarity, matches = find_text_matches(block_content, page_content)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_block = block
                    best_matches = matches
            
            if best_block is not None and best_similarity >= 30:  # Only show similar content if above threshold
                tampered_pages[i] = {
                    'original': best_block.data['content'],
                    'modified': page,
                    'block': best_block,
                    'similarity': best_similarity,
                    'matches': best_matches
                }
                print(f"✗ Page {i+1} verification failed - Content has been modified")
                print(f"  Found similar content with {best_similarity:.1f}% similarity")
            else:
                print(f"✗ Page {i+1} verification failed - No matching content found")
    
    # Summary
    print("\nVerification Summary:")
    print(f"Total Pages: {len(pages)}")
    print(f"Verified Pages: {len(verified_pages)}")
    
    if len(verified_pages) == len(pages):
        print("\n✓ Document is VALID - All pages verified successfully")
        print(f"Verified at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n✗ Document is INVALID - Some pages failed verification")
        unverified_pages = set(range(len(pages))) - verified_pages
        
        # Show diff for all unverified pages
        if unverified_pages:
            print("\nUnverified Pages Details:")
            for page_num in unverified_pages:
                print(f"\nPage {page_num + 1}:")
                if page_num in tampered_pages:
                    print(f"WARNING: Content modifications detected almost - {tampered_pages[page_num]['similarity']:.1f}% similarity to original")
                    print("Signature invalid")
                    # Show detailed diff for each tampered page
                    show_diff(
                        tampered_pages[page_num]['original'],
                        tampered_pages[page_num]['modified']
                    )
                    print(f"\nTimestamp of original block: {tampered_pages[page_num]['block'].timestamp}")
                else:
                    print("No matching content found in blockchain")

def check_for_pages_by_content(pages, blocks_to_check, tampered_pages=None):
    """
    Check pages for content against a list of blocks.
    
    Args:
        pages: List of page contents to check
        blocks_to_check: List of blockchain blocks to compare against
        tampered_pages: Optional dictionary to store information about tampered pages
        
    Returns:
        tuple: (matching_blocks, tampered_pages) where:
            - matching_blocks: List of blocks that exactly match any pages
            - tampered_pages: Dictionary mapping page numbers to tampering information
    """
    matching_blocks = []
    if tampered_pages is None:
        tampered_pages = {}
    
    for block in blocks_to_check:
        if 'content' not in block.data:
            continue
            
        # For each page in the document
        for i, page in enumerate(pages):
            # Skip if we already found an exact match or tampering for this page
            if i in tampered_pages or any(b.data['page'] == i for b in matching_blocks):
                continue
            
            block_content = block.data['content'].strip()
            page_content = page.strip()
            
            # Compare documents
            match_type, similarity, matches = find_text_matches(block_content, page_content)
            
            if match_type == 'exact':
                matching_blocks.append(block)
                print(f"Found exact match for page {i+1}")
                break
            elif match_type == 'modified':
                tampered_pages[i] = {
                    'original': block_content,
                    'modified': page_content,
                    'block': block,
                    'similarity': similarity,
                    'matches': matches
                }
                print(f"⚠ Page {i+1} appears to be modified almost - {similarity:.1f}% similar to original")
                print("  Signature will be invalid")
                
    return matching_blocks, tampered_pages

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')
    
def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nReceived interrupt signal. Saving blockchain...")
    blockchain.save_chain()
    print("Blockchain saved. Exiting...")
    exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)
    
if __name__ == "__main__":
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        main_menu()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Saving blockchain before exit...")
        blockchain.save_chain()
        print("Blockchain saved. Exiting...")