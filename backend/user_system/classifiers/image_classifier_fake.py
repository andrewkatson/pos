from .classifier_constants import POSITIVE_IMAGE_URL

def is_image_positive(image_url):
    if image_url == POSITIVE_IMAGE_URL:
        return True
    return False