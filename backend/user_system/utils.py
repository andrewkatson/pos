import string
import hashlib
import uuid
import secrets
from django.conf import settings

from .constants import LEN_LOGIN_COOKIE_TOKEN, LEN_SESSION_MANAGEMENT_TOKEN


def get_compressed_image_url(url):
    """
    Replaces the original bucket name in the URL with the compressed bucket name
    if the original bucket name is present.
    """
    if not url:
        return url
    
    source_bucket = settings.AWS_STORAGE_BUCKET_NAME
    compressed_bucket = settings.AWS_COMPRESSED_STORAGE_BUCKET_NAME
    
    if source_bucket in url:
        return url.replace(source_bucket, compressed_bucket)
    
    return url


def generate_random_string(length):
    """Generates a random string of specified length."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for i in range(length))


def hash_string_sha256(input_string):
    """Hashes a string using SHA256."""
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_string.encode('utf-8'))
    return sha256_hash.hexdigest()


def convert_to_bool(str_value):
    """Convert a bool, or the string 'true'/'false' in any case, to a bool.

    Raises TypeError for everything else — including None and non-string types
    like an int or a dict, which arrive whenever a client sends
    `"remember_me": 1` or omits the field entirely.

    That "everything else" matters: callers catch TypeError to turn a bad value
    into a 400, so a non-string input has to raise TypeError and not the
    AttributeError a bare `.lower()` used to raise. AttributeError escaped every
    caller's except clause, so a request that merely left the field out came back
    as a 500 instead of a validation error.
    """
    if isinstance(str_value, bool):
        return str_value

    if not isinstance(str_value, str):
        raise TypeError('Invalid input')

    lowered = str_value.lower()
    if lowered == 'true':
        return True
    elif lowered == 'false':
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


def get_batch(batch_num, batch_size, lst):
    starting_index = batch_num * batch_size
    ending_index = min((batch_num + 1) * batch_size, len(lst))
    return lst[starting_index:ending_index]


def get_queryset_batch(queryset, batch_num, batch_size):
    """One batch of a QuerySet via DB-level LIMIT/OFFSET, materialized as a list.

    Unlike get_batch (which calls len() and so evaluates the whole sequence),
    this slices the QuerySet directly so the database only returns up to
    batch_size rows.
    """
    starting_index = batch_num * batch_size
    return list(queryset[starting_index:starting_index + batch_size])
