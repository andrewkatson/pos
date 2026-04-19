import re
import uuid
import logging
from uuid import UUID

from .constants import Patterns

logger = logging.getLogger(__name__)


def is_valid_uuid(uuid_to_test):
    try:
        uuid_obj = UUID(uuid_to_test, version=4)
    except ValueError:
        logger.debug(f"UUID validation failed: ValueError for {uuid_to_test}")
        return False
    except AttributeError:
        if type(uuid_to_test) is not uuid.UUID:
            logger.debug(f"UUID validation failed: Not a UUID object ({type(uuid_to_test)})")
            return False
        return True
        
    is_valid = str(uuid_obj) == uuid_to_test
    if not is_valid:
        logger.debug(f"UUID validation failed: String mismatch for {uuid_to_test}")
    return is_valid


def is_valid_pattern(text, pattern_str):
    if pattern_str == Patterns.uuid4:
        return is_valid_uuid(text)
    matches_list = re.findall(str(pattern_str), str(text))
    is_match = len(matches_list) > 0
    if not is_match:
        logger.debug("Pattern validation failed for text input against regex")
    return is_match