POSITIVE_IMAGE_FILENAME = 'positive_image_url.png'
NEGATIVE_IMAGE_FILENAME = 'negative_image_url.png'
POSITIVE_IMAGE_URL = f'https://test-bucket.s3.amazonaws.com/{POSITIVE_IMAGE_FILENAME}'
NEGATIVE_IMAGE_URL = f'https://test-bucket.s3.amazonaws.com/{NEGATIVE_IMAGE_FILENAME}'
POSITIVE_TEXT = 'positive'
NEGATIVE_TEXT = 'negative'
GEMINI_MODEL = 'gemini-2.5-flash'
CLAUDE_MODEL = 'claude-haiku-4-5-20251001'
OPENAI_MODEL = 'gpt-4o-mini'

# Probability zones for classification scores (probability that content is
# positive/acceptable). Scores at or below REJECT_THRESHOLD are rejected with
# no possibility of appeal. Scores at or above ALLOW_THRESHOLD are always
# allowed. Anything strictly between the two is the "middle zone": escalated
# to additional AIs and, if still not allowed, rejected but appealable.
REJECT_THRESHOLD = 0.3
ALLOW_THRESHOLD = 0.7

# Per-call timeout (in seconds) for outbound AI classification requests. Without
# an explicit timeout the provider SDKs default to minutes, so a single hung
# provider can stall a whole post-creation request well past the gateway's own
# timeout and surface to the client as a 504. A call that exceeds this is
# treated like any other failed provider and skipped by the cascade.
LLM_TIMEOUT_SECONDS = 15

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

# User-facing explanations for blocked content, keyed by the rule numbers in
# _CONTENT_RULES (0 means "no specific rule"). Models report only a rule
# number; these fixed phrases are the only reason text a user ever sees, so no
# model-generated prose (or anything an uploader smuggled into it) can reach
# the client.
RULE_REASON_CODES = {
    1: 'profanity',
    2: 'nudity',
    3: 'sexual_content',
    4: 'gore',
    5: 'hate_speech',
    6: 'harassment',
    7: 'bullying',
    8: 'misinformation',
}

GENERIC_REASON_CODE = 'guidelines'

# Phrases complete a sentence like "your caption ..." or "it ...".
REASON_PHRASES = {
    'profanity': 'may contain profanity',
    'nudity': 'may contain nudity',
    'sexual_content': 'may contain sexually suggestive content',
    'gore': 'may contain gore',
    'hate_speech': 'may contain hate speech',
    'harassment': 'may contain harassment',
    'bullying': 'may contain bullying',
    'misinformation': 'may contain misinformation',
    GENERIC_REASON_CODE: 'did not meet our positivity guidelines',
}

_CONTENT_ALLOWANCES = (
    "Neutral content is acceptable. "
    "Content that begins sad but ends on a happy or hopeful note is also acceptable.\n"
)

_PROBABILITY_INSTRUCTION = (
    "Answer with only two numbers separated by a comma. The first is a number "
    "between 0.00 and 1.00 representing the probability that the content is "
    "acceptable, where 1.00 means clearly acceptable and 0.00 means clearly "
    "unacceptable. The second is the number of the single rule above that the "
    "content most risks violating, or 0 if none. For example: 0.95,0\n"
)

TEXT_CLASSIFIER_PROMPT = (
    "How likely is the following text to be positive, neutral, or otherwise acceptable? "
    "Text is acceptable if it follows these rules:\n"
    + _CONTENT_RULES
    + _CONTENT_ALLOWANCES
    + _PROBABILITY_INSTRUCTION
    + "\nText: \"{text}\""
)

IMAGE_CLASSIFIER_PROMPT = (
    "How likely is this image to be positive, neutral, or otherwise acceptable? "
    "An image is acceptable if it follows these rules:\n"
    + _CONTENT_RULES
    + _CONTENT_ALLOWANCES
    + _PROBABILITY_INSTRUCTION
)
