from cryptography.fernet import Fernet

def generate_key():
    """Generates a valid Fernet key."""
    key = Fernet.generate_key().decode()
    print(f"\nYour new ENCRYPTION_KEY is:\n\n{key}\n")
    print("Copy this key and add it to your .env file like this:")
    print(f"ENCRYPTION_KEY={key}\n")

if __name__ == "__main__":
    generate_key()
