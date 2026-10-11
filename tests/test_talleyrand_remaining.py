"""Volume three retains its pinned source while translation advances."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from translation_yaml import load_document, validate_document

PIN = 'ce1b9bc9904d3d973fc0b6bc03d01a6b0e896c07'
PREFIX = 'recovery/talleyrand/2026-10-10'


def witness(volume, file):
    return json.loads(subprocess.check_output(
        ['git', 'show', f'{PIN}:{PREFIX}/source-volume-{volume}/{file}'], cwd=ROOT))


class RemainingVolumeTests(unittest.TestCase):
    def test_sources_notes_images_and_unfinished_state_are_explicit(self):
        for volume, count in [(3, 2337)]:
            with self.subTest(volume=volume):
                doc = load_document(ROOT / f'translations/talleyrand/memoirs-volume-{volume}-fr-ja.yaml')
                self.assertEqual([], validate_document(doc, ROOT))
                original = witness(volume, 'units.json')
                self.assertEqual(len(original), count)
                source_units = []
                for segment in doc['segments']:
                    for alignment in segment.get('source_alignment', []):
                        span = alignment.get('source_span')
                        text = (segment['source_text'][span['start']:span['end']]
                                if span else segment['source_text'])
                        source_units.append((alignment['original_unit_id'], text))
                # A source row may be split into cells; concatenation must preserve
                # every character and the original reading order.
                preserved = {}
                for ident, text in source_units:
                    preserved[ident] = preserved.get(ident, '') + text
                self.assertEqual(list(preserved), [u['id'] for u in original])
                for unit in original:
                    self.assertEqual(preserved[unit['id']], unit['text'])
                for note in witness(volume, 'notes-inventory.json'):
                    actual = next(n for n in doc['notes'] if n['id'] == f'v{volume:02}-note-{note["label"]}')
                    self.assertEqual([p['segment_id'] for p in actual['body']], note['unit_ids'])
                for asset in doc['assets']:
                    self.assertEqual(hashlib.sha256((ROOT / asset['path']).read_bytes()).hexdigest(), asset['sha256'])
                if any(s['translation_status'] == 'pending' and s.get('translation_required', True)
                       for s in doc['segments']):
                    self.assertEqual(doc['workflow']['stage'], 'translating')
                    self.assertNotEqual(doc['workflow']['full_review']['status'], 'complete')
                    self.assertTrue(doc['scope']['known_gaps'])

    def test_title_meaning_and_all_original_fragments_stay_together(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-3-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        aliases = {a['old_id']: a for a in doc['aliases']}
        for first in (1, 13):
            ident = f'v03-u{first:06}'
            heading = segments[ident]
            self.assertEqual(heading['source_text'], 'MÉMOIRES DU PRINCE DE TALLEYRAND')
            self.assertEqual(heading['translation_ja'], 'タレーラン公の回想録')
            self.assertEqual([a['original_unit_id'] for a in heading['source_alignment']],
                             [f'v03-u{i:06}' for i in range(first, first + 3)])
            for old in range(first + 1, first + 3):
                old_id = f'v03-u{old:06}'
                self.assertNotIn(old_id, segments)
                self.assertEqual(aliases[old_id]['new_id'], ident)
                self.assertIn('source_span', aliases[old_id])
                self.assertIn('translation_span', aliases[old_id])

    def test_translator_comment_is_separate_from_note_12(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-3-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        self.assertEqual(segments['v03-u001812']['translation_ja'], '[12] 異文：「さまざまな」。')
        note = next(n for n in doc['notes'] if n['id'] == 'v03-note-12-tn-001')
        self.assertEqual(note['origin'], 'translator')
        supplement = segments[note['body'][0]['segment_id']]
        self.assertEqual(supplement['origin'], 'translator')
        self.assertIsNone(supplement['source_text'])
        self.assertTrue(any(r['origin'] == 'translator' and
                            r['from']['segment_id'] == 'v03-u001812' and
                            r['to']['id'] == note['id'] for r in doc['references']))

    def test_signed_bacourt_note_names_the_contributor(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-3-fr-ja.yaml')
        note = next(n for n in doc['notes'] if n['id'] == 'v03-note-5')
        self.assertEqual(note['origin'], 'editor')
        contributor = next(c for c in doc['metadata']['contributors'] if c['id'] == note['contributor_id'])
        self.assertEqual(contributor['name_original'], 'Adolphe de Bacourt')
        segment = next(s for s in doc['segments'] if s['id'] == 'v03-u001805')
        self.assertTrue(any(a['voice'] == 'editor' and a.get('contributor_id') == contributor['id']
                            for a in segment['attributions']))

    def test_original_tables_have_two_columns_and_the_page_break_is_joined(self):
        doc = load_document(ROOT / 'translations/talleyrand/memoirs-volume-3-fr-ja.yaml')
        segments = {s['id']: s for s in doc['segments']}
        for gid, rows in [('v03-table-signatures', 8), ('v03-table-cabinet', 11)]:
            group = next((g for g in doc['groups'] if g['id'] == gid), None)
            self.assertIsNotNone(group)
            self.assertEqual(group['kind'], 'table')
            self.assertEqual([(m['row'], m['column']) for m in group['members']],
                             [(row, col) for row in range(1, rows + 1) for col in (1, 2)])
            self.assertTrue(all(segments[m['segment_id']]['kind'] == 'table_cell'
                                for m in group['members']))
        joined = next((g for g in doc['groups'] if g['id'] == 'v03-paragraph-page-110-111'), None)
        self.assertIsNotNone(joined)
        self.assertEqual(joined['kind'], 'paragraph')
        self.assertEqual([m['segment_id'] for m in joined['members']], ['v03-u000501', 'v03-u000502'])


if __name__ == '__main__':
    unittest.main()
