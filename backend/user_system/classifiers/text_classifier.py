import os
import logging
from .classifier_constants import TEXT_CLASSIFIER_PROMPT
from .classifier_utils import (
    get_available_apis, classify_with_voting,
    call_text_gemini, call_text_claude, call_text_openai,
    API_GEMINI, API_CLAUDE, API_OPENAI,
)
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)


def is_text_positive(text):
    testing = os.environ.get("TESTING", False)
    testing = testing if isinstance(testing, bool) else convert_to_bool(testing)

    if testing:
        return "negative" not in text.lower()

    available_apis = get_available_apis()

    def call_api(api_name):
        api_mapping = {
            API_GEMINI: call_text_gemini,
            API_CLAUDE: call_text_claude,
            API_OPENAI: call_text_openai,
        }
        try:
            api_func = api_mapping.get(api_name)
            if not api_func:
                logger.error("Unsupported API name: %s", api_name)
                return False
            return api_func(text, TEXT_CLASSIFIER_PROMPT)
        except Exception:
            logger.exception("Error calling %s API for text classification", api_name)
            return False

    return classify_with_voting(available_apis, call_api)
