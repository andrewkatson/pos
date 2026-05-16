import os
import logging
from google import genai
from .classifier_constants import POSITIVE_TEXT, GEMINI_MODEL, TEXT_CLASSIFIER_PROMPT
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)


def is_text_positive(text):
    """
    Determines if the given text is positive using Gemini.
    """

    testing = os.environ.get("TESTING", False)
    testing = testing if isinstance(testing, bool) else convert_to_bool(testing)

    if testing:
        return "negative" not in text.lower()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables.")
        # Fallback to simple check for testing purposes if API key is missing
        # In production, this should probably raise an error or handle gracefully
        return False

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = TEXT_CLASSIFIER_PROMPT.format(text=text)
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        
        # Clean up response and check for "True"
        answer = response.text.strip().lower()
        is_positive = (answer == "true")
        logger.info(f"Gemini text classification returned: {is_positive}")
        return is_positive
    except Exception as e:
        logger.exception("Error calling Gemini API for text classification")
        return False