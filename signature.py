
import hashlib # For SHA-256
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import getpass
import os

def sign_data(data, private_key):
    """
    Sign the data using the provided private key.
    
    Args:
        data (str): The data to be signed.
        private_key (str): The private key used for signing.
        
    Returns:
        str: The signature of the data.
    """
    # Placeholder for actual signing logic
    return hashlib.sha256((data + private_key).encode()).hexdigest()

def verify_signature(data, signature, public_key):
    """
    
    Verify the signature of the data using the provided public key.
    
    Args:
        data (str): The data whose signature is to be verified.
        signature (str): The signature to be verified.
        public_key (str): The public key used for verification.
    
    returns:
        bool: True if the signature is valid, False otherwise.
    """
    # Placeholder for actual verification logic
    expected_signature = hashlib.sha256((data + public_key).encode()).hexdigest()
    return expected_signature == signature



def username_exists(username, Data_path):
    """
    Check if a key pair with the given username already exists in the key directory.
    Returns True if either private or public key file contains the username.
    """
    if not os.path.exists(Data_path):
        return False
    for fname in os.listdir(Data_path):
        if username in fname:
            return True
    return False

def generate_key_pair(Data_path=".\\data\\keys"):
    """Generate a public/private RSA 2048-bit key pair and encrypt the private key."""

    # Get a valid username
    while True:
        username = input("Enter username for this key: ")
        if not username.isalnum():
            print("Username must be alphanumeric. Please try again.")
        elif len(username) < 3 or len(username) > 20:
            print("Username must be between 3 and 20 characters. Please try again.")
        elif username_exists(username, Data_path):
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
    os.makedirs(Data_path, exist_ok=True)
    private_key_path = os.path.join(Data_path, f"{username}_private_key.pem")
    public_key_path = os.path.join(Data_path, f"{username}_public_key.pem")

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
    
    
if __name__ == "__main__":
    # Example usage
    generate_key_pair()
    

# reference:       
# https://dev.to/u2633/the-flow-of-creating-digital-signature-and-verification-in-python-37ng