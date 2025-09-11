from .classifier_constants import POSITIVE_TEXT

def is_text_positive(text):
    if text == POSITIVE_TEXT:
        return True
    return False