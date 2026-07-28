"""Cheap, local pre-filter for blatant caption violations (issues #282, #393).

Classification now runs asynchronously, so a genuinely negative post is
normally accepted with a "pending" response and rejected minutes later. For
the most blatant cases that is a UX regression (the author only learns by
email) and needless queue load, so make_post still runs this zero-cost local
check inline: an unambiguous hit is rejected immediately, exactly like the
old synchronous final rejection, and the post is never created.

This is deliberately a blunt instrument: a word/phrase-list match on word
boundaries, no LLM. Anything subtle (context, sarcasm, imagery) is the AI
cascade's job — a miss here just means the post goes through the normal async
review.

The profanity list is the vendored **LDNOOBW** word list (issue #393,
`data/ldnoobw_en.txt`), the "List of Dirty, Naughty, Obscene and Otherwise Bad
Words". It is far broader than a hand-maintained list, so it favours catching
blatant obscenity over avoiding every false positive — the trade the product
made by keeping these hits *final*. A short curated slur list is checked first
and reported as hate speech, so slurs surface the more serious reason even
though many also appear in LDNOOBW.
"""
import os
import re

from .classifier_utils import ClassificationResult

# Unambiguous slurs — rule 5 ("No hate speech"). Checked before the profanity
# list so a slur is reported as hate speech, not generic profanity. Kept to
# terms with no benign everyday reading.
_SLURS = (
    'nigger', 'niggers',
    'faggot', 'faggots',
    'kike', 'kikes',
    'spic', 'spics',
    'tranny', 'trannies',
    'retard', 'retards', 'retarded',
)

# Curated profanity kept as a floor under the vendored list, so the pre-filter
# never regresses on these even if the LDNOOBW file is trimmed or missing.
_CURATED_PROFANITY = (
    'fuck', 'fucking', 'fucked', 'fucker', 'motherfucker',
    'shit', 'bullshit', 'shitty',
    'bitch', 'bitches',
    'asshole', 'assholes',
    'cunt', 'cunts',
    'dickhead',
)

_LDNOOBW_FILE = os.path.join(os.path.dirname(__file__), 'data', 'ldnoobw_en.txt')


def _load_ldnoobw():
    """Load the vendored LDNOOBW terms, or fall back to the curated list.

    A missing/unreadable data file must never take the pre-filter down: it
    just degrades to the curated floor and the async cascade still runs.
    """
    try:
        with open(_LDNOOBW_FILE, encoding='utf-8') as fh:
            return [line.strip() for line in fh if line.strip()]
    except OSError:
        return []


def _term_regex(term):
    """Regex for one term/phrase: each whitespace-separated token escaped,
    joined by ``\\s+`` so multi-word phrases still match across runs of
    whitespace (e.g. "alabama  hot pocket")."""
    return r'\s+'.join(re.escape(token) for token in term.split())


def _word_pattern(terms):
    """Whole-word / whole-phrase, case-insensitive matcher for ``terms``.

    Word boundaries keep e.g. "shiitake" or "class" from tripping "shit"/"ass".
    Empty input yields a pattern that never matches (rather than an empty
    alternation, which would match everything).
    """
    unique = sorted({t for t in terms if t})
    if not unique:
        return re.compile(r'(?!)')
    return re.compile(r'\b(?:' + '|'.join(_term_regex(t) for t in unique) + r')\b',
                      re.IGNORECASE)


_SLUR_PATTERN = _word_pattern(_SLURS)
# Profanity = the vendored LDNOOBW list unioned with the curated floor.
_PROFANITY_PATTERN = _word_pattern(tuple(_CURATED_PROFANITY) + tuple(_load_ldnoobw()))


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
