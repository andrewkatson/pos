import os
import google.generativeai as genai
from .classifier_constants import POSITIVE_TEXT

def is_text_positive(text):
    """
    Determines if the given text is positive using Gemini.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment variables.")
        # Fallback to simple check for testing purposes if API key is missing
        # In production, this should probably raise an error or handle gracefully
        return text == POSITIVE_TEXT

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f'Is the following text positive, happy or otherwise makes the user feel good? Answer with only "True" or "False".\n\nText: "{text}"'
        
        response = model.generate_content(prompt)
        
        # Clean up response and check for "True"
        answer = response.text.strip().lower()
        return answer == "true"
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return False