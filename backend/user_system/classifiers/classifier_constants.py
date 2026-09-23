POSITIVE_IMAGE_FILENAME = 'positive_image_url.png'
NEGATIVE_IMAGE_FILENAME = 'negative_image_url.png'
POSITIVE_IMAGE_URL = f'https://test-bucket.s3.amazonaws.com/{POSITIVE_IMAGE_FILENAME}'
NEGATIVE_IMAGE_URL = f'https://test-bucket.s3.amazonaws.com/{NEGATIVE_IMAGE_FILENAME}'
POSITIVE_TEXT = 'positive'
NEGATIVE_TEXT = 'negative'
# Every non-first-line classifier call is routed through OpenRouter, an
# OpenAI-compatible gateway, so we can swap the model behind each cascade tier
# without a code change (issue #393). The concrete model IDs and their priority
# order live in classifier_utils.
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

# Probability zones for classification scores (probability that content is
# positive/acceptable). Scores at or below REJECT_THRESHOLD are rejected with
# no possibility of appeal. Scores at or above ALLOW_THRESHOLD are always
# allowed. Anything strictly between the two is the "middle zone": escalated
# to additional AIs and, if still not allowed, rejected but appealable.
REJECT_THRESHOLD = 0.3
ALLOW_THRESHOLD = 0.7

# Local image pre-filter (issue #393). Blunt, zero-API detectors for the two
# most objective image violations — nudity (rule 2) and gore (rule 4) — run in
# the classification worker before the paid AI vision cascade. A confident hit
# is a final, non-appealable rejection, mirroring the text pre-filter; anything
# subtler is the cascade's job. The detector models are heavy *optional*
# dependencies (see backend/requirements-local-image-filter.txt): when they are
# absent or fail to load the pre-filter fails OPEN (allows) and the cascade
# stays the real gate, so CI/dev without the models are unaffected.
#
# NudeNet reports fine-grained classes; only these "exposed" ones are treated
# as blatant nudity. Suggestive-but-covered classes are deliberately left to
# the AI cascade to keep local rejections unambiguous.
NUDENET_BLOCKING_CLASSES = frozenset({
    'FEMALE_GENITALIA_EXPOSED',
    'MALE_GENITALIA_EXPOSED',
    'FEMALE_BREAST_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
})
# Minimum detector confidence for a *final* local rejection. Set conservatively
# high so only blatant hits are rejected outright here; the AI cascade catches
# the rest. Gore models are noisier than NudeNet, so its bar is higher.
LOCAL_NUDITY_THRESHOLD = 0.5
LOCAL_GORE_THRESHOLD = 0.85
# Optional env overrides. LOCAL_GORE_MODEL_PATH points at an ONNX NSFW/gore
# classifier (loaded via onnxruntime); with it unset gore detection is skipped
# (fails open) since there is no reliable pip-installable local gore model.
ENV_GORE_MODEL_PATH = 'LOCAL_GORE_MODEL_PATH'
ENV_NUDENET_MODEL_PATH = 'LOCAL_NUDENET_MODEL_PATH'

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
    "9. No photographs or images of babies, children, or anyone under 18\n"
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
    9: 'minors',
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
    'minors': 'may contain images of babies, children, or anyone under 18',
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

# Line-of-defense context, prepended per cascade stage (issue #491).
#
# The cascade gives its three stages genuinely different powers (see
# classify_with_thresholds): a low score from the *first* reviewer is a final,
# non-appealable rejection, while the *third* reviewer's uncertainty is itself a
# rejection because there is nobody left to escalate to. Until now every stage
# received the identical prompt, so the models could not act on the weight their
# answer carried.
#
# The goal is CALIBRATION, not vagueness. Small first-tier models are
# overconfident — they cluster at 0.9/0.1 and rarely use the middle zone — which
# at stage 1 turns a spurious low score into an unappealable ban. Stage 1 is
# therefore told that abstaining (a middle score) is a legitimate answer that
# escalates. Stage 3 is told the opposite: nothing follows it, so hedging is
# itself a verdict and it should commit.
#
# The context carries no numerals, deliberately. parse_probability_and_rule
# takes the *last* "score,rule" pair (or bare number) in a reply so that a model
# echoing its prompt before answering still parses; a numeral here could be read
# back as the verdict by a model that echoes *after* answering instead. Keep any
# new wording digit-free — there is a test for it.
#
# Deliberately absent: the earlier reviewers' scores. Passing them would anchor
# later stages toward the middle and defeat the point of asking again — each
# stage judges the content, not its predecessor. Stage position is the *only*
# per-call context any model ever receives; in particular the report re-review
# path (README, "Reporting and user moderation") adds nothing about the report,
# so no report can steer a verdict.
_STAGE_CONTEXT = {
    1: (
        "You are the first of up to three reviewers of this content. A clearly "
        "acceptable answer from you approves it immediately and a clearly "
        "unacceptable answer rejects it outright, so give an answer at either "
        "end of the range below only when you are confident. If you are "
        "genuinely unsure, answer in the middle of the range: a further, more "
        "capable reviewer will then look at it."
    ),
    2: (
        "You are the second of up to three reviewers of this content. An earlier "
        "reviewer was not confident about it. You are not told their answer and "
        "should not try to guess it — judge the content on its own. A clearly "
        "acceptable answer from you approves it; anything else passes it to a "
        "final reviewer."
    ),
    3: (
        "You are the final reviewer of this content. No one reviews it after "
        "you, so an unsure answer rejects it just as a confident rejection "
        "would. Commit to the verdict the content deserves rather than hedging."
    ),
}


def classifier_prompt(base_prompt, stage):
    """Prefix a classifier prompt with this reviewer's place in the cascade.

    `stage` is the reviewer's 1-based position among the scores that actually
    counted, which is NOT the same as its position in CASCADE_ORDER: when a tier
    errors or returns an unparseable score it is skipped, so the next tier moves
    up a stage. The cascade's decision rules key on that same stage number, so
    the prompt has to follow it rather than the tier's identity.

    An unknown stage returns the prompt unchanged — the cascade never consults a
    4th reviewer, but a prompt with no stage context is a safe default rather
    than a crash.
    """
    context = _STAGE_CONTEXT.get(stage)
    if not context:
        return base_prompt
    return context + "\n\n" + base_prompt


# =============================================================================
# POSITIVE INTEREST CATEGORIZATION (issues #446 / #35)
# =============================================================================
# These prompts are a *topic tagger*, not the safety gate above: a post has
# already passed moderation by the time it is categorized, and a freeform
# interest term has already passed is_text_positive. The model is asked only to
# pick which of the curated interest buckets the content is about. The allowed
# bucket slugs ({options}) and the per-item cap ({max}) are injected by the
# caller (interest_classifier) so the vocabulary stays defined in one place
# (user_system.constants) without this module importing it.
_INTEREST_CATEGORIZATION_INSTRUCTION = (
    "Choose up to {max} categories from this exact list that best describe what "
    "the {subject} is about:\n{options}\n"
    "Reply with only matching category names from the list, lowercase, separated "
    "by commas, and nothing else. If none of them apply, reply with the single "
    "word: none.\n"
)

INTEREST_CATEGORIZATION_TEXT_PROMPT = (
    "You label short, positive social-media posts with topic categories.\n"
    + _INTEREST_CATEGORIZATION_INSTRUCTION.replace("{subject}", "post")
    + "\nPost: \"{text}\""
)

INTEREST_CATEGORIZATION_IMAGE_PROMPT = (
    "You label positive social-media images with topic categories.\n"
    + _INTEREST_CATEGORIZATION_INSTRUCTION.replace("{subject}", "image")
)
