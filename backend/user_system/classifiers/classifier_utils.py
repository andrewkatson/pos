import os
import re
import random
import logging
import base64
from io import BytesIO
from dataclasses import dataclass, field
from google import genai
import anthropic
import openai as openai_lib
from .classifier_constants import (
    GEMINI_MODEL, CLAUDE_MODEL, OPENAI_MODEL,
    REJECT_THRESHOLD, ALLOW_THRESHOLD,
)

logger = logging.getLogger(__name__)

API_GEMINI = 'gemini'
API_CLAUDE = 'claude'
API_OPENAI = 'openai'

ZONE_REJECT = 'reject'
ZONE_MIDDLE = 'middle'
ZONE_ALLOW = 'allow'

ENV_KEY_TO_API = {
    'GEMINI_API_KEY': API_GEMINI,
    'ANTHROPIC_API_KEY': API_CLAUDE,
    'OPENAI_API_KEY': API_OPENAI,
}


def get_available_apis():
    return [api for env_var, api in ENV_KEY_TO_API.items() if os.environ.get(env_var)]


@dataclass
class ClassificationResult:
    """Outcome of a probability-threshold classification.

    Truthy when the content is allowed, so existing `if not is_text_positive(...)`
    call sites keep working. `appealable` only matters when `allowed` is False;
    the appeal system itself is a future feature.
    """
    allowed: bool
    appealable: bool = False
    scores: list = field(default_factory=list)

    def __bool__(self):
        return self.allowed


def get_zone(score):
    if score <= REJECT_THRESHOLD:
        return ZONE_REJECT
    if score >= ALLOW_THRESHOLD:
        return ZONE_ALLOW
    return ZONE_MIDDLE


def parse_probability(text):
    """Extracts a probability in [0, 1] from a model response, or None.

    Takes the last in-range number so a response that echoes the prompt's
    "between 0.00 and 1.00" range before giving its answer still parses the
    answer rather than the echoed bounds.
    """
    numbers = [float(m) for m in re.findall(r'\d+(?:\.\d+)?|\.\d+', str(text))]
    in_range = [n for n in numbers if 0.0 <= n <= 1.0]
    if not in_range:
        logger.warning("Could not parse an in-range probability from model response: %r", text)
        return None
    return in_range[-1]


def classify_with_thresholds(available_apis, call_fn):
    """
    Cascades through up to 3 AIs using probability zones.

    - First AI: allow zone -> allowed; reject zone -> rejected, not appealable;
      middle zone -> ask a second AI.
    - Second AI: allow zone -> allowed; middle or reject zone -> ask a third AI.
    - Third AI: allow zone -> allowed; reject zone -> rejected, not appealable;
      middle zone -> rejected but appealable.
    - If the cascade needs another AI and none is available, the content is
      rejected; it is appealable only if the last score was in the middle zone.

    APIs are consulted in random order. An API that errors or returns an
    unparseable score is skipped as if unavailable. With no usable scores at
    all the content is rejected and not appealable.
    """
    if not available_apis:
        return ClassificationResult(allowed=False)

    order = random.sample(available_apis, len(available_apis))
    scores = []

    for api_name in order:
        score = call_fn(api_name)
        if score is None:
            logger.warning("API %s returned no usable score; skipping it.", api_name)
            continue

        scores.append(score)
        zone = get_zone(score)
        stage = len(scores)
        logger.info("AI #%d (%s) scored %.2f -> %s zone", stage, api_name, score, zone)

        if zone == ZONE_ALLOW:
            return ClassificationResult(allowed=True, scores=scores)
        if stage == 1 and zone == ZONE_REJECT:
            return ClassificationResult(allowed=False, appealable=False, scores=scores)
        if stage == 3:
            return ClassificationResult(allowed=False, appealable=(zone == ZONE_MIDDLE), scores=scores)
        # Middle zone (or reject zone at stage 2): escalate to the next AI.

    if not scores:
        logger.warning("No AI produced a usable score. Rejecting without appeal.")
        return ClassificationResult(allowed=False)

    appealable = get_zone(scores[-1]) == ZONE_MIDDLE
    logger.info("Cascade exhausted available AIs. Rejecting (appealable=%s).", appealable)
    return ClassificationResult(allowed=False, appealable=appealable, scores=scores)


def call_text_gemini(text, prompt_template):
    api_key = os.environ.get('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return parse_probability(response.text)


def call_text_claude(text, prompt_template):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_probability(response.content[0].text)


def call_text_openai(text, prompt_template):
    api_key = os.environ.get('OPENAI_API_KEY')
    client = openai_lib.OpenAI(api_key=api_key)
    prompt = prompt_template.format(text=text)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_probability(response.choices[0].message.content)


def _image_to_base64_png(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return base64.standard_b64encode(buffer.getvalue()).decode('utf-8')


def call_image_gemini(image, prompt):
    api_key = os.environ.get('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt, image])
    return parse_probability(response.text)


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
    return parse_probability(response.content[0].text)


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
    return parse_probability(response.choices[0].message.content)


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
