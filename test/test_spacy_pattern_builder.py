'''
Tests for `spacy-pattern-builder` module.
'''
import pytest
from pprint import pprint
import json
import en_core_web_sm
from spacy.tokens import Token
from spacy_pattern_builder import (
    build_dependency_pattern,
    yield_pattern_permutations,
    yield_node_level_pattern_variants,
    yield_extended_trees,
)
from spacy_pattern_builder.exceptions import (
    TokensNotFullyConnectedError,
    DuplicateTokensError,
)
import spacy_pattern_builder.util as util
import spacy_pattern_builder.match as match


nlp = en_core_web_sm.load()

text1 = 'We introduce efficient methods for fitting Boolean models to molecular data, successfully demonstrating their application to synthetic time courses generated by a number of established clock models, as well as experimental expression levels measured using luciferase imaging.'

text2 = 'Moreover, again only in sCON individuals, we observed a significant positive correlation between ASL and wine in overlapping left parietal WM indicating better baseline brain perfusion.'

text3 = 'We focused on green tea and performed a systematic review of observational studies that examined the association between green tea intake and dementia, Alzheimer\'s disease, mild cognitive impairment, or cognitive impairment.'

text4 = 'L-theanine alone improved self-reported relaxation, tension, and calmness starting at 200 mg.'


doc1 = nlp(text1)
doc2 = nlp(text2)
doc3 = nlp(text3)
doc4 = nlp(text4)

cases = [
    {
        'example': {
            'doc': doc1,
            'match': util.idxs_to_tokens(doc1, [0, 1, 3]),  # [We, introduce, methods]
        }
    },
    {
        'example': {
            'doc': doc1,
            'match': util.idxs_to_tokens(
                doc1, [13, 15, 16, 19]
            ),  # [demonstrating, application, to, courses]
        }
    },
    {
        'example': {
            'doc': doc3,
            'match': util.idxs_to_tokens(doc3, [0, 1, 2, 4]),  # [We, focused, on, tea]
        },
        'should_miss': [
            {
                'doc': doc2,
                'match': util.idxs_to_tokens(
                    doc2, [4, 8, 9, 18]
                ),  # [in, we, observed, in]
            }
        ],
    },
    {
        'example': {
            'doc': doc4,
            'match': util.idxs_to_tokens(
                doc4, [2, 4, 8]
            ),  # [theanine, relaxation, improved]
        }
    },
]


class TestSpacyPatternBuilder(object):
    def test_build_pattern(self):
        feature_dict = {'DEP': 'dep_', 'TAG': 'tag_'}
        for i, case in enumerate(cases):
            doc = case['example']['doc']
            match_example = case['example']['match']
            pattern = build_dependency_pattern(doc, match_example, feature_dict)
            matches = match.find_matches(doc, pattern)
            assert match_example in matches, 'does not match example'
            pattern_file_name = 'examples/pattern_{}.json'.format(i)
            with open(pattern_file_name, 'w') as f:
                json.dump(pattern, f, indent=2)
            if 'should_hit' in case:
                for item in case['should_hit']:
                    doc = item['doc']
                    hit_match = item['match']
                    matches = match.find_matches(doc, pattern)
                    assert hit_match in matches, 'false negative'
            if 'should_miss' in case:
                for item in case['should_miss']:
                    doc = item['doc']
                    miss_match = item['match']
                    matches = match.find_matches(doc, pattern)
                    assert miss_match not in matches, 'false positive'

    def test_custom_extension(self):
        Token.set_extension('custom_attr', default=False)
        feature_dict = {'DEP': 'dep_', '_': {'custom_attr': 'custom_attr'}}
        for i, case in enumerate(cases):
            doc = case['example']['doc']
            for token in doc:
                token._.custom_attr = 'my_attr'
            match_example = case['example']['match']
            pattern = build_dependency_pattern(doc, match_example, feature_dict)
            matches = match.find_matches(doc, pattern)
            assert match_example in matches, 'does not match example'
            pattern_file_name = 'examples/pattern_{}.json'.format(i)
            with open(pattern_file_name, 'w') as f:
                json.dump(pattern, f, indent=2)
            if 'should_hit' in case:
                for item in case['should_hit']:
                    doc = item['doc']
                    hit_match = item['match']
                    matches = match.find_matches(doc, pattern)
                    assert hit_match in matches, 'false negative'
            if 'should_miss' in case:
                for item in case['should_miss']:
                    doc = item['doc']
                    miss_match = item['match']
                    matches = match.find_matches(doc, pattern)
                    assert miss_match not in matches, 'false positive'

    def test_tokens_not_connected_error(self):
        doc = doc1
        match_examples = [
            util.idxs_to_tokens(
                doc, [19, 20, 21, 27]
            )  # [courses, generated, by, models]
        ]
        feature_dict = {'DEP': 'dep_', 'TAG': 'tag_'}
        for match_example in match_examples:
            with pytest.raises(TokensNotFullyConnectedError):
                build_dependency_pattern(doc, match_example, feature_dict)

    def test_duplicate_tokens_error(self):
        doc = doc1
        match_examples = [
            util.idxs_to_tokens(
                doc, [0, 1, 1, 3]
            )  # [We, introduce, introduce, methods]
        ]
        for match_example in match_examples:
            with pytest.raises(DuplicateTokensError):
                build_dependency_pattern(doc, match_example)

    def test_yield_node_level_pattern_variants(self):
        # Build initial pattern
        doc = doc1
        match_tokens = util.idxs_to_tokens(doc, [0, 1, 3])  # [We, introduce, methods]
        feature_dict = {'DEP': 'dep_', 'TAG': 'tag_'}
        pattern = build_dependency_pattern(doc, match_tokens, feature_dict)

        feature_dicts = (
            {'DEP': 'dep_', 'TAG': 'tag_'},
            {'DEP': 'dep_', 'TAG': 'tag_', 'LOWER': 'lower_'},
        )
        pattern_variants = list(
            yield_node_level_pattern_variants(pattern, match_tokens, feature_dicts)
        )
        assert not util.list_contains_duplicates(pattern_variants)
        n_variants = len(pattern_variants)
        assert n_variants == len(feature_dicts) ** len(pattern)
        for pattern_variant in pattern_variants:
            matches = match.find_matches(doc, pattern_variant)
            assert match_tokens in matches

        # Test mutate_tokens parameter
        pattern_variants = list(
            yield_node_level_pattern_variants(
                pattern, match_tokens, feature_dicts, mutate_tokens=[match_tokens[1]]
            )
        )
        n_variants = len(pattern_variants)
        assert n_variants == len(feature_dicts) ** len(pattern)
        for pattern_variant in pattern_variants:
            matches = match.find_matches(doc, pattern_variant)
            assert match_tokens in matches

    def test_yield_extended_trees(self):
        # Build initial pattern
        doc = doc1
        match_tokens = util.idxs_to_tokens(doc, [0, 1, 3])  # [We, introduce, methods]
        feature_dict = {'DEP': 'dep_', 'TAG': 'tag_', 'LOWER': 'lower_'}
        pattern = build_dependency_pattern(doc, match_tokens, feature_dict)

        match_tokens_variants = list(yield_extended_trees(match_tokens))

        pattern_variants = [
            build_dependency_pattern(doc, match_token_variant, feature_dict)
            for match_token_variant in match_tokens_variants
        ]

        assert not util.list_contains_duplicates(pattern_variants)
        n_variants = len(pattern_variants)
        for pattern_variant, match_tokens_variant in zip(
            pattern_variants, match_tokens_variants
        ):
            matches = match.find_matches(doc, pattern_variant)
            match_tokens_variant = sorted(match_tokens_variant, key=lambda t: t.i)
            assert match_tokens_variant in matches

    # def test_yield_pattern_permutations(self):
    #     doc = doc1
    #     match_example = util.idxs_to_tokens(doc, [0, 1, 3])  # [We, introduce, methods]
    #     feature_dict = {'DEP': 'dep_', 'TAG': 'tag_', 'LOWER': 'lower_'}
    #     pattern = build_dependency_pattern(doc, match_example, feature_dict)

    #     feature_sets = (('DEP', 'TAG'), ('DEP', 'TAG', 'LOWER'))
    #     pattern_variants = list(yield_pattern_permutations(pattern, feature_sets))
    #     assert not util.list_contains_duplicates(pattern_variants)
    #     n_variants = len(pattern_variants)
    #     assert n_variants == len(feature_sets) ** len(pattern)
    #     for pattern_variant in pattern_variants:
    #         matches = match.find_matches(doc, pattern_variant)
    #         assert match_example in matches

    #     feature_sets = (('DEP',), ('DEP', 'TAG'), ('DEP', 'TAG', 'LOWER'))
    #     pattern_variants = list(yield_pattern_permutations(pattern, feature_sets))
    #     assert not util.list_contains_duplicates(pattern_variants)
    #     n_variants = len(pattern_variants)
    #     assert n_variants == len(feature_sets) ** len(pattern)
    #     for pattern_variant in pattern_variants:
    #         matches = match.find_matches(doc, pattern_variant)
    #         assert match_example in matches
