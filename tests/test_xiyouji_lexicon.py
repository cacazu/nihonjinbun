import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from translation_yaml import load_document
from validate_xiyouji_lexicon import validate_lexicon


def fixture():
    evidence = {'status': 'estimated', 'source_ids': [], 'reason_ja': '構成字の音読みから推定。'}
    return {'schema_version': '1.0', 'dictionary_id': 'xiyouji', 'title_ja': '西遊記辞書',
            'sources': [{'id': 'source', 'title': '底本', 'url': 'https://example.org/book',
                         'accessed_at': '2026-10-24'}],
            'entries': [{'id': 'monkey', 'kind': 'person', 'headword': '石猿',
                         'definition_ja': '石から生まれた猿。', 'definition_evidence': copy.deepcopy(evidence),
                         'forms': [{'id': 'stone-monkey', 'text': '石猿', 'relation': 'preferred',
                                    'reading': {'kana': 'せきえん', **copy.deepcopy(evidence)}}]}]}


class LexiconTests(unittest.TestCase):
    def test_valid_without_any_chapter_or_translation(self):
        self.assertEqual([], validate_lexicon(fixture()))

    def test_required_reading_meaning_status_and_evidence(self):
        for field in ('definition_ja', 'definition_evidence'):
            data = fixture(); del data['entries'][0][field]
            self.assertTrue(validate_lexicon(data))
        for field in ('kana', 'reason_ja', 'status'):
            data = fixture(); del data['entries'][0]['forms'][0]['reading'][field]
            self.assertTrue(validate_lexicon(data))
        for kind in ('reading', 'definition'):
            data = fixture(); e = data['entries'][0]
            evidence = e['forms'][0]['reading'] if kind == 'reading' else e['definition_evidence']
            evidence['status'] = 'verified'
            self.assertTrue(validate_lexicon(data))
            evidence['source_ids'] = ['source']
            self.assertEqual([], validate_lexicon(data))
            evidence['source_ids'] = ['missing']
            self.assertTrue(validate_lexicon(data))

    def test_duplicate_ids(self):
        for collection in ('sources', 'entries'):
            data = fixture(); data[collection].append(copy.deepcopy(data[collection][0]))
            self.assertTrue(validate_lexicon(data))
        data = fixture(); forms = data['entries'][0]['forms']
        forms.append(copy.deepcopy(forms[0])); forms[-1]['relation'] = 'alias'
        self.assertTrue(validate_lexicon(data))

    def test_aliases_share_one_entity(self):
        data = fixture(); forms = data['entries'][0]['forms']
        alias = copy.deepcopy(forms[0]); alias.update(id='king', text='美猴王', relation='alias')
        alias['reading']['kana'] = 'びこうおう'; forms.append(alias)
        self.assertEqual([], validate_lexicon(data))

    def test_preferred_form_matches_headword(self):
        data = fixture(); data['entries'][0]['headword'] = '別人'
        self.assertTrue(validate_lexicon(data))

    def test_all_categories_require_reading_and_definition(self):
        for kind in ('person', 'place', 'title', 'object', 'concept', 'term'):
            data = fixture(); data['entries'][0]['kind'] = kind
            self.assertEqual([], validate_lexicon(data))
            del data['entries'][0]['forms'][0]['reading']
            self.assertTrue(validate_lexicon(data))

    def test_chapter_specific_tracking_is_rejected(self):
        for key, value in [('coverage', {'reviewed_work_ids': ['ch1']}), ('work_id', 'ch1')]:
            data = fixture(); data[key] = value
            self.assertTrue(validate_lexicon(data))
        for key, value in [('first_occurrences', []), ('segment_id', 'p1'),
                           ('translation_span', {'start': 0, 'end': 2, 'exact': '石猿'}),
                           ('rendered_text', '石猿（せきえん）')]:
            data = fixture(); data['entries'][0]['forms'][0][key] = value
            self.assertTrue(validate_lexicon(data))

    def test_invalid_dates_urls_unknown_fields_and_blank_explanations(self):
        data = fixture(); data['sources'][0]['accessed_at'] = '2026-02-30'
        self.assertTrue(validate_lexicon(data))
        data = fixture(); data['sources'][0]['url'] = 'https://user:secret@example.org'
        self.assertTrue(validate_lexicon(data))
        data = fixture(); data['unexpected'] = True
        self.assertTrue(validate_lexicon(data))
        data = fixture(); data['entries'][0]['definition_ja'] = '   '
        self.assertTrue(validate_lexicon(data))

    def test_shared_loader_rejects_duplicate_keys_aliases_and_non_json(self):
        for text in ('a: 1\na: 2\n', 'a: &value text\nb: *value\n', 'a: !!str text\n', '1: value\n'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'lexicon.yaml'; path.write_text(text)
                with self.assertRaises(ValueError):
                    load_document(path)


if __name__ == '__main__':
    unittest.main()
