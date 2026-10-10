"""One-time migration invariants against the immutable source Git revision."""
import base64
import collections
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from translation_yaml import load_document, validate_catalog

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'a63dfa5727d2eca74c36e2fa54c010fa2a42be8e'
SOURCE_KEYS = ('source_text', 'original', 'source_la', 'source_en', 'source_fr', 'source_it', 'source_ru', 'source_original')


def old_documents():
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, 'translations'], cwd=ROOT).decode().splitlines()
    for path in paths:
        if path.endswith('.yaml'):
            raw = subprocess.check_output(['git', 'show', f'{BASELINE}:{path}'], cwd=ROOT)
            yield path, yaml.load(raw, Loader=yaml.CSafeLoader)


def primary(old):
    if 'segments' in old: return old['segments']
    if 'units' in old: return old['units']
    if 'parts' in old: return [s for p in old['parts'] for c in p['chapters'] for s in c['segments']]
    if 'folios' in old: return [s for f in old['folios'] for s in f['segments']]
    return old.get('front_matter', []) + [s for section in old['sections'] for s in section.get('segments', [])]


def walk(value, seen=None):
    if seen is None: seen = set()
    if isinstance(value, (dict, list)):
        if id(value) in seen: return
        seen.add(id(value))
    yield value
    if isinstance(value, dict):
        for k, child in value.items():
            if k != 'field_guide': yield from walk(child, seen)
    elif isinstance(value, list):
        for child in value: yield from walk(child, seen)


class MigrationTests(unittest.TestCase):
    def test_all_23_share_contract_and_preserve_data(self):
        count = 0
        for path, old in old_documents():
            print('Checking ' + path, flush=True)
            count += 1
            new = load_document(ROOT / path)
            self.pairs = [(path, old, new)]
            with self.subTest(path=path):
                self.assertEqual('2.0', new['schema_version'])
                self.check_all_active_primary_ids_and_exact_texts_survive()
                self.check_translator_note_strings_are_canonical_segments()
                self.check_groups_and_distinct_originals()
                self.check_explicit_footnotes_and_callout_spans_survive()
                self.check_untranslated_editorial_and_digital_supplements_preserved()
                self.check_embedded_images_are_extracted_without_byte_changes()
            self.pairs = []
        self.assertEqual(23, count)
        self.assertEqual([], validate_catalog(ROOT))

    def check_all_active_primary_ids_and_exact_texts_survive(self):
        for path, old, new in self.pairs:
            with self.subTest(path=path):
                units = {s['id']: s for s in new['segments']}
                old_ids = [s['id'] for s in primary(old)]
                old_id_set = set(old_ids)
                new_ids = [s['id'] for s in new['segments'] if s['id'] in old_id_set]
                expected = old.get('reader_order', old_ids)
                self.assertEqual(expected, new_ids)
                for segment in primary(old):
                    self.assertIn(segment['id'], units)
                    migrated = units[segment['id']]
                    self.assertEqual(segment.get('translation_ja', segment.get('japanese')), migrated['translation_ja'])
                    source = next((segment[k] for k in SOURCE_KEYS if k in segment), None)
                    self.assertEqual(source, migrated['source_text'])
                    if segment.get('source_ids'):
                        self.assertEqual([str(x) for x in segment['source_ids']],
                                         [x['original_unit_id'] for x in migrated['source_alignment']])

    def check_translator_note_strings_are_canonical_segments(self):
        for path, old, new in self.pairs:
            old_notes = []
            text_containers = [old.get(k, []) for k in ('segments', 'units', 'sections', 'parts', 'folios',
                                                        'front_matter', 'figures', 'facsimile_translations')]
            for node in walk(text_containers):
                if isinstance(node, dict):
                    for key in ('notes', 'translator_notes'):
                        values = node.get(key, [])
                        if isinstance(values, str): values = [values]
                        if isinstance(values, list): old_notes.extend(x for x in values if isinstance(x, str) and x)
            available = collections.Counter(s['translation_ja'] for s in new['segments']
                                             if s['origin'] == 'translator')
            for text, count in collections.Counter(old_notes).items():
                with self.subTest(path=path, note=text[:40]): self.assertGreaterEqual(available[text], count)

    def check_groups_and_distinct_originals(self):
        count = differences = 0
        for _, old, new in self.pairs:
            groups = {g['id']: g for g in new.get('groups', [])}
            units = {s['id']: s for s in new['segments']}
            for old_group in old.get('logical_render_groups', []):
                count += 1
                group = groups[old_group['id']]
                ids = [x['segment_id'] for x in group['members']]
                self.assertEqual(old_group['member_ids'], ids)
                self.assertEqual(old_group['translation_ja'], group['separator'].join(units[i]['translation_ja'] for i in ids))
                if old_group['source_text'] != group['separator'].join(units[i]['source_text'] for i in ids):
                    differences += 1
                    self.assertIn(old_group['source_text'], [x['text'] for x in group['source_variants']])
        self.assertEqual(sum(len(old.get('logical_render_groups', [])) for _, old, _ in self.pairs), count)
        self.assertEqual(10 if any('the-new-laokoon' in path for path, _, _ in self.pairs) else 0, differences)

    def check_explicit_footnotes_and_callout_spans_survive(self):
        for path, old, new in self.pairs:
            app = old.get('reader_apparatus', {})
            units = {s['id']: s for s in new['segments']}
            notes = {n['id']: n for n in new.get('notes', [])}
            refs = {r['id']: r for r in new.get('references', [])}
            for note in app.get('footnotes', []) + app.get('digital_footnotes', []):
                with self.subTest(path=path, note=note):
                    self.assertIn(note['id'], notes)
                    self.assertEqual(note['unit_id'], notes[note['id']]['body'][0]['segment_id'])
            for ref in app.get('callouts', []) + app.get('digital_callouts', []):
                with self.subTest(path=path, ref=ref['id']):
                    self.assertEqual(ref['footnote_id'], refs[ref['id']]['to']['id'])
                    span = refs[ref['id']]['from']['translation_span']
                    self.assertEqual((ref['start'], ref['end']), (span['start'], span['end']))
                    self.assertEqual(units[ref['unit_id']]['translation_ja'][ref['start']:ref['end']], span['exact'])

    def check_untranslated_editorial_and_digital_supplements_preserved(self):
        for _, old, new in self.pairs:
            units = {s['id']: s for s in new['segments']}
            for note in old.get('source_editorial_notes', []):
                self.assertEqual(note['source_it'], units[note['id']]['source_text'])
                self.assertFalse(units[note['id']]['translation_required'])
            for note in old.get('digital_editorial_notes', []):
                self.assertEqual(note['translation_ja'], units[note['id']]['translation_ja'])
            for supplement in old.get('facsimile_translations', []):
                texts = [s['translation_ja'] for s in new['segments']]
                for text in supplement['paragraphs_ja']: self.assertIn(text, texts)

    def check_embedded_images_are_extracted_without_byte_changes(self):
        for path, old, new in self.pairs:
            available = {a.get('sha256') for a in new.get('assets', []) if a['status'] == 'available'}
            for asset in old.get('image_assets', []):
                self.assertIn(asset['sha256'], available)
            for figure in old.get('figures', []):
                if figure.get('svg_sha256'): self.assertIn(figure['svg_sha256'], available)
            for node in walk(old):
                if isinstance(node, dict) and node.get('data_base64'):
                    raw = base64.b64decode(node['data_base64'])
                    with self.subTest(path=path, asset=node.get('id')):
                        self.assertIn(hashlib.sha256(raw).hexdigest(), available)


if __name__ == '__main__': unittest.main()
