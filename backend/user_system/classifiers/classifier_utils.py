import os
import re
import logging
import base64
from collections import Counter
from io import BytesIO
from dataclasses import dataclass, field
import openai as openai_lib
from .classifier_constants import (
    OPENROUTER_BASE_URL,
    REJECT_THRESHOLD, ALLOW_THRESHOLD, LLM_TIMEOUT_SECONDS,
    RULE_REASON_CODES, GENERIC_REASON_CODE, REASON_PHRASES,
)

logger = logging.getLogger(__name__)

# Logical cascade tiers, consulted in this order: a free model first and Claude
# only as a last resort (issue #393). Every call is routed through OpenRouter
# (one OPENROUTER_API_KEY), so the concrete model behind each tier can be
# swapped via env without a code change. All four defaults are vision-capable,
# so the same tiers serve both the text and image cascades.
API_GEMMA = 'gemma'
API_GEMINI = 'gemini'
API_OPENAI = 'openai'
API_CLAUDE = 'claude'

# Priority order: cheapest/free first, most expensive last.
#
# NOTE: classify_with_thresholds consults at most THREE tiers (it decides by the
# 3rd usable score), so on the normal path where the first three tiers all
# return a usable score, Claude is never called. Listing it 4th is deliberate:
# it makes Claude a genuine *last resort*, reached only when one of the cheaper
# tiers yields no usable score (an error or an unparseable response) and is
# skipped — never adding a 4th vote on top of three good ones. Reorder this
# tuple to change which tier is the fallback.
CASCADE_ORDER = (API_GEMMA, API_GEMINI, API_OPENAI, API_CLAUDE)

# Default OpenRouter model ID per tier. Override any one of them with the env
# var OPENROUTER_MODEL_<TIER> (e.g. OPENROUTER_MODEL_GEMMA) to switch models
# without touching code.
_DEFAULT_MODELS = {
    API_GEMMA:  'google/gemma-3-12b-it:free',
    API_GEMINI: 'google/gemini-2.5-flash',
    API_OPENAI: 'openai/gpt-4o-mini',
    API_CLAUDE: 'anthropic/claude-haiku-4-5',
}

ZONE_REJECT = 'reject'
ZONE_MIDDLE = 'middle'
ZONE_ALLOW = 'allow'


def model_for(api_name):
    """OpenRouter model ID for a cascade tier, honoring an env override."""
    return os.environ.get(f'OPENROUTER_MODEL_{api_name.upper()}') or _DEFAULT_MODELS[api_name]


def get_available_apis():
    """Cascade tiers to consult, in priority order (free first, Claude last).

    Everything routes through OpenRouter, so the whole cascade is available
    when OPENROUTER_API_KEY is set, and nothing is otherwise.
    """
    if not os.environ.get('OPENROUTER_API_KEY'):
        return []
    return list(CASCADE_ORDER)


@dataclass
class ClassificationResult:
    """Outcome of a probability-threshold classification.

    Truthy when the content is allowed, so existing `if not is_text_positive(...)`
    call sites keep working. `appealable` only matters when `allowed` is False;
    the appeal system itself is a future feature. `reason_code` is set on
    rejections when at least one AI cited a content rule; None otherwise.
    `provider_failure` marks a rejection that reflects infrastructure rather
    than content — no provider produced a usable score (no keys, all calls
    errored, or the image could not even be fetched). The async classification
    worker retries those instead of recording a real rejection.
    """
    allowed: bool
    appealable: bool = False
    scores: list = field(default_factory=list)
    reason_code: str = None
    provider_failure: bool = False

    def __bool__(self):
        return self.allowed

    def public_reason_code(self):
        """Stable machine-readable reason for clients."""
        return self.reason_code or GENERIC_REASON_CODE

    def public_reason(self):
        """User-facing phrase completing a sentence like "your caption ..."."""
        return REASON_PHRASES[self.public_reason_code()]


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


def parse_probability_and_rule(text):
    """Extracts a "probability,rule" answer from a model response.

    Returns (probability, rule_number) where rule_number is None when the model
    cited no rule (0) or did not use the pair format. Takes the last well-formed
    pair so a response that echoes the prompt's example before answering still
    parses the answer. Falls back to parse_probability for responses containing
    only a bare score, so a model that ignores the rule instruction still yields
    a usable probability.
    """
    pairs = re.findall(r'(\d+(?:\.\d+)?|\.\d+)\s*,\s*(\d+)', str(text))
    for prob_str, rule_str in reversed(pairs):
        prob = float(prob_str)
        if prob <= 1.0:
            return prob, int(rule_str) or None
    return parse_probability(text), None


def _normalize_call_result(value):
    """Maps a call_fn result to (score, reason_code).

    Providers return (score, rule_number) pairs, but tests and legacy callers
    may still return a bare score; both are accepted. Unknown rule numbers
    (including 0/None) normalize to no reason.
    """
    if isinstance(value, tuple):
        score, rule = value
    else:
        score, rule = value, None
    return score, RULE_REASON_CODES.get(rule)


def _pick_rejection_reason(scores, cited_codes):
    """One reason to show the user for a rejection: the rule cited most often
    by the AIs that scored the content below the allow zone, tie-broken in
    favor of the most recent (decisive) citation. Scores, model identities,
    and per-model votes are never exposed.
    """
    cited = [code for score, code in zip(scores, cited_codes)
             if code and get_zone(score) != ZONE_ALLOW]
    if not cited:
        return None
    counts = Counter(cited)
    best = max(counts.values())
    return next(code for code in reversed(cited) if counts[code] == best)


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

    APIs are consulted in the given priority order (free models first, Claude
    last — issue #393), so clear content is usually settled by the cheap tier
    and only ambiguous content escalates to the pricier ones. An API that
    errors or returns an unparseable score is skipped as if unavailable. With
    no usable scores at all the content is rejected and not appealable.
    """
    if not available_apis:
        return ClassificationResult(allowed=False, provider_failure=True)

    order = list(available_apis)
    scores = []
    cited_codes = []

    def rejection(appealable):
        return ClassificationResult(
            allowed=False, appealable=appealable, scores=scores,
            reason_code=_pick_rejection_reason(scores, cited_codes))

    for api_name in order:
        score, reason_code = _normalize_call_result(call_fn(api_name))
        if score is None:
            logger.warning("API %s returned no usable score; skipping it.", api_name)
            continue

        scores.append(score)
        cited_codes.append(reason_code)
        zone = get_zone(score)
        stage = len(scores)
        logger.info("AI #%d (%s) scored %.2f (cited rule: %s) -> %s zone",
                    stage, api_name, score, reason_code, zone)

        if zone == ZONE_ALLOW:
            return ClassificationResult(allowed=True, scores=scores)
        if stage == 1 and zone == ZONE_REJECT:
            return rejection(appealable=False)
        if stage == 3:
            return rejection(appealable=(zone == ZONE_MIDDLE))
        # Middle zone (or reject zone at stage 2): escalate to the next AI.

    if not scores:
        logger.warning("No AI produced a usable score; flagging a provider failure "
                       "(not a content verdict) so the caller can retry.")
        return ClassificationResult(allowed=False, provider_failure=True)

    appealable = get_zone(scores[-1]) == ZONE_MIDDLE
    logger.info("Cascade exhausted available AIs. Rejecting (appealable=%s).", appealable)
    return rejection(appealable=appealable)


def _openrouter_client():
    # OpenRouter is OpenAI-compatible, so the openai SDK talks to it by simply
    # pointing base_url at the gateway. One key covers every model.
    api_key = os.environ.get('OPENROUTER_API_KEY')
    return openai_lib.OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, timeout=LLM_TIMEOUT_SECONDS)


def call_text_openrouter(text, prompt_template, model):
    client = _openrouter_client()
    prompt = prompt_template.format(text=text)
    response = client.chat.completions.create(
        model=model,
        max_tokens=16,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_probability_and_rule(response.choices[0].message.content)


def call_text_openrouter_raw(prompt, model, max_tokens=64):
    """Send a fully-formed text prompt and return the raw model reply string.

    Unlike call_text_openrouter this does no probability parsing — it is the
    plumbing for callers (interest categorization) whose reply is a list of
    labels rather than a score. A slightly larger max_tokens leaves room for a
    short comma-separated list.
    """
    client = _openrouter_client()
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def _image_to_base64_png(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return base64.standard_b64encode(buffer.getvalue()).decode('utf-8')


def call_image_openrouter(image, prompt, model):
    client = _openrouter_client()
    image_data = _image_to_base64_png(image)
    response = client.chat.completions.create(
        model=model,
        max_tokens=16,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return parse_probability_and_rule(response.choices[0].message.content)


def call_image_openrouter_raw(image, prompt, model, max_tokens=64):
    """Image counterpart to call_text_openrouter_raw: returns the raw reply."""
    client = _openrouter_client()
    image_data = _image_to_base64_png(image)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return response.choices[0].message.content


# One entry per cascade tier. Each binds its tier's OpenRouter model (resolved
# at call time so an env override takes effect without reimport) and keeps the
# (content, prompt) signature the classifiers call with.
def _text_caller(api_name):
    return lambda text, prompt: call_text_openrouter(text, prompt, model_for(api_name))


def _image_caller(api_name):
    return lambda image, prompt: call_image_openrouter(image, prompt, model_for(api_name))


TEXT_API_DISPATCH = {api: _text_caller(api) for api in CASCADE_ORDER}

IMAGE_API_DISPATCH = {api: _image_caller(api) for api in CASCADE_ORDER}
