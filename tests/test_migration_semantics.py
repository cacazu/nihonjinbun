"""Apparatus and physical structure must remain usable without legacy provenance."""
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from translation_yaml import load_document
from test_corpus_migration import BASELINE, ROOT, primary, walk


class ApparatusMigrationTests(unittest.TestCase):
    def test_publication_policy_is_preserved(self):
        path='translations/alchemy/rosarium-philosophorum-ja.yaml'
        old=yaml.load(subprocess.check_output(['git','show',f'{BASELINE}:{path}'],cwd=ROOT),Loader=yaml.CSafeLoader)
        new=load_document(ROOT/path)
        strings=[value for value in walk(new) if isinstance(value,str)]
        for value in walk(old['metadata']['editorial_policy']):
            if isinstance(value,str):self.assertTrue(any(value in text for text in strings), value)

    def test_semantic_structure_and_source_information(self):
        names = ('amphitheatrum', 'spanish', 'frammenti', 'zosimos', 'in-praise', 'folly',
                 'rosarium', 'talleyrand', 'stanislavsky-actor-work-on-role')
        paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, 'translations'], cwd=ROOT).decode().splitlines()
        count = 0
        for path in paths:
            if not path.endswith('.yaml') or not any(word in path for word in names): continue
            old = yaml.load(subprocess.check_output(['git', 'show', f'{BASELINE}:{path}'], cwd=ROOT), Loader=yaml.CSafeLoader)
            new = load_document(ROOT / path)
            units = {s['id']: s for s in new['segments']}
            sections = {s['id']: s for s in new['sections']}
            count += 1
            with self.subTest(path=path):
                for section in old.get('sections', []):
                    if section.get('parent_section_id'):
                        self.assertEqual(section['parent_section_id'], sections[section['id']]['parent_id'])
                for u in primary(old):
                    for style in u.get('source_style_spans', []):
                        self.assertTrue(any(a['span']['start'] == style['start'] and a['span']['end'] == style['end']
                                            for a in units[u['id']].get('annotations', [])))
                    if u.get('source_order') is not None:
                        self.assertEqual(u['source_order'], units[u['id']]['source_locations'][0]['source_sequence'])
                    annotation = u.get('reader_annotations', {})
                    if annotation.get('whole_unit_role') == 'quotation':
                        self.assertTrue(any(g['kind'] == 'quotation' and any(m['segment_id'] == u['id'] for m in g['members'])
                                            for g in new.get('groups', [])))
                    for block in annotation.get('block_spans', []):
                        if block['kind'] == 'quotation':
                            self.assertTrue(any(m['segment_id'] == u['id'] and m.get('translation_span', {}).get('end') == block['end']
                                                for g in new.get('groups', []) for m in g['members']))
                if old.get('original_work_language'):
                    self.assertEqual([old['original_work_language']], new['metadata']['original_languages'])
                    for s in old['sections']:
                        if s.get('greek_facsimile_url'):
                            locs = sections[s['chapter_id']]['source_locations']
                            self.assertTrue(any(l.get('url') == s['greek_facsimile_url'] and l.get('printed_page') == str(s['greek_page']) for l in locs))
                if 'amphitheatrum' in path:
                    self.assertTrue(any(g['kind'] == 'parallel' for g in new.get('groups', [])))
                    ids = {m['segment_id'] for g in new.get('groups', []) for m in g['members']}
                    self.assertTrue({u['id'] for u in primary(old) if u.get('parallel_text_sequence')} <= ids)
                for figure in old.get('figures', []):
                    if figure.get('source_native_image_url') or figure.get('source_image_url'):
                        url = figure.get('source_native_image_url', figure.get('source_image_url'))
                        self.assertTrue(any(l.get('url') == url for a in new.get('assets', []) for l in a['source_locations']))
                    if figure.get('source_crop_box_1000px'):
                        self.assertTrue(any(p.get('coordinate_image_width') == 1000 for a in new.get('assets', []) for p in a.get('processing', [])))
                    if figure.get('source_crop_box'):
                        migrated=next(f for f in new['figures'] if f['id']==figure.get('id',figure.get('segment_id')))
                        asset=next(a for a in new['assets'] if a['id']==migrated['asset_id'])
                        self.assertTrue(any(p.get('crop') for p in asset.get('processing', [])))
                        if figure.get('encoding', {}).get('resized') is False:
                            self.assertFalse(any(p['kind']=='resize' for p in asset.get('processing', [])))
                for qualification in old.get('source_qualifications', []):
                    self.assertTrue(any(qualification['qualification_ja'] in g['description_ja'] for g in new['scope']['known_gaps']))
                for omitted in old.get('source_apparatus', {}).get('omitted_inline_spans', []):
                    self.assertTrue(any(r['segment_id'] == omitted['segment_id'] for s in new['scope']['excluded'] for r in s.get('source_ranges', [])))
        self.assertGreaterEqual(count, 7)


if __name__ == '__main__': unittest.main()
