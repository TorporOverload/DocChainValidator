

from blockchain import Blockchain
from pdfreader import parse_pdf_to_pages_text, get_pdf_title
# --- Example Usage ---
if __name__ == '__main__':
    my_blockchain = Blockchain(difficulty=4) 

    path_to_pdf = "MSA_Vessel_Tracking___CPT245.pdf"
    print("\nAdding new blocks...")
    
    pages = parse_pdf_to_pages_text(path_to_pdf) # This will parse the PDF and print the number of pages.
    title = get_pdf_title(path_to_pdf) # This will extract the title from the PDF metadata.
    print(f"Title of the PDF: {title}")
    public_key = "PublicKey" # Placeholder for the public key

    for i, page in enumerate(pages):
        print(f"Adding block for Page {i+1}...")
        data = {
            'title' : title,
            'page': i,
            'content' : page,
            'public_key' : public_key
        }
        my_blockchain.add_block(data=data, signature=f"SigPage{i+1}")

    # Print the blockchain
    print("\nCurrent Blockchain:")
    for block in my_blockchain.chain:
        print(block)
    # Validate the blockchain
    
    print("\nValidating the chain...")
    my_blockchain.is_chain_valid()

  