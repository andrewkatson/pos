"""Rotating the classifier cascade across rounds of review (issue #511).

One piece of content can be judged by the cascade more than once: the initial
classification, the retry of a classification that reached no verdict, and the
automated re-review a user report triggers. Running the same fixed
cheapest-first order every time would hand every round to the same model —
whatever Gemma decided about a post the first time it would very likely decide
again on re-review, and the re-review would be theatre. So each post and
comment remembers which cascade tiers have already looked at it, and every
later round is ordered to put fresh eyes first:

1. tiers that have never been consulted about this content;
2. tiers that were consulted but did not settle a verdict (they scored in the
   middle zone and the cascade escalated past them, or they errored);
3. tiers whose score *did* settle an earlier verdict — the chain the issue
   asks for — as last-resort fallbacks, so a round still has the full cascade
   depth to escalate through.

Within each group the usual cheapest-first order is kept. Once every available
tier has decided once, the cycle is complete: both lists are cleared and the
next round starts from a tier chosen at random (the cascade order rotated to
begin there), so the second cycle is not a predictable replay of the first.

The two lists live on the content row (`classification_models_tried`,
`classification_model_chain`) and describe the current cycle only. The text
and image cascades of one round share one order, so the same tier gives the
first opinion on both halves of a post. Model identities are bookkeeping for
the pipeline and moderators; they are never exposed to users.

The lists are folded into the row under a row lock (apply_round on a freshly
locked instance): rounds of the same content can overlap — a duplicate queue
delivery, a retry landing beside a re-review — and a fold computed from a
pre-cascade read would overwrite whatever the other round recorded meanwhile.
"""
import logging
import random

logger = logging.getLogger(__name__)


def cycle_complete(available, chain):
    """Whether every available tier has settled a verdict on this content."""
    return bool(available) and set(available) <= set(chain)


def round_order(available, tried, chain):
    """Cascade order for the next round of review of one piece of content.

    `available` is the cascade in its normal priority order (see
    classifier_utils.get_available_apis); `tried` and `chain` are the content's
    stored lists. Returns `(order, reset)` where `reset` is True when every
    available tier has already decided once, meaning the round starts a new
    cycle and `record_round` must discard the old lists.
    """
    available = list(available)
    if not available:
        return [], False
    if cycle_complete(available, chain):
        # Every tier has settled a verdict on this content. Rotate rather than
        # shuffle so the cascade fallbacks stay in their cheapest-first order
        # relative to the (random) starting tier.
        start = random.randrange(len(available))
        order = available[start:] + available[:start]
        logger.info("Model chain complete (%s); starting a new cycle from %s.", chain, order[0])
        return order, True
    fresh = [api for api in available if api not in tried and api not in chain]
    unsure = [api for api in available if api in tried and api not in chain]
    decided = [api for api in available if api in chain]
    return fresh + unsure + decided, False


def record_round(tried, chain, results, reset=False):
    """Fold one round's cascade results into the stored lists.

    Returns the new `(tried, chain)`: every tier any result consulted is added
    to `tried` (no duplicates, first-use order), and every tier that settled
    one of the results goes to the END of `chain` — moved there if it was
    already in it — so the chain's tail is always the most recent decider (the
    "final determiner") even when a round was settled by a fallback tier that
    had decided before. A rejection is what settles a post's outcome — one
    rejected half hides the whole post — so rejecting results are folded after
    allowing ones and their tier lands last, whichever half it judged. With `reset` (a new cycle, see round_order) the lists
    start empty. Results that involved no tier — testing mode, a local
    pre-filter, a text-only post's image side — contribute nothing.
    """
    tried = [] if reset else list(tried)
    chain = [] if reset else list(chain)
    # Stable sort: allowing results first, so a rejecting tier ends the chain.
    for result in sorted(results, key=lambda r: not r.allowed):
        for api in result.consulted:
            if api not in tried:
                tried.append(api)
        if result.decided_by:
            if result.decided_by in chain:
                chain.remove(result.decided_by)
            chain.append(result.decided_by)
    return tried, chain


def plan_round(target, available):
    """The cascade order for a Post's or Comment's next round (round_order
    without the reset flag — apply_round re-derives that when it records)."""
    return round_order(available, target.classification_models_tried, target.classification_model_chain)[0]


def apply_round(target, results, available):
    """Fold one round's results into a Post's or Comment's lists (unsaved).

    Call it on an instance read fresh under a row lock, never on the one the
    round was planned from: by the time the cascades return, another round of
    the same content may have recorded. Whether this round starts a new cycle
    is decided here from the lists as they are now, for the same reason —
    the planning-time answer can be stale.
    """
    reset = cycle_complete(available, target.classification_model_chain)
    target.classification_models_tried, target.classification_model_chain = record_round(
        target.classification_models_tried, target.classification_model_chain, results, reset=reset)


# The two model fields the helpers above read and write, for callers' update_fields.
CHAIN_FIELDS = ('classification_models_tried', 'classification_model_chain')
