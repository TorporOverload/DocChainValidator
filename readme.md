# DocChainValidator

DocChainValidator is a terminal-based digital document signing system that uses a custom-built, peer-to-peer blockchain network to sign and verify PDF documents. It ensures document integrity by creating records in a blockchain, making it easy to detect any unauthorized modifications or tampering.

### Features
- Cryptographically sign PDF documents page-by-page. Each page is stored as a unique, validated block on the blockchain.
- Verify any PDF against the blockchain's records. The system can identify exact matches and also detect tampered pages by analyzing content similarity.
- The application runs as a node in a peer-to-peer network, allowing it to sync the blockchain with other nodes and broadcast new blocks as they are created.
- Users can generate and manage their own RSA key pairs, which are used to create and verify digital signatures.

### How It Works
- Blockchain: The core of the system is a custom Proof-of-Work blockchain. When a document is signed, each page's content, along with metadata and the user's digital signature, is encapsulated in a block and added to the chain.
- Signatures: The system creates a chained hash from the sentences on a page, which is then signed using the user's private RSA key. This makes the signature highly sensitive to any change in content or structure.
- Text Matching: If a document cannot be detected on the blockchain index, the program ca search the whole blockchain to find if the same document has been added in a different name using Knuth-Morris-Pratt (KMP) algorithm to find common substrings and difflib to calculate an overall similarity ratio between the local file and the content stored on the blockchain.
- Networking: The P2P protocol ensures reliable communication using a custom magic number and a fixed-length prefix for every message sent between nodes.

### Getting Started
Prerequisites

- Python 3.7+
- Dependencies can be found in requirements.txt.

#### Installation
1. Clone the repository (or download the source code):
    ```bash
    git clone https://github.com/torporoverload/docchainvalidator.git
    cd docchainvalidator
    ```
2. Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows, use venv\Scripts\activate
    ```

1. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```
Running the Application
1. Launch the application by running main.py:

    ```bash
    python main.py
    ```
2. The application will automatically create the `data/` directory to store keys, logs, and the blockchain file on its first run.

#### Usage
1. Sign a new document: Prompts for a PDF file path and a user's credentials to sign the document and add its pages to the blockchain. The mining process runs in the background.
2. Verify a document: Asks for a PDF file path and checks its integrity against the blockchain records, providing a detailed page-by-page summary of the verification results.
3. Create new key pair: This generates a password-protected RSA public/private key pair tied to a username.
4. Network Status: Displays statistics about the P2P network node, including its ID, connected peers, and local chain height.
5. Connect to peer: Allows you to manually connect your node to another peer on the network to begin syncing.
6. Exit: Shutdown the application, saving the blockchain and closing all network connections.
