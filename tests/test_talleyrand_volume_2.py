"""The second volume must preserve its pinned draft in the common contract."""
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from translation_yaml import load_document, validate_document

FILE = 'translations/talleyrand/memoirs-volume-2-fr-ja.yaml'
PIN = '39eecd94d356e08edd9538f3d7ae4d707d20a71b'


class VolumeTwoTests(unittest.TestCase):
    def test_pinned_translation_notes_typography_and_images_survive_migration(self):
        raw = subprocess.check_output(['git', 'show', f'{PIN}:{FILE}'], cwd=ROOT)
        old = yaml.load(raw, Loader=yaml.CSafeLoader)
        new = load_document(ROOT/FILE)
        self.assertEqual([], validate_document(new, ROOT))
        self.assertEqual(new['schema_version'], '2.0')
        self.assertFalse({'reader_order','render_blocks','reader_apparatus','logical_render_groups','structured_units'} & new.keys())
        units = {s['id']: s for s in new['segments']}
        self.assertEqual([s['id'] for s in new['segments'] if s['id'] in old['reader_order']], old['reader_order'])
        for s in old['segments']:
            self.assertEqual(units[s['id']]['source_text'], s['source_text'])
            self.assertEqual(units[s['id']]['translation_ja'], s['translation_ja'])
        notes = {n['id']: n for n in new['notes']}
        for n in old['reader_apparatus']['footnotes']:
            self.assertEqual([p['segment_id'] for p in notes[n['id']]['body']], [n['unit_id']]+n['continuation_unit_ids'])
        self.assertEqual(len([r for r in new['references'] if r['id'].startswith('v02-ref-')]), 478)
        for s in old['segments']:
            annotation = s.get('reader_annotations', {})
            spans = annotation.get('inline_spans', []) + [p for m in annotation.get('inline_mappings', []) for p in m['target_ranges']]
            actual = [a['span'] for a in units[s['id']].get('annotations', []) if a['side']=='translation']
            for p in spans:
                self.assertIn(dict(start=p['start'], end=p['end'], exact=s['translation_ja'][p['start']:p['end']]), actual)
        self.assertEqual(len(new['figures']), 2)
        self.assertEqual(len(new['assets']), 3)
        for a in new['assets']:
            self.assertEqual(a['status'], 'available')
            self.assertEqual(hashlib.sha256((ROOT/a['path']).read_bytes()).hexdigest(), a['sha256'])
        self.assertEqual(len(new['sources'][0]['page_inventory']), 570)
        self.assertEqual(new['workflow']['full_review']['status'], 'not_started')


if __name__ == '__main__': unittest.main()
