from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature, InvalidKey
import getpass
import os
from typing import Optional, Tuple, Any
from DPDocSigner import generate_dp_page_signature, get_dp_signature_details, verify_dp_signature_integrity


KEY_PATH = os.path.join("data", "keys")

def sign_data(dp_signature: str, private_key: Any) -> str:
    """
    Sign the data using the provided private key.
    
    Args:
        dp_signature (str): The DP signature to be signed.
        private_key (Any): The private key used for signing.
        
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

def verify_signature(dp_signature: str, signature: str, public_key: Any) -> bool:
    """
    Verify the signature of the data using the provided public key.
    
    Args:
        dp_signature (str): The DP signature whose signature is to be verified.
        signature (str): The signature to be verified.
        public_key (Any): The public key used for verification.
    
    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    message = dp_signature.encode("utf-8")
    signature_bytes = bytes.fromhex(signature)
    try:
        public_key.verify(
            signature_bytes,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False

def username_exists(username: str) -> bool:
    """
    Check if a key pair with the given username already exists in the key directory.
    Returns True if either private or public key file contains the username.
    """
    if not os.path.exists(KEY_PATH):
        return False
    for fname in os.listdir(KEY_PATH):
        if username in fname:
            return True
    return False

def generate_key_pair() -> None:
    """Generate a public/private RSA 4096-bit key pair and encrypt the private key."""

    # Get a valid username
    while True:
        username = input("Enter username for this key: ")
        if not username.isalnum():
            print("Username must be alphanumeric. Please try again.")
        elif len(username) < 3 or len(username) > 20:
            print("Username must be between 3 and 20 characters. Please try again.")
        elif username_exists(username):
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
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8'))
    )

    # Prepare output paths
    os.makedirs(KEY_PATH, exist_ok=True)
    private_key_path = os.path.join(KEY_PATH, f"{username}_private_key.pem")
    public_key_path = os.path.join(KEY_PATH, f"{username}_public_key.pem")

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
    
def load_private_key(private_key_path: str) -> Optional[Any]:
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

def get_keypair_by_username(username: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Get the public and private keys for a given username.
    """
    private_key_path = os.path.join(KEY_PATH, f"{username}_private_key.pem")
    public_key_path = os.path.join(KEY_PATH, f"{username}_public_key.pem")

    if not os.path.exists(private_key_path) or not os.path.exists(public_key_path):
        print(f"Key pair for {username} does not exist.")
        return None, None
    
    try:
        private_key = load_private_key(private_key_path)
    except (ValueError, InvalidKey) as e:
        print(f"Error loading private key for {username}: {e}")
        return None, None
    
    with open(public_key_path, "rb") as file:
        public_key_data = file.read()
    
    public_key = serialization.load_pem_public_key(public_key_data)
    
    return private_key, public_key

# if __name__ == "__main__":
#     # testing the DP signature system
#     sample_text = "This is the first 5entence. This is the second sentence. This is the third sentence."
#     doc_title = "Test Document"
#     page_number = 1
    
#     print("=== Testing DP Document Signing System ===\n")
    
#     # Generate DP signature
#     dp_signature = generate_dp_page_signature(sample_text, doc_title, page_number)
#     print(f"Generated DP Signature: {dp_signature[:32]}...\n")
    
#     # Show DP details
#     details = get_dp_signature_details()
#     print("DP Signature Chain:")
#     for detail in details["signature_chain"]:
#         print(f"  Step {detail['step_id']}: {detail['cumulative_signature']} (deps: {detail['dependencies']})")
    
#     print(f"\nTotal DP steps: {details['total_steps']}")
#     print(f"Cache efficiency: {details['cache_size']} cached computations")
    
#     # Verify integrity
#     integrity_results = verify_dp_signature_integrity()
#     print(f"\nIntegrity verification:")
#     for step_id, is_valid in integrity_results.items():
#         print(f"  Step {step_id}: {'✓ Valid' if is_valid else '✗ Invalid'}")
    
#     print("\n" + "="*50)
#     print("DP signature generation complete!")
    

    # generate_key_pair()
    # username = input("Enter username to load keys: ")
    # private_key, public_key = get_keypair_by_username(username)
    # if private_key and public_key:
    #     signature = sign_data(dp_signature, private_key)
    #     is_valid = verify_signature(dp_signature, signature, public_key)
    #     print(f"Cryptographic signature valid: {is_valid}")