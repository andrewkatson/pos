"""The per-content model chain (issue #511): each round of review of the same
content leads with a cascade tier that has not judged it yet, and once every
tier has, the cycle restarts from a random tier."""
from unittest.mock import patch

from django.test import SimpleTestCase

from ..classifiers.classifier_utils import (
    API_CLAUDE, API_GEMINI, API_GEMMA, API_OPENAI, CASCADE_ORDER, ClassificationResult,
)
from ..classifiers.model_chain import record_round, round_order

ALL = list(CASCADE_ORDER)


def _result(consulted, decided_by, allowed=True):
    return ClassificationResult(allowed=allowed, consulted=list(consulted), decided_by=decided_by)


class RoundOrderTests(SimpleTestCase):

    def test_fresh_content_uses_the_normal_order(self):
        self.assertEqual(round_order(ALL, [], []), (ALL, False))

    def test_a_decider_drops_to_the_back(self):
        """The tier that settled the last verdict is the last resort next time,
        never the first opinion — that is the whole point of the chain."""
        order, reset = round_order(ALL, [API_GEMMA], [API_GEMMA])
        self.assertEqual(order, [API_GEMINI, API_OPENAI, API_CLAUDE, API_GEMMA])
        self.assertFalse(reset)

    def test_an_unsure_tier_sits_between_fresh_and_decided(self):
        """Gemma scored in the middle zone and Gemini then decided: fresh eyes
        first, then the tier that was unsure, then the decider."""
        order, _ = round_order(ALL, [API_GEMMA, API_GEMINI], [API_GEMINI])
        self.assertEqual(order, [API_OPENAI, API_CLAUDE, API_GEMMA, API_GEMINI])

    def test_deciders_keep_their_cheapest_first_order_among_themselves(self):
        order, _ = round_order(ALL, [API_OPENAI, API_GEMMA], [API_OPENAI, API_GEMMA])
        self.assertEqual(order, [API_GEMINI, API_CLAUDE, API_GEMMA, API_OPENAI])

    def test_a_complete_chain_resets_and_rotates_from_a_random_tier(self):
        with patch('user_system.classifiers.model_chain.random.randrange', return_value=2) as pick:
            order, reset = round_order(ALL, ALL, ALL)
        pick.assert_called_once_with(len(ALL))
        self.assertTrue(reset)
        # Rotated, not shuffled: the cascade fallbacks keep their relative order.
        self.assertEqual(order, [API_OPENAI, API_CLAUDE, API_GEMMA, API_GEMINI])

    def test_chain_order_does_not_matter_for_completeness(self):
        with patch('user_system.classifiers.model_chain.random.randrange', return_value=0):
            order, reset = round_order(ALL, ALL, list(reversed(ALL)))
        self.assertTrue(reset)
        self.assertEqual(order, ALL)

    def test_a_tier_added_to_the_cascade_is_fresh(self):
        """Every previously available tier has decided, but the cascade grew
        (env change): the new tier is untried, so the cycle is not complete."""
        old = [API_GEMMA, API_GEMINI]
        order, reset = round_order(ALL, old, old)
        self.assertFalse(reset)
        self.assertEqual(order, [API_OPENAI, API_CLAUDE, API_GEMMA, API_GEMINI])

    def test_a_tier_removed_from_the_cascade_is_ignored(self):
        available = [API_GEMMA, API_GEMINI]
        with patch('user_system.classifiers.model_chain.random.randrange', return_value=1):
            order, reset = round_order(available, ALL, ALL)
        self.assertTrue(reset)
        self.assertEqual(order, [API_GEMINI, API_GEMMA])

    def test_no_available_tiers(self):
        self.assertEqual(round_order([], [API_GEMMA], [API_GEMMA]), ([], False))


class RecordRoundTests(SimpleTestCase):

    def test_first_round_records_consulted_and_decider(self):
        tried, chain = record_round([], [], [_result([API_GEMMA, API_GEMINI], API_GEMINI)])
        self.assertEqual(tried, [API_GEMMA, API_GEMINI])
        self.assertEqual(chain, [API_GEMINI])

    def test_later_rounds_append_without_duplicates(self):
        tried, chain = record_round(
            [API_GEMMA], [API_GEMMA],
            [_result([API_GEMINI, API_GEMMA], API_GEMMA), _result([API_GEMINI], API_GEMINI)])
        self.assertEqual(tried, [API_GEMMA, API_GEMINI])
        # The latest decider is the chain's tail — the "final determiner".
        self.assertEqual(chain, [API_GEMMA, API_GEMINI])

    def test_a_repeat_decider_moves_to_the_tail(self):
        """A round settled by a fallback tier that had decided before: the
        chain stays duplicate-free, but its tail — the final determiner the
        admin shows — must be the tier that settled the LATEST verdict."""
        tried, chain = record_round(
            [API_GEMMA, API_GEMINI], [API_GEMMA, API_GEMINI],
            [_result([API_OPENAI, API_GEMMA], API_GEMMA)])
        self.assertEqual(tried, [API_GEMMA, API_GEMINI, API_OPENAI])
        self.assertEqual(chain, [API_GEMINI, API_GEMMA])

    def test_both_cascades_of_one_round_contribute(self):
        """A post's text and image cascades can settle on different tiers;
        both tiers have judged the content, so both join the chain."""
        tried, chain = record_round([], [], [
            _result([API_GEMMA], API_GEMMA),
            _result([API_GEMMA, API_GEMINI], API_GEMINI, allowed=False),
        ])
        self.assertEqual(tried, [API_GEMMA, API_GEMINI])
        self.assertEqual(chain, [API_GEMMA, API_GEMINI])

    def test_the_rejecting_half_is_the_final_determiner(self):
        """A text rejection hides the post even when the image is allowed, so
        the text tier — not the image tier — must end the chain."""
        tried, chain = record_round([], [], [
            _result([API_GEMMA, API_GEMINI], API_GEMINI, allowed=False),
            _result([API_GEMMA], API_GEMMA),
        ])
        self.assertEqual(tried, [API_GEMMA, API_GEMINI])
        self.assertEqual(chain, [API_GEMMA, API_GEMINI])

    def test_tried_keeps_first_use_order_when_a_rejection_moves_last(self):
        """Only the chain is reordered for a rejection; `tried` still lists
        tiers in the order the round actually consulted them."""
        tried, chain = record_round([], [], [
            _result([API_GEMINI], API_GEMINI, allowed=False),
            _result([API_OPENAI], API_OPENAI),
        ])
        self.assertEqual(tried, [API_GEMINI, API_OPENAI])
        self.assertEqual(chain, [API_OPENAI, API_GEMINI])

    def test_a_round_with_no_verdict_records_only_tried(self):
        failed = ClassificationResult(allowed=False, provider_failure=True, consulted=ALL)
        tried, chain = record_round([], [], [failed])
        self.assertEqual(tried, ALL)
        self.assertEqual(chain, [])

    def test_results_without_a_tier_change_nothing(self):
        """Testing mode, the local pre-filters and a text-only post's synthetic
        image result involve no tier at all."""
        tried, chain = record_round([API_GEMMA], [API_GEMMA], [ClassificationResult(allowed=True)])
        self.assertEqual((tried, chain), ([API_GEMMA], [API_GEMMA]))

    def test_reset_starts_a_new_cycle(self):
        tried, chain = record_round(ALL, ALL, [_result([API_OPENAI], API_OPENAI)], reset=True)
        self.assertEqual(tried, [API_OPENAI])
        self.assertEqual(chain, [API_OPENAI])

    def test_inputs_are_not_mutated(self):
        tried_in, chain_in = [API_GEMMA], [API_GEMMA]
        record_round(tried_in, chain_in, [_result([API_GEMINI], API_GEMINI)])
        self.assertEqual((tried_in, chain_in), ([API_GEMMA], [API_GEMMA]))
