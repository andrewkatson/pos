from .classifier_constants import POSITIVE_IMAGE_URL

# TODO: code real classifier using an LLM
def is_image_positive(image_url):
    if image_url == POSITIVE_IMAGE_URL:
        return True
    return False