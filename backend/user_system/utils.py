import random
import string
import hashlib


def generate_random_string(length):
    """Generates a random string of specified length."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))


def hash_string_sha256(input_string):
    """Hashes a string using SHA256."""
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_string.encode('utf-8'))
    return sha256_hash.hexdigest()


def convert_to_bool(str_value):
    """Converts a string to boolean."""
    if str_value == 'True':
        return True
    elif str_value == 'False':
        return False
    else:
        raise TypeError('Invalid input')
