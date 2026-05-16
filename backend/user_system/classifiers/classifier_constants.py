POSITIVE_IMAGE_URL = 'https://test-bucket.s3.amazonaws.com/positive_image_url.png'
NEGATIVE_IMAGE_URL = 'https://test-bucket.s3.amazonaws.com/negative_image_url.png'
POSITIVE_TEXT = 'positive'
NEGATIVE_TEXT = 'negative'
GEMINI_MODEL = 'gemini-2.5-flash'

_CONTENT_RULES = (
    "1. No swear words\n"
    "2. No nudity\n"
    "3. No sexually suggestive content\n"
    "4. No gore\n"
    "5. No hate speech\n"
    "6. No harassment\n"
    "7. No bullying\n"
    "8. No misinformation\n"
)

_CONTENT_ALLOWANCES = (
    "Neutral content is acceptable. "
    "Content that begins sad but ends on a happy or hopeful note is also acceptable.\n"
)

TEXT_CLASSIFIER_PROMPT = (
    "Is the following text positive, neutral, or otherwise acceptable? "
    "Text is acceptable if it follows these rules:\n"
    + _CONTENT_RULES
    + _CONTENT_ALLOWANCES
    + 'Answer with only "True" or "False".\n\n'
    "Text: \"{text}\""
)

IMAGE_CLASSIFIER_PROMPT = (
    "Is this image positive, neutral, or otherwise acceptable? "
    "An image is acceptable if it follows these rules:\n"
    + _CONTENT_RULES
    + _CONTENT_ALLOWANCES
    + 'Answer with only "True" or "False".'
)