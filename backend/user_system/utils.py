import random
import string
import hashlib
import uuid
import secrets

from .constants import LEN_LOGIN_COOKIE_TOKEN, LEN_SESSION_MANAGEMENT_TOKEN


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
    if str_value.lower() == 'true':
        return True
    elif str_value.lower() == 'false':
        return False
    else:
        raise TypeError('Invalid input')


def generate_series_identifier():
    return uuid.uuid4()


def generate_token(len_string):
    return hash_string_sha256(generate_random_string(len_string))


def generate_management_token():
    return generate_token(LEN_SESSION_MANAGEMENT_TOKEN)


def generate_login_cookie_token():
    return generate_token(LEN_LOGIN_COOKIE_TOKEN)


def generate_password(length):
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3):
            return password


def generate_reset_id(length):
    alphabet = string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))


def get_batch(batch_num, batch_size, lst):
    starting_index = batch_num * batch_size
    ending_index = min((batch_num + 1) * batch_size, len(lst))
    return lst[starting_index:ending_index]
