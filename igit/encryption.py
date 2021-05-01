
from cryptography.fernet import Fernet
 
ENCRYPTORS = {}

class NoOpEncryptor:
    key: bytes

    def __init__(self, key=b""):
        self.key = key

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data
    
ENCRYPTORS["fernet"] = Fernet