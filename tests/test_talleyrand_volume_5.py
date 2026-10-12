"""Acceptance checks for the complete preserved volume V source, not its neighbors."""
import json
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / 'recovery/talleyrand/2026-10-10/source-volume-5'
MANUSCRIPT = ROOT / 'translations/talleyrand/memoirs-volume-5-fr-ja.yaml'


class VolumeFiveTests(unittest.TestCase):
    def test_every_source_unit_and_restored_contents_keeps_its_id_text_and_order(self):
        source = json.loads((WITNESS / 'units.json').read_text('utf-8'))
        source += json.loads((WITNESS / 'facsimile-supplement-units.json').read_text('utf-8'))
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        actual = [s for s in doc['segments'] if s['origin'] == 'source']
        self.assertEqual(len(actual), 4531)
        self.assertEqual([s['id'] for s in actual], [u['id'] for u in source])
        for segment, unit in zip(actual, source):
            retained_texts = [segment['source_text']]
            retained_texts.extend(v['text'] for v in segment.get('source_variants', []))
            self.assertIn(unit['text'], retained_texts, segment['id'])
        self.assertTrue(all(s.get('translation_required', True) for s in actual))
        self.assertEqual(doc['work_id'], 'talleyrand-memoirs-volume-5')
        self.assertEqual(doc['metadata']['title_ja'], 'タレーラン公回想録 第五巻')

    def test_all_historical_notes_keep_their_distinct_body_members(self):
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        inventory = json.loads((WITNESS / 'notes-inventory.json').read_text('utf-8'))
        notes = {n['id']: n for n in doc['notes']}
        for original in inventory:
            note = notes['v05-' + original['anchor']]
            self.assertEqual(note['label'], original['label'])
            self.assertEqual([p['segment_id'] for p in note['body']], original['unit_ids'])
            self.assertNotEqual(note['origin'], 'digital_editor')

    def test_independent_source_findings(self):
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        segments = {s['id']: s for s in doc['segments']}
        reading = segments['v05-u000123']
        self.assertIn('un changement de ministère à Paris', reading['source_text'])
        self.assertIn('パリで内閣が交代し', reading['translation_ja'])
        self.assertTrue(any('un changement de propagande à Paris' in v['text'] for v in reading['source_variants']))
        self.assertTrue(segments['v05-u004051']['source_text'].endswith('403.'))
        self.assertTrue(any(v['text'].endswith('339.') for v in segments['v05-u004051']['source_variants']))
        for sid in ('v05-u001569', 'v05-u001585', 'v05-u001596'):
            self.assertEqual(segments[sid]['source_languages'], ['en'])
        self.assertEqual(segments['v05-u000785']['source_languages'], ['en', 'fr'])
        for sid in ('v05-u001616', 'v05-u001617', 'v05-u001618'):
            self.assertEqual(segments[sid]['attributions'][0]['voice'], 'editor')
        for label in ('266', '267'):
            note = next(n for n in doc['notes'] if n['label'] == label)
            self.assertIn('ミラボー伯爵夫人', note['description_ja'])
            self.assertNotIn('署名がない', note['description_ja'])

    def test_printed_frederick_entry(self):
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        entry = next(s for s in doc['segments'] if s['id'] == 'v05-u002984')
        self.assertIn('comme roi de Wurtemberg', entry['source_text'])
        self.assertTrue(any('comme MARET.' in v['text'] and v['kind'] == 'diplomatic'
                            for v in entry['source_variants']))
        self.assertTrue(any(l.get('printed_page') == '613' and l['url'].endswith('/n640.jpg')
                            for l in entry['source_locations']))
        if entry['translation_status'] != 'pending':
            self.assertIn('ヴュルテンベルク王としては一世', entry['translation_ja'])

    def test_draft_index_preserves_reference_numbers_and_stars(self):
        import re
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        for entry in doc['segments']:
            if not 2362 <= int(entry['id'].rsplit('u', 1)[1]) <= 4051:
                continue
            if entry['translation_status'] == 'pending':
                continue
            marker = re.search(r'(?:—|:|;)\s*(?=(?:[IV]+,|\d))', entry['source_text'])
            if marker:
                original = entry['source_text'][marker.end():]
                translated = entry['translation_ja'].split('—', 1)[1]
                self.assertEqual(re.findall(r'\d+|\*|\b[IV]+\b', translated),
                                 re.findall(r'\d+|\*|\b[IV]+\b', original), entry['id'])

    def test_index_cross_references_keep_their_named_destination(self):
        import re
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        for entry in doc['segments']:
            number = int(entry['id'].rsplit('u', 1)[1])
            if not 2362 <= number <= 4051:
                continue
            destination = re.search(r"\bvoir\s+([^.(]+)", entry['source_text'], re.I)
            if destination:
                # Descriptive titles are translated; the named heading is retained.
                name = re.split(r"\s+(?:rois?|reines?)\b", destination.group(1), flags=re.I)[0].strip()
                self.assertIn(name.casefold(), entry['translation_ja'].casefold(), entry['id'])
                self.assertIn('参照', entry['translation_ja'], entry['id'])

    def test_draft_never_claims_full_review_without_finished_translation(self):
        doc = yaml.safe_load(MANUSCRIPT.read_text('utf-8'))
        if any(s['translation_status'] in ('pending', 'draft') for s in doc['segments']):
            self.assertNotEqual(doc['workflow']['stage'], 'ready')
            self.assertNotEqual(doc['workflow'].get('full_review', {}).get('status'), 'complete')


if __name__ == '__main__':
    unittest.main()
