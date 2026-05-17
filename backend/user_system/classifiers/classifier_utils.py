import os
import random
import logging
import base64
from io import BytesIO
from google import genai
import anthropic
import openai as openai_lib
from .classifier_constants import GEMINI_MODEL, CLAUDE_MODEL, OPENAI_MODEL

logger = logging.getLogger(__name__)

API_GEMINI = 'gemini'
API_CLAUDE = 'claude'
API_OPENAI = 'openai'

ENV_KEY_TO_API = {
    'GEMINI_API_KEY': API_GEMINI,
    'ANTHROPIC_API_KEY': API_CLAUDE,
    'OPENAI_API_KEY': API_OPENAI,
}


def get_available_apis():
    return [api for env_var, api in ENV_KEY_TO_API.items() if os.environ.get(env_var)]


def classify_with_voting(available_apis, call_fn):
    """
    Picks 2 random APIs and uses majority vote; a 3rd breaks ties if available.
    Falls back to False with 0 APIs, or uses the sole API with 1.
    """
    if not available_apis:
        return False

    if len(available_apis) == 1:
        return call_fn(available_apis[0])

    chosen = random.sample(available_apis, 2)
    remaining = [a for a in available_apis if a not in chosen]

    result_a = call_fn(chosen[0])
    result_b = call_fn(chosen[1])

    if result_a == result_b:
        return result_a

    if remaining:
        return call_fn(remaining[0])

    logger.warning("Two APIs disagreed with no tiebreaker available. Defaulting to False.")
    return False


def call_text_gemini(text, prompt_template):
    api_key = os.environ.get('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text.strip().lower() == 'true'


def call_text_claude(text, prompt_template):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip().lower() == 'true'


def call_text_openai(text, prompt_template):
    api_key = os.environ.get('OPENAI_API_KEY')
    client = openai_lib.OpenAI(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip().lower() == 'true'


def _image_to_base64_png(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return base64.standard_b64encode(buffer.getvalue()).decode('utf-8')


def call_image_gemini(image, prompt):
    api_key = os.environ.get('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt, image])
    return response.text.strip().lower() == 'true'


def call_image_claude(image, prompt):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    image_data = _image_to_base64_png(image)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return response.content[0].text.strip().lower() == 'true'


def call_image_openai(image, prompt):
    api_key = os.environ.get('OPENAI_API_KEY')
    client = openai_lib.OpenAI(api_key=api_key)
    image_data = _image_to_base64_png(image)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return response.choices[0].message.content.strip().lower() == 'true'


TEXT_API_DISPATCH = {
    API_GEMINI: call_text_gemini,
    API_CLAUDE: call_text_claude,
    API_OPENAI: call_text_openai,
}

IMAGE_API_DISPATCH = {
    API_GEMINI: call_image_gemini,
    API_CLAUDE: call_image_claude,
    API_OPENAI: call_image_openai,
}
