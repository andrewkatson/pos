import os
import logging
from .classifier_constants import TEXT_CLASSIFIER_PROMPT
from .classifier_utils import (
    get_available_apis, classify_with_thresholds, ClassificationResult,
    TEXT_API_DISPATCH,
)
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)


def is_text_positive(text):
    """Returns a ClassificationResult (truthy when the text is allowed)."""
    text = str(text)
    logger.debug("is_text_positive called — text length=%d", len(text))
    testing = os.environ.get("TESTING", False)
    testing = testing if isinstance(testing, bool) else convert_to_bool(testing)

    if testing:
        allowed = "negative" not in text.lower()
        logger.debug("Testing mode — allowed=%s", allowed)
        return ClassificationResult(allowed=allowed)

    logger.debug("Checking available AI APIs for text classification")
    available_apis = get_available_apis()
    logger.info("Available APIs for text classification: %s", available_apis)

    if not available_apis:
        logger.error("No AI API keys available.")
        return ClassificationResult(allowed=False)

    def call_api(api_name):
        try:
            api_func = TEXT_API_DISPATCH.get(api_name)
            if not api_func:
                logger.error("Unsupported API name: %s", api_name)
                return None
            logger.debug("Calling %s API for text classification", api_name)
            score = api_func(text, TEXT_CLASSIFIER_PROMPT)
            logger.debug("%s API returned: %s", api_name, score)
            return score
        except Exception:
            logger.exception("Error calling %s API for text classification", api_name)
            return None

    logger.info("Starting text classification cascade with APIs: %s", available_apis)
    result = classify_with_thresholds(available_apis, call_api)
    logger.info("Text classification result: %s", result)
    return result
