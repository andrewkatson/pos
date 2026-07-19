"""Cheap, local pre-filter for blatant caption violations (issue #282).

Classification now runs asynchronously, so a genuinely negative post is
normally accepted with a "pending" response and rejected minutes later. For
the most blatant cases that is a UX regression (the author only learns by
email) and needless queue load, so make_post still runs this zero-cost local
check inline: an unambiguous hit is rejected immediately, exactly like the
old synchronous final rejection, and the post is never created.

This is deliberately a blunt, conservative instrument: a small list of
unambiguous profanity and slurs matched on word boundaries. Anything subtle
(context, sarcasm, imagery) is the AI cascade's job — a miss here just means
the post goes through the normal async review.
"""
import re

from .classifier_utils import ClassificationResult

# Unambiguous profanity — rule 1 ("No swear words"). Matched as whole words,
# case-insensitively, so e.g. "shiitake" or "class" never trip it.
_PROFANITY = (
    'fuck', 'fucking', 'fucked', 'fucker', 'motherfucker',
    'shit', 'bullshit', 'shitty',
    'bitch', 'bitches',
    'asshole', 'assholes',
    'cunt', 'cunts',
    'dickhead',
)

# Unambiguous slurs — rule 5 ("No hate speech"). Kept to terms with no benign
# everyday reading.
_SLURS = (
    'nigger', 'niggers',
    'faggot', 'faggots',
    'kike', 'kikes',
    'spic', 'spics',
    'tranny', 'trannies',
    'retard', 'retards', 'retarded',
)


def _word_pattern(words):
    return re.compile(r'\b(?:' + '|'.join(re.escape(w) for w in words) + r')\b', re.IGNORECASE)


_SLUR_PATTERN = _word_pattern(_SLURS)
_PROFANITY_PATTERN = _word_pattern(_PROFANITY)


def prefilter_text(text):
    """Local heuristic check for blatant violations; never calls an LLM.

    Returns a ClassificationResult: allowed=True when nothing blatant was
    found (the async cascade still runs), or a final, non-appealable
    rejection on an unambiguous hit. Slurs are checked first so a caption
    containing both reports the more serious reason.
    """
    text = str(text)
    if _SLUR_PATTERN.search(text):
        return ClassificationResult(allowed=False, appealable=False, reason_code='hate_speech')
    if _PROFANITY_PATTERN.search(text):
        return ClassificationResult(allowed=False, appealable=False, reason_code='profanity')
    return ClassificationResult(allowed=True)
