import hashlib

HASH_FUNCTIONS = {}

def sha1_hash(data):
    return hashlib.sha1(data).hexdigest()

HASH_FUNCTIONS["sha1"] = sha1_hash