import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from translation_yaml import content_hash, load_document, validate_document


def document():
    return {
        'schema_version': '2.0', 'work_id': 'example',
        'metadata': {'title_ja': '例', 'title_original': 'Example',
                     'original_languages': ['en'], 'target_language': 'ja',
                     'contributors': [], 'translation_rights': {'status': 'unknown'}},
        'sources': [{'id': 'original', 'role': 'primary', 'title': 'Example',
                     'languages': ['en'], 'url': None, 'edition': None,
                     'work_rights': {'status': 'unknown'},
                     'transcription_rights': {'status': 'unknown'}}],
        'scope': {'included': [{'source_id': 'original', 'description_ja': '本文'}],
                  'excluded': [], 'known_gaps': []},
        'sections': [{'id': 'body', 'parent_id': None, 'kind': 'editorial_group',
                      'origin': 'editorial', 'label_ja': '本文', 'heading_segment_ids': []}],
        'segments': [{'id': 'p1', 'section_id': 'body', 'kind': 'paragraph',
                      'origin': 'source', 'source_text': 'A😀.[1]', 'source_languages': ['en'],
                      'source_locations': [{'source_id': 'original', 'precision': 'work'}],
                      'translation_ja': '例😀。[1]', 'translation_status': 'draft'}],
        'workflow': {'stage': 'reviewing'},
    }


class ContractTests(unittest.TestCase):
    def assert_valid(self, data):
        self.assertEqual([], validate_document(data))

    def test_minimal_document_and_unknown_field(self):
        d = document()
        self.assert_valid(d)
        d['segments'][0]['japanese'] = '別経路'
        self.assertTrue(validate_document(d))

    def test_typed_note_refs_and_unicode_codepoint_spans(self):
        d = document()
        note = copy.deepcopy(d['segments'][0])
        note.update(id='note-text', kind='note_body', source_text='[1] Note.', translation_ja='[1] 注。')
        d['segments'].append(note)
        d['notes'] = [{'id': 'note-1', 'origin': 'author', 'label': '1',
                       'body': [{'segment_id': 'note-text'}]}]
        d['references'] = [{'id': 'ref-1', 'kind': 'note', 'origin': 'source',
                            'from': {'segment_id': 'p1', 'translation_span':
                                     {'start': 3, 'end': 6, 'exact': '[1]'}},
                            'to': {'type': 'note', 'id': 'note-1'}, 'status': 'verified'}]
        self.assert_valid(d)
        d['references'][0]['from']['translation_span']['start'] = 4
        self.assertTrue(validate_document(d))
        d['references'][0]['from'].pop('translation_span')
        d['references'][0]['to']['id'] = 'missing'
        self.assertTrue(validate_document(d))

    def test_excluded_untranslated_editorial_note(self):
        d = document()
        s = d['segments'][0]
        s.update(translation_required=False, translation_ja=None, translation_status='pending')
        self.assertTrue(validate_document(d))
        d['scope']['included'][0]['description_ja'] = '別の本文範囲'
        d['scope']['excluded'].append({'source_id': 'original', 'segment_ids': ['p1'],
                                     'description_ja': '未訳編者注を保持'})
        self.assert_valid(d)

    def test_ready_requires_real_review_and_matching_hash(self):
        d = document()
        d['workflow']['stage'] = 'ready'
        self.assertTrue(validate_document(d))
        d['segments'][0]['translation_status'] = 'reviewed'
        d['workflow']['full_review'] = {'status': 'complete',
                                      'completed_at': '2026-10-11T00:00:00Z',
                                      'reviewed_by': 'reviewer', 'content_sha256': content_hash(d)}
        self.assert_valid(d)
        d['segments'][0]['translation_ja'] += '変更'
        self.assertTrue(validate_document(d))

    def test_hash_optional_arrays_and_provenance(self):
        d = document()
        h = content_hash(d)
        d['notes'] = []
        d['provenance'] = {'previous_review': '履歴'}
        d['workflow']['stage'] = 'translating'
        self.assertEqual(h, content_hash(d))

    def test_hierarchy_cycles_and_duplicate_ids(self):
        d = document()
        d['sections'][0]['parent_id'] = 'body'
        self.assertTrue(validate_document(d))
        d = document()
        d['segments'].append(copy.deepcopy(d['segments'][0]))
        self.assertTrue(validate_document(d))

    def test_many_to_one_alignment_and_unattached_note(self):
        d = document()
        d['segments'][0]['source_alignment'] = [
            {'source_id': 'original', 'original_unit_id': '1'},
            {'source_id': 'original', 'original_unit_id': '2'}]
        d['notes'] = [{'id': 'unattached', 'origin': 'unknown', 'description_ja': '署名なし',
                       'body': [{'segment_id': 'p1'}]}]
        self.assert_valid(d)

    def test_groups_preserve_noncontiguous_members_and_distinct_source(self):
        d = document()
        for i in range(2, 4):
            s = copy.deepcopy(d['segments'][0]); s['id'] = f'p{i}'; d['segments'].append(s)
        d['groups'] = [{'id': 'poem', 'kind': 'poem', 'members':
                        [{'segment_id': 'p1'}, {'segment_id': 'p3'}], 'separator': '\n',
                        'source_variants': [{'kind': 'corrected', 'text': 'Different assembled original'}]}]
        self.assert_valid(d)
        d['groups'][0]['members'].reverse()
        self.assertTrue(validate_document(d))

    def test_image_only_section_planned_asset_and_unsafe_path(self):
        d = document()
        d['segments'] = []
        d['assets'] = [{'id': 'image', 'status': 'planned', 'path': 'assets/example/image.png',
                        'media_type': 'image/png', 'rights': {'status': 'unknown'},
                        'source_locations': []}]
        d['figures'] = [{'id': 'plate', 'asset_id': 'image', 'caption_ja': None, 'alt_ja': None,
                         'placement': {'anchor_type': 'section', 'anchor_id': 'body', 'position': 'start'},
                         'required': True}]
        self.assert_valid(d)
        d['assets'][0]['path'] = 'assets/example/../secret.png'
        self.assertTrue(validate_document(d))

    def test_loader_rejects_duplicate_keys_aliases_and_extra_documents(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'bad.yaml'
            for raw in ['a: 1\na: 2\n', 'a: &one []\nb: *one\n', '---\na: 1\n---\nb: 2\n']:
                p.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError): load_document(p)

    def test_crossing_attributions_and_sibling_group_overlap_are_rejected(self):
        d = document()
        source = d['segments'][0]['source_text']
        d['segments'][0]['attributions'] = [
            {'voice': 'author', 'source_span': {'start': 0, 'end': 4, 'exact': source[:4]}},
            {'voice': 'editor', 'source_span': {'start': 3, 'end': 6, 'exact': source[3:6]}}]
        self.assertTrue(validate_document(d))
        d = document()
        d['groups'] = [{'id': ident, 'kind': 'poem', 'members': [{'segment_id': 'p1'}],
                        'separator': '\n'} for ident in ('g1', 'g2')]
        self.assertTrue(validate_document(d))

    def test_invalid_calendar_url_language_and_blank_explanation(self):
        for kind in ('date', 'url', 'language', 'issue'):
            with self.subTest(kind=kind):
                d = document()
                if kind == 'date':
                    d['workflow']['full_review'] = {'status': 'complete', 'completed_at': '2026-99-99T88:99:99Z',
                                                  'reviewed_by': 'reviewer', 'content_sha256': content_hash(d)}
                elif kind == 'url': d['sources'][0]['url'] = 'https:///'
                elif kind == 'language': d['metadata']['original_languages'] = ['en-a']
                else:
                    d['segments'][0]['source_text'] = None
                    d['segments'][0]['issues'] = [{'kind': 'source_untranscribed', 'status': 'open', 'message_ja': '  '}]
                self.assertTrue(validate_document(d))

    def test_ready_partial_translation_needs_scoped_gap(self):
        d = document()
        d['segments'][0].update(translation_status='partial', issues=[
            {'kind': 'uncertain_translation', 'status': 'open', 'message_ja': '一節が未確定'}])
        d['workflow'] = {'stage': 'ready', 'full_review': {'status': 'complete',
                        'completed_at': '2026-10-11T00:00:00Z', 'reviewed_by': 'reviewer',
                        'content_sha256': content_hash(d)}}
        self.assertTrue(validate_document(d))
        d['scope']['known_gaps'].append({'segment_ids': ['p1'], 'description_ja': '一節が未確定'})
        d['workflow']['full_review']['content_sha256'] = content_hash(d)
        self.assert_valid(d)

    def test_partial_quotation_and_inline_scope_use_exact_spans(self):
        d = document()
        s = d['segments'][0]
        source_span = {'start': 0, 'end': 3, 'exact': s['source_text'][:3]}
        target_span = {'start': 0, 'end': 2, 'exact': s['translation_ja'][:2]}
        d['groups'] = [{'id': 'quote', 'kind': 'quotation', 'separator': '',
                        'members': [{'segment_id': 'p1', 'translation_span': target_span}]}]
        d['scope']['excluded'].append({'source_id': 'original', 'description_ja': '本文中の別言語の傍記',
            'source_ranges': [{'segment_id': 'p1', 'span': source_span}]})
        self.assert_valid(d)
        d['groups'][0]['members'][0]['translation_span']['exact'] = '違う'
        self.assertTrue(validate_document(d))

    def test_crop_recipe_preserves_coordinate_scale_before_source_is_available(self):
        d = document()
        d['assets'] = [{'id': 'scan', 'status': 'planned', 'path': 'assets/example/scan.jpg',
                       'media_type': 'image/jpeg', 'rights': {'status': 'unknown'}, 'source_locations': []},
                      {'id': 'crop', 'status': 'planned', 'path': 'assets/example/crop.webp',
                       'media_type': 'image/webp', 'rights': {'status': 'unknown'}, 'source_locations': [],
                       'derived_from_asset_id': 'scan', 'processing': [{'kind': 'crop',
                       'description_ja': '幅1000pxの原画像から切り出す', 'coordinate_image_width': 1000,
                       'crop': {'unit': 'pixel', 'x': 90, 'y': 415, 'width': 620, 'height': 745}}]}]
        self.assert_valid(d)
        d['assets'][1]['processing'][0]['crop']['width'] = 1001
        self.assertTrue(validate_document(d))

    def test_invalid_url_host_is_reported_and_private_language_is_valid(self):
        d = document()
        d['metadata']['original_languages'] = ['x-private']
        self.assert_valid(d)
        d['sources'][0]['url'] = 'https://[bad/'
        self.assertTrue(validate_document(d))


if __name__ == '__main__':
    unittest.main()
