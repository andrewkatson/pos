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
"""
import logging
import random

logger = logging.getLogger(__name__)


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
    if set(available) <= set(chain):
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
    to `tried`, and every tier that settled one of the results is appended to
    `chain`, each without duplicates and preserving first-use order. With
    `reset` (a new cycle, see round_order) the lists start empty. Results that
    involved no tier — testing mode, a local pre-filter, a text-only post's
    image side — contribute nothing.
    """
    tried = [] if reset else list(tried)
    chain = [] if reset else list(chain)
    for result in results:
        for api in result.consulted:
            if api not in tried:
                tried.append(api)
        if result.decided_by and result.decided_by not in chain:
            chain.append(result.decided_by)
    return tried, chain


def plan_round(target, available):
    """round_order for a Post or Comment, read from its stored lists."""
    return round_order(available, target.classification_models_tried, target.classification_model_chain)


def apply_round(target, results, reset=False):
    """record_round for a Post or Comment, written back to its lists (unsaved)."""
    target.classification_models_tried, target.classification_model_chain = record_round(
        target.classification_models_tried, target.classification_model_chain, results, reset=reset)


# The two model fields the helpers above read and write, for callers' update_fields.
CHAIN_FIELDS = ('classification_models_tried', 'classification_model_chain')
