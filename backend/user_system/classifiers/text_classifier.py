import os
from google import genai
from .classifier_constants import POSITIVE_TEXT
from ..utils import convert_to_bool


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
        print("GEMINI_API_KEY not found in environment variables.")
        # Fallback to simple check for testing purposes if API key is missing
        # In production, this should probably raise an error or handle gracefully
        return False

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = (
            "Is the following text positive, happy or otherwise makes the user feel good? "
            "To be considered positive, it must follow these rules:\n"
            "1. No swear words\n"
            "2. No nudity\n"
            "3. No gore\n"
            "4. No hate speech\n"
            "5. No harassment\n"
            "6. No bullying\n"
            'Answer with only "True" or "False".\n\n'
            f'Text: "{text}"'
        )
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        # Clean up response and check for "True"
        answer = response.text.strip().lower()
        return answer == "true"
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return False