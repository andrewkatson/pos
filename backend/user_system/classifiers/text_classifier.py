from .classifier_constants import POSITIVE_TEXT

# TODO: code real classifier using an LLM
def is_text_positive(text):
    if text == POSITIVE_TEXT:
        return True
    return False