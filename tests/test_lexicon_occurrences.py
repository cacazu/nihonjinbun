"""Chapter annotations are separate from the reusable vocabulary dictionary."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from translation_yaml import content_hash, validate_document, validate_lexicon_occurrences
from test_translation_yaml import document
from test_xiyouji_lexicon import fixture


class ChapterLexiconTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'lexicons').mkdir()
        self.dictionary = fixture()
        self.write_dictionary()
        self.data = document()
        self.data['segments'][0]['translation_ja'] = '😀石猿（せきえん。石から生まれた猿）は進んだ。'
        self.data['lexicon'] = {'dictionary_id': 'xiyouji', 'file': 'lexicons/xiyouji.yaml',
            'first_occurrences': [{'entry_id': 'monkey', 'form_id': 'stone-monkey', 'segment_id': 'p1',
                'translation_span': {'start': 1, 'end': 3, 'exact': '石猿'},
                'rendered_text': '石猿（せきえん。石から生まれた猿）'}]}

    def write_dictionary(self):
        (self.root / 'lexicons/xiyouji.yaml').write_text(json.dumps(self.dictionary, ensure_ascii=False))

    def test_valid_unicode_body_anchor(self):
        self.assertEqual([], validate_document(self.data, self.root))

    def test_estimated_reading_does_not_require_body_confidence_label(self):
        reading = self.dictionary['entries'][0]['forms'][0]['reading']
        reading.update(status='estimated', source_ids=[], reason_ja='漢字の音からの仮の読み')
        self.write_dictionary()
        self.assertNotIn('推定', self.data['segments'][0]['translation_ja'])
        self.assertEqual([], validate_document(self.data, self.root))
        self.assertEqual('estimated', reading['status'])

    def test_old_document_hash_unchanged_and_new_field_is_hashed(self):
        self.assertEqual('09ff9f94c739a8d14fbc1b869e8e11101d2baadd2ba4a95583b863c1408be5b0',
                         content_hash(document()))
        before = copy.deepcopy(self.data); del before['lexicon']
        self.assertNotEqual(content_hash(before), content_hash(self.data))
        self.assertEqual([], validate_document(document(), self.root))

    def test_stale_complete_review_fails_after_annotation_added(self):
        before = copy.deepcopy(self.data); del before['lexicon']
        self.data['workflow']['full_review'] = {'status': 'complete', 'completed_at': '2026-10-24T00:00:00Z',
            'reviewed_by': 'test', 'content_sha256': content_hash(before)}
        self.assertTrue(any('stale content hash' in e for e in validate_document(self.data, self.root)))

    def test_earlier_note_heading_substring_and_explanation_do_not_override_human_choice(self):
        for ident, kind, text in [('h', 'heading', '石猿'), ('n', 'note_body', '石猿'),
                                  ('p0', 'paragraph', '石猿王。説明（石猿と呼ばれる者）。')]:
            segment = copy.deepcopy(self.data['segments'][0])
            segment.update(id=ident, kind=kind, translation_ja=text)
            self.data['segments'].insert(0, segment)
        self.assertEqual([], validate_document(self.data, self.root))

    def test_note_and_heading_anchor_rejected_but_poetry_allowed(self):
        for kind in ('note_body', 'heading'):
            self.data['segments'][0]['kind'] = kind
            self.assertTrue(validate_lexicon_occurrences(self.data, self.root))
        self.data['segments'][0]['kind'] = 'verse'
        self.assertEqual([], validate_document(self.data, self.root))

    def test_bad_dictionary_references_body_spans_and_reading(self):
        occurrence = self.data['lexicon']['first_occurrences'][0]
        for key, value in [('entry_id', 'missing'), ('form_id', 'missing'), ('segment_id', 'missing'),
                           ('translation_span', {'start': 2, 'end': 4, 'exact': '石猿'}),
                           ('rendered_text', '石猿（ちがう）')]:
            bad = copy.deepcopy(self.data)
            bad['lexicon']['first_occurrences'][0][key] = value
            self.assertTrue(validate_document(bad, self.root))
        self.dictionary['entries'][0]['forms'][0]['reading']['kana'] = 'せき'
        self.write_dictionary()
        self.assertTrue(validate_document(self.data, self.root))

    def test_one_form_once_and_reading_order(self):
        occurrences = self.data['lexicon']['first_occurrences']
        occurrences.append(copy.deepcopy(occurrences[0]))
        self.assertTrue(validate_document(self.data, self.root))
        occurrences.pop()
        alias = copy.deepcopy(self.dictionary['entries'][0]['forms'][0])
        alias.update(id='other', text='美猴王', relation='alias'); alias['reading']['kana'] = 'びこうおう'
        self.dictionary['entries'][0]['forms'].append(alias); self.write_dictionary()
        segment = copy.deepcopy(self.data['segments'][0]); segment.update(id='p2', translation_ja='美猴王（びこうおう）')
        self.data['segments'].append(segment)
        occurrences.append({'entry_id': 'monkey', 'form_id': 'other', 'segment_id': 'p2',
            'translation_span': {'start': 0, 'end': 3, 'exact': '美猴王'}, 'rendered_text': '美猴王（びこうおう）'})
        self.assertEqual([], validate_document(self.data, self.root))
        occurrences.reverse()
        self.assertTrue(validate_document(self.data, self.root))

    def test_kana_spelling_does_not_need_duplicate_reading(self):
        form = self.dictionary['entries'][0]['forms'][0]
        form['text'] = 'レイシ'; form['reading']['kana'] = 'れいし'
        self.dictionary['entries'][0]['headword'] = 'レイシ'; self.write_dictionary()
        self.data['segments'][0]['translation_ja'] = 'レイシは果物だ。'
        occurrence = self.data['lexicon']['first_occurrences'][0]
        occurrence.update(translation_span={'start': 0, 'end': 3, 'exact': 'レイシ'}, rendered_text='レイシ')
        self.assertEqual([], validate_document(self.data, self.root))

    def test_separate_gloss_is_optional_validated_and_hashed(self):
        occurrence = self.data['lexicon']['first_occurrences'][0]
        self.data['segments'][0]['translation_ja'] = '😀石猿（せきえん）は進んだ。'
        occurrence['rendered_text'] = '石猿（せきえん）'
        without = content_hash(self.data)
        self.assertEqual([], validate_document(self.data, self.root))
        occurrence['gloss_ja'] = '石から生まれた猿'
        self.assertEqual([], validate_document(self.data, self.root))
        self.assertNotEqual(without, content_hash(self.data))
        occurrence['rendered_text'] = '石猿（せきえん。石から生まれた猿）'
        self.data['segments'][0]['translation_ja'] = '😀石猿（せきえん。石から生まれた猿）は進んだ。'
        self.assertTrue(validate_document(self.data, self.root))
        occurrence['rendered_text'] = '石猿（せきえん）'
        self.data['segments'][0]['translation_ja'] = '😀石猿（せきえん）は進んだ。'
        for bad in ('', ' 　', None, [], 1):
            occurrence['gloss_ja'] = bad
            self.assertTrue(validate_document(self.data, self.root))
        del occurrence['gloss_ja']
        self.assertEqual(without, content_hash(self.data))

    def test_paths_id_mismatch_and_symlink_escape_rejected(self):
        for path in ('../xiyouji.yaml', '/tmp/xiyouji.yaml', 'lexicons/../xiyouji.yaml', 'lexicons/other.yaml'):
            bad = copy.deepcopy(self.data); bad['lexicon']['file'] = path
            self.assertTrue(validate_document(bad, self.root))
        self.dictionary['dictionary_id'] = 'other'; self.write_dictionary()
        self.assertTrue(validate_document(self.data, self.root))
        outside = self.root / 'outside.yaml'; outside.write_text(json.dumps(fixture()))
        path = self.root / 'lexicons/xiyouji.yaml'; path.unlink(); path.symlink_to(outside)
        self.assertTrue(validate_document(self.data, self.root))


if __name__ == '__main__':
    unittest.main()
