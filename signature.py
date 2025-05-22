from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from cryptography.exceptions import InvalidKey
import getpass
import os

DP_SEED_CONSTANT = "9ca57ab0545f346b422ebf7fe6be7b9a5e11f214a1e575bfc0db081f4b5fa0ec"

def sign_data(dp_signature, private_key):
    """
    Sign the data using the provided private key.
    
    Args:
        data (str): The data to be signed.
        private_key (str): The private key used for signing.
        
    Returns:
        str: The signature of the data.
    """
    message = dp_signature.encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return signature.hex()

def verify_signature(dp_signature, signature, public_key):
    """
    
    Verify the signature of the data using the provided public key.
    
    Args:
        data (str): The data whose signature is to be verified.
        signature (str): The signature to be verified.
        public_key (str): The public key used for verification.
    
    returns:
        bool: True if the signature is valid, False otherwise.
    """
    message = dp_signature.encode("utf-8")
    signature = bytes.fromhex(signature)
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        print(f"Signature verified successfully: {signature}")
        return True
    except InvalidSignature:
        print(f"Signature verification failed: {signature}")
        return False

def username_exists(username, Key_path):
    """
    Check if a key pair with the given username already exists in the key directory.
    Returns True if either private or public key file contains the username.
    """
    if not os.path.exists(Key_path):
        return False
    for fname in os.listdir(Key_path):
        if username in fname:
            return True
    return False

def generate_key_pair(Key_path=".\\data\\keys"):
    """Generate a public/private RSA 2048-bit key pair and encrypt the private key."""

    # Get a valid username
    while True:
        username = input("Enter username for this key: ")
        if not username.isalnum():
            print("Username must be alphanumeric. Please try again.")
        elif len(username) < 3 or len(username) > 20:
            print("Username must be between 3 and 20 characters. Please try again.")
        elif username_exists(username, Key_path):
            print("A key pair with this username already exists. Please choose a different username.")
        else:
            break

    # Get and confirm a secure password
    while True:
        password = getpass.getpass("Enter password for this key: ")
        if len(password) < 8:
            print("Password must be at least 8 characters long. Please try again.")
            continue
        pass_confirm = getpass.getpass("Confirm password: ")
        if password != pass_confirm:
            print("Passwords do not match. Please try again.")
        else:
            break

    # Generate the RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    public_key = private_key.public_key()

    # Encrypt and serialize the private key
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,  # or PKCS8
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8'))
    )

    # Prepare output paths
    os.makedirs(Key_path, exist_ok=True)
    private_key_path = os.path.join(Key_path, f"{username}_private_key.pem")
    public_key_path = os.path.join(Key_path, f"{username}_public_key.pem")

    # Save private key
    with open(private_key_path, "wb") as file:
        file.write(pem_private)

    # Save public key
    with open(public_key_path, "wb") as file:
        file.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    print(f"Keys saved:\n  Private: {private_key_path}\n  Public : {public_key_path}")
    
def load_private_key(private_key_path):
    """
    Loads an RSA private key from a PEM file.
    - Handles encrypted and unencrypted keys.
    - Prompts for password if needed.
    """
    private_key = None
    
    try:
        if not os.path.exists(private_key_path):
            raise FileNotFoundError(f"Key file not found: {private_key_path}")
        if not os.path.isfile(private_key_path):
            raise IsADirectoryError(f"Key file is a directory: {private_key_path}")
        if not private_key_path.endswith(".pem"):
            raise ValueError("Key file must be in PEM format.")
        if not os.access(private_key_path, os.R_OK):
            raise PermissionError(f"Key file is not readable: {private_key_path}")
    except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
        print(f"[Key File Error] {e}")
        return False
    
    with open(private_key_path, "rb") as key_file:
        key_data = key_file.read()

    try:
        # Try loading without password (unencrypted)
        private_key = serialization.load_pem_private_key(
            key_data,
            password=None,
        )
        print("Loaded unencrypted private key.")
    except TypeError:
        # Key is encrypted, ask for password
        for _ in range(3):  # Allow up to 3 attempts
            password = getpass.getpass("Enter password for encrypted private key: ")
            try:
                private_key = serialization.load_pem_private_key(
                    key_data,
                    password=password.encode('utf-8'),
                )
                print("Successfully loaded encrypted private key.")
                break
            except (ValueError, InvalidKey):
                print("Incorrect password. Try again.")
        else:
            raise ValueError("Failed to load private key: Incorrect password.")
    return private_key

def get_keypair_by_username(username, Key_path=".\\data\\keys"):
    """
    Get the public and private keys for a given username.
    """
    private_key_path = os.path.join(Key_path, f"{username}_private_key.pem")
    public_key_path = os.path.join(Key_path, f"{username}_public_key.pem")

    if not os.path.exists(private_key_path) or not os.path.exists(public_key_path):
        print(f"Key pair for {username} does not exist.")
        return None, None

    private_key = load_private_key(private_key_path)
    with open(public_key_path, "rb") as file:
        public_key_data = file.read()
    
    public_key = serialization.load_pem_public_key(public_key_data)
    
    return private_key, public_key

    
    
def generate_dp_page_signature(page_text, doc_title, page_number):
    """
    Generates a page signature using Dynamic Programming and Hashing.
    """
    chunk_size = 20
    page_chunks = [page_text[i:i+chunk_size] for i in range(0, len(page_text), chunk_size)]
    
    if not page_text: 
        empty_page_material = (doc_title + str(page_number) + DP_SEED_CONSTANT + "EMPTY_PAGE_PLACEHOLDER").encode('utf-8')
        digest = hashes.Hash(hashes.SHA256())
        digest.update(empty_page_material) 
        hash_bytes = digest.finalize()
        return hash_bytes.hex()
    
    initial_seed = (doc_title + str(page_number) + DP_SEED_CONSTANT).encode('utf-8')
    dp_signature = hashes.Hash(hashes.SHA256())
    dp_signature.update(initial_seed)
    dp_signature = dp_signature.finalize()
    dp_signature = dp_signature.hex()
    
    for chunk in page_chunks:
        
        data_to_hash = (chunk + dp_signature).encode('utf-8')
        
        dp_signature = hashes.Hash(hashes.SHA256())
        dp_signature.update(data_to_hash)
        dp_signature = dp_signature.finalize()
        dp_signature = dp_signature.hex()
    
    return dp_signature
    
    
    
    
if __name__ == "__main__":
    # Example usage
    # generate_key_pair()

    attempts = 0
    username = input("Enter username to load keys: ")
    private_key, public_key = get_keypair_by_username(username)
    while (private_key is None or public_key is None) and attempts < 3:
        if attempts > 0: # Only ask for username again if it's not the first try
            username = input("Enter a valid username to load keys: ")
        private_key, public_key = get_keypair_by_username(username)
        attempts += 1
    if private_key is None or public_key is None:
        print("Failed to load keys after 3 attempts.")
        exit(1) # ewfrgetfnh
        
# reference:       
# https://dev.to/u2633/the-flow-of-creating-digital-signature-and-verification-in-python-37ng